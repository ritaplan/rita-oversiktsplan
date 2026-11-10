"""Flytta, kopiera och ta bort planer i en PostGIS-databas, och flytta dem till och från GeoPackage-filer (som i Rita
Detaljplan).

* **Importera** lägger en plan ur en GeoPackage som en ny plan i ett schema i databasen. Allt läses ur filen först, och
  raderna skrivs sedan i en enda transaktion (allt eller inget). Antalet rader i varje tabell kontrolleras efteråt, och
  går något fel tas den nya planen bort igen.
* **Exportera** sparar en plan ur databasen som en ny GeoPackage, utan att checka ut den eller låsa den för andra. Filen
  är planen som den ligger i databasen, inte någons utcheckade arbetskopia.
* **Kopiera** gör en ny plan av en plan i databasen, i samma eller en annan databas eller ett annat schema (exporterar
  till en tillfällig fil och importerar den).
* **Ta bort** tar bort en plan ur databasen, i en transaktion och bara om ingen har den utcheckad.

En befintlig plan skrivs aldrig över: importen och kopieringen avbryts om plan-id:t redan finns i schemat (se
``storage.create_postgis_plan_from_file``), och exporten om filen redan finns.
"""
from __future__ import annotations

import gc
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import checkout, geopackage, model, storage
from .storage import PostgisError, PostgisStorage, literal

# uppgifter i filens metadata som inte hör till planen i databasen: en utcheckad kopias och själva låset
_NOT_PLAN_META = (checkout.LOCK_KEY, *checkout.LOCAL_KEYS)
LOCKED_ADVICE = "Kasta utcheckningen eller bryt låset först."
LOCKED_MESSAGE = "Planen är utcheckad och kan inte tas bort. " + LOCKED_ADVICE


class TransferError(RuntimeError):
    """Planen gick inte att flytta. Meddelandet är avsett för användaren."""


@dataclass(frozen=True)
class Imported:
    plan: PostgisStorage
    counts: dict[str, int]  # tabell -> antal rader som lagts in

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def read_plan_file(path: Path) -> dict[str, str]:
    """Planens metadata ur en GeoPackage (schemaversion, koordinatsystem …). Kastar ``TransferError`` om filen inte är en
    översiktsplan från Rita Översiktsplan, är gjord med en nyare version, eller är äldre och behöver öppnas i pluginet
    först (då uppgraderas den)."""
    path = Path(path)
    meta = geopackage.read_meta(path) if path.is_file() else {}
    version = meta.get("schema_version", "")
    if not version:
        raise TransferError(f"{path.name} är ingen översiktsplan från Rita Översiktsplan.")
    if version.isdigit() and int(version) > int(model.SCHEMA_VERSION):
        raise TransferError(f"{path.name} är gjord med en nyare version av Rita Översiktsplan. Uppdatera pluginet först.")
    if version != str(model.SCHEMA_VERSION):
        raise TransferError(f"{path.name} är gjord med en äldre version av Rita Översiktsplan. Öppna den i pluginet först, "
                            "så uppgraderas den, och importera den sedan.")
    return meta


def _count(plan: PostgisStorage, table: storage.Table) -> int:
    rows = plan.sql(f'SELECT count(*) FROM {plan.table(table.name)} WHERE "plan" = {literal(plan.plan_id)}')
    return int(rows[0][0]) if rows else 0


def _discard(plan: PostgisStorage) -> None:
    """Tar bort allt som hör till planen (för att städa efter en misslyckad import). Fel här döljer inte det första felet."""
    for table in storage.tables():
        try:
            plan.sql(f'DELETE FROM {plan.table(table.name)} WHERE "plan" = {literal(plan.plan_id)}')
        except PostgisError:
            pass


def import_plan(path: Path, connection_name: str, schema: str, plan_id: str, connection=None) -> Imported:
    """Lägger planen i GeoPackage-filen ``path`` som planen ``plan_id`` i ``schema`` i databasen. Schemat skapas om det
    inte finns, och måste annars ha planens koordinatsystem. Kastar ``TransferError`` eller ``PostgisError`` (båda med ett
    meddelande för användaren); då är databasen som förut."""
    path = Path(path)
    read_plan_file(path)
    epsg = storage.GeoPackageStorage(path).epsg
    expected = {}
    for table in storage.tables():
        try:
            rows = storage.read_file_rows(path, table)
        except PostgisError as exc:
            raise TransferError(str(exc)) from exc
        expected[table.name] = len(rows) - (sum(1 for r in rows if r.get("key") in _NOT_PLAN_META)
                                            if table.name == model.META_TABLE else 0)
    plan = storage.create_postgis_plan_from_file(connection_name, schema, plan_id, path, epsg, connection,
                                                 skip_meta=_NOT_PLAN_META)
    try:
        for table in storage.tables():
            found = _count(plan, table)
            if found != expected[table.name]:
                raise TransferError(f"Importen blev inte komplett: tabellen {table.name} fick {found} av "
                                    f"{expected[table.name]} rader.")
    except Exception:
        _discard(plan)
        raise
    return Imported(plan, expected)


def export_plan(plan: PostgisStorage, path: Path) -> Path:
    """Sparar planen som en ny GeoPackage på ``path``. Kastar ``TransferError`` om filen redan finns eller något går fel
    (då lämnas ingen halv fil kvar). Är schemat i databasen från en äldre version uppgraderas det först, som när en plan
    öppnas."""
    path = Path(path)
    if path.exists():
        raise TransferError(f"{path.name} finns redan.")
    message = ""
    try:
        if not plan.read_meta():
            raise TransferError(f"Planen {plan.plan_id} finns inte i schemat {plan.schema}.")
        plan.upgrade()
        checkout.copy_to_geopackage(plan, path)
    except TransferError as exc:
        message = str(exc)
    except (checkout.CheckoutError, PostgisError) as exc:
        message = str(exc)
    except Exception as exc:  # noqa: BLE001 - användaren ska få ett meddelande, och ingen halv fil
        message = f"Kunde inte exportera planen: {exc}"
    if message:
        # Bara texten sparas: felet och de lager som hölls öppna mot filen släpps först, annars går filen inte att ta bort
        # på Windows.
        gc.collect()
        checkout.remove_copy(path)
        raise TransferError(message)
    geopackage.checkpoint(path)  # filen ska vara komplett även om bara .gpkg-filen kopieras vidare
    return path


def unique_export_paths(folder: Path, plans: list[PostgisStorage], suffix: str = ".gpkg") -> list[tuple[PostgisStorage, Path]]:
    """Filnamn i ``folder`` för planerna: planens id och ``suffix``. Heter två planer i olika scheman lika får de schemat
    som prefix."""
    plan_ids = [plan.plan_id for plan in plans]
    return [(plan, Path(folder) / ((plan.plan_id if plan_ids.count(plan.plan_id) == 1
                                    else f"{plan.schema}_{plan.plan_id}") + suffix)) for plan in plans]


def copy_plan(source: PostgisStorage, connection_name: str, schema: str, plan_id: str, connection=None) -> Imported:
    """Kopierar planen ``source`` till planen ``plan_id`` i ``schema`` i databasen ``connection_name`` (samma eller en annan
    databas, samma eller ett annat schema). Kopian görs via en tillfällig GeoPackage, så den visar planen som den ligger i
    databasen (inte ändringar som någon har utcheckade) och följer reglerna för ``import_plan``: en plan som redan finns
    skrivs aldrig över, och går något fel tas kopian bort igen."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        path = export_plan(source, Path(folder) / "kopia.gpkg")
        return import_plan(path, connection_name, schema, plan_id, connection)


def delete_sql(plan: PostgisStorage) -> str:
    """Ett enda SQL-block som i en transaktion tar bort planens rader i alla tabeller, om ingen har den utcheckad.
    Metadatatabellen låses medan det görs, så att ingen hinner checka ut planen mitt i (se ``checkout.acquire_lock``).
    Andra planers rader i samma tabeller rörs inte."""
    meta = plan.table(model.META_TABLE)
    plan_id = literal(plan.plan_id)
    parts = [f"LOCK TABLE {meta} IN EXCLUSIVE MODE;",
             f"IF EXISTS (SELECT 1 FROM {meta} WHERE \"plan\" = {plan_id} AND \"key\" = {literal(checkout.LOCK_KEY)}) THEN "
             f"RAISE EXCEPTION '{LOCKED_MESSAGE}'; END IF;"]
    parts += [f'DELETE FROM {plan.table(table.name)} WHERE "plan" = {plan_id};' for table in storage.tables()
              if table.name != model.META_TABLE]
    parts.append(f'DELETE FROM {meta} WHERE "plan" = {plan_id};')
    return storage.transaction_sql(parts)


def delete_plan(plan: PostgisStorage) -> None:
    """Tar bort planen ur databasen. Kastar ``TransferError`` om planen inte finns eller är utcheckad (av någon, även dig:
    kasta utcheckningen eller bryt låset först). Det går inte att ångra: spara en kopia först om planen kan behövas."""
    if not plan.read_meta():
        raise TransferError(f"Planen {plan.plan_id} finns inte i schemat {plan.schema}.")
    lock = checkout.read_lock(plan)
    if lock is not None:
        raise TransferError(f"Planen {plan.plan_id} är utcheckad av {lock.describe()}. {LOCKED_ADVICE}")
    try:
        plan.sql(delete_sql(plan))
    except PostgisError as exc:
        raise TransferError(str(exc)) from exc
    if storage.plan_exists(plan.connection, plan.schema, plan.plan_id):
        raise TransferError(f"Planen {plan.plan_id} finns kvar i databasen.")

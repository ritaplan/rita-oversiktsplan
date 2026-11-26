"""Var planen lagras: en GeoPackage-fil eller ett schema i en PostGIS-databas (som i Rita Detaljplan).

Båda har samma tabeller (se :mod:`model`). Resten av pluginet läser planen genom ``Storage`` och behöver inte veta
vilket det är. Ett PostGIS-schema delas av alla planer som lagts i det: varje tabell har en kolumn ``plan`` som
skiljer planernas rader åt, och varje QGIS-lager är tabellen filtrerad på just den planens identifierare. Även
uppslagstabellerna med ÖP-katalogens värden och metadatatabellen har kolumnen, så att varje plan behåller sin egen
katalogversion. Databasanslutningen är en av QGIS sparade PostgreSQL-anslutningar, så inloggningen sköts av QGIS.

Man ritar aldrig direkt mot databasen: en plan som öppnas därifrån är skrivskyddad och checkas ut till en lokal
GeoPackage för att redigeras (se :mod:`checkout`)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from qgis.core import Qgis, QgsCredentials, QgsDataSourceUri, QgsProviderRegistry, QgsVectorLayer

from . import geopackage, model

PROVIDER = "postgres"
SCHEMA_TABLE = "rita_oversiktsplan_schema"  # schemats egna nycklar (schemaversion), gemensamma för alla planer
KEY_PREFIX = "postgis:"
BATCH = 200  # rader per INSERT
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_TRANSLITERATE = str.maketrans({"å": "a", "ä": "a", "ö": "o", "é": "e", "ü": "u"})
_SQL_TYPES = {model.TEXT: "text", model.INT: "integer", model.REAL: "double precision", model.DATE: "date",
              model.DATETIME: "timestamp", model.BOOL: "boolean"}
_WKB = {"MultiPolygon": Qgis.WkbType.MultiPolygon, "MultiLineString": Qgis.WkbType.MultiLineString,
        "Point": Qgis.WkbType.Point}


MAX_IDENTIFIER = 63  # PostgreSQL kortar längre namn (i byte), så att olika tabeller kan få samma namn
# Boverkets tabellnamn som är för långa för PostgreSQL får ett kortare namn i databasen (i GeoPackage behålls mallens)
SHORT_NAMES = {"sarskiltvardefullabyggnadsverkallmannaplatserochbebyggelseomraden": "sarskiltvardefullkulturmiljo"}


def db_name(name: str) -> str:
    """Tabellens namn i databasen: samma som i GeoPackage, utom när det är längre än PostgreSQL tillåter. Då kortas
    det läsbart (``SHORT_NAMES``) eller, om det inte räcker, med en kort kontrollsumma på slutet."""
    if len(name.encode("utf-8")) <= MAX_IDENTIFIER:
        return name
    for long, short in SHORT_NAMES.items():
        name = name.replace(long, short)
    if len(name.encode("utf-8")) <= MAX_IDENTIFIER:
        return name
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    head = name.encode("utf-8")[:MAX_IDENTIFIER - 9].decode("utf-8", "ignore")
    return f"{head}_{digest}"


def index_name(table: str, column: str) -> str:
    """Ett kort, unikt indexnamn (index syns inte för användaren)."""
    return f"rop_{hashlib.sha1(table.encode('utf-8')).hexdigest()[:12]}_{column}"


def _short_error(text: str) -> str:
    """Databasens eget felmeddelande, utan den långa SQL-frågan som QGIS lägger före."""
    match = re.search(r"ERROR:\s*(.+?)(?:\n|$)", text)
    return match.group(1).strip() if match else text[:500]


class PostgisError(RuntimeError):
    """Något gick fel mot databasen. Meddelandet är avsett för användaren."""


def _execute(connection, sql: str):
    try:
        return connection.executeSql(sql)
    except PostgisError:
        raise
    except Exception as exc:  # QgsProviderConnectionException m.fl.
        raise PostgisError(f"Databasen svarade med ett fel: {_short_error(str(exc))}") from exc


# -- tabellerna i en plan (samma i filen och i databasen) ----------------------------------------------------------
class Table:
    """En tabell som flyttas mellan filen och databasen: namn, geometri och kolumner (namn, typ)."""

    def __init__(self, name: str, geometry: Optional[str], columns: list[tuple[str, str]]):
        self.name, self.geometry, self.columns = name, geometry, columns


def tables() -> list[Table]:
    """Planens geometri- och attributtabeller, uppslagstabellerna och metadatatabellen."""
    result = [Table(d.name, d.geometry, [(f.name, f.type) for f in d.fields]) for d in model.LAYERS]
    for lookup in model.LOOKUPS:
        result.append(Table(lookup.name, None, [(c, model.TEXT) for c in geopackage.lookup_columns(lookup)]))
    result.append(Table(model.META_TABLE, None, [("key", model.TEXT), ("value", model.TEXT)]))
    return result


# -- namn och SQL (rena funktioner) -----------------------------------------------------------------------------------
def identifier(text: str) -> str:
    """Gör fri text (till exempel planens titel) till ett giltigt schema- eller plan-id: gemener a–z, siffror och
    understreck, börjar med en bokstav."""
    name = re.sub(r"[^a-z0-9_]+", "_", (text or "").strip().lower().translate(_TRANSLITERATE)).strip("_")
    if name and not name[0].isalpha():
        name = "op_" + name
    return name[:63]


def is_valid_schema(name: str) -> bool:
    return bool(_IDENTIFIER_RE.match(name or "")) and name not in ("public", "information_schema") \
        and not name.startswith("pg_")


def is_valid_plan_id(name: str) -> bool:
    return bool(_IDENTIFIER_RE.match(name or ""))


_NOT_IN_FILE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def file_name(text: str) -> str:
    """Namn ur databasen eller QGIS (schema, plan-id, anslutning) som del av ett filnamn: tecken som byter mapp eller inte
    får stå i ett filnamn blir understreck. Pluginet skapar bara scheman och plan-id med a–z, siffror och understreck, men
    den som kan skriva i databasen kan lägga in andra."""
    return _NOT_IN_FILE_NAME.sub("_", str(text)).strip(" .") or "plan"


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def literal(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _wanted(existing: Optional[dict[str, bool]], table: str, index: Optional[str] = None) -> bool:
    """Om tabellen, eller dess index ``index``, ska skapas. ``existing`` är det som redan finns i schemat (namn -> om
    användaren får ändra det, se ``existing_relations``). Bara det som saknas skapas, eftersom PostgreSQL kräver att man
    äger tabellen för att skapa index (även med ``IF NOT EXISTS``). Ett index som saknas på en tabell som någon annan
    äger lämnas därför."""
    existing = existing or {}
    if index is None:
        return table not in existing
    return index not in existing and existing.get(table, True)


def ensure_schema_sql(schema: str, epsg: int = model.EPSG, create_schema: bool = True,
                      existing: Optional[dict[str, bool]] = None,
                      existing_columns: Optional[set[tuple[str, str]]] = None) -> list[str]:
    """SQL som skapar alla tabeller i schemat, om de inte redan finns. Det som redan finns (``existing`` och
    ``existing_columns``) rörs inte, så i ett schema som har allt blir listan tom och en ny plan kräver bara rätt att
    läsa och skriva. Med ``create_schema`` skapas också schemat. Det ska bara göras när schemat saknas:
    PostgreSQL kräver rätt att skapa scheman i databasen även för ``CREATE SCHEMA IF NOT EXISTS`` på ett schema som
    finns, och många kommuner ger användarna rätt bara i ett eget schema."""
    statements = [f"CREATE SCHEMA IF NOT EXISTS {quote(schema)}"] if create_schema else []
    if _wanted(existing, SCHEMA_TABLE):
        statements.append(f'CREATE TABLE IF NOT EXISTS {quote(schema)}.{quote(SCHEMA_TABLE)} '
                          '("key" text PRIMARY KEY, "value" text)')
    for table in tables():
        name = f"{quote(schema)}.{quote(db_name(table.name))}"
        columns = ['"fid" serial PRIMARY KEY', '"plan" text NOT NULL']
        if table.geometry:
            columns.append(f'"geom" geometry({table.geometry}, {int(epsg)})')
        columns += [f"{quote(column)} {_SQL_TYPES[kind]}" for column, kind in table.columns]
        stored = db_name(table.name)
        if _wanted(existing, stored):
            statements.append(f"CREATE TABLE IF NOT EXISTS {name} ({', '.join(columns)})")
        plan_index, geom_index = index_name(table.name, "plan"), index_name(table.name, "geom")
        if _wanted(existing, stored, plan_index):
            statements.append(f'CREATE INDEX IF NOT EXISTS {quote(plan_index)} ON {name} ("plan")')
        if table.geometry and _wanted(existing, stored, geom_index):
            statements.append(f'CREATE INDEX IF NOT EXISTS {quote(geom_index)} ON {name} USING gist ("geom")')
    key_index = index_name(model.META_TABLE, "plan_key")
    if _wanted(existing, db_name(model.META_TABLE), key_index):
        statements.append(f"CREATE UNIQUE INDEX IF NOT EXISTS {quote(key_index)} ON "
                          f'{quote(schema)}.{quote(model.META_TABLE)} ("plan", "key")')
    return statements + added_columns_sql(schema, existing_columns)


def added_columns_sql(schema: str, existing_columns: Optional[set[tuple[str, str]]] = None) -> list[str]:
    """Kolumner som kommit till i senare schemaversioner, för scheman som skapats tidigare (``CREATE TABLE IF NOT
    EXISTS`` lägger inte till kolumner i en befintlig tabell). Kolumner i ``existing_columns`` (tabell, kolumn) finns
    redan och tas inte med: bara den som äger tabellen får köra ``ALTER TABLE``, även när kolumnen finns."""
    statements = []
    for table, columns in model.ADDED_COLUMNS.items():
        kinds = {f.name: f.type for f in model.layer(table).fields}
        for column in columns:
            if existing_columns and (db_name(table), column) in existing_columns:
                continue
            statements.append(f"ALTER TABLE {quote(schema)}.{quote(db_name(table))} ADD COLUMN IF NOT EXISTS "
                              f"{quote(column)} {_SQL_TYPES[kinds[column]]}")
    return statements


UPGRADABLE = ("3", "4")  # schemaversioner i databasen som pluginet kan uppgradera


def migration_sql(schema: str, catalog=None) -> list[str]:
    """Flytten till Boverkets databasmodell 0.4 och katalogen som följer med pluginet, för alla planer i schemat (se
    :mod:`migration`), och sedan bort med kolumnerna som inte finns i 0.4. Förutsätter ett schema från version 3 eller
    4, där alla gamla kolumner finns och de nya just lagts till."""
    from . import migration, opkatalog
    catalog = catalog or opkatalog.bundled()

    def table(name: str) -> str:
        return f"{quote(schema)}.{quote(db_name(name))}"

    plans = f'SELECT DISTINCT "plan" FROM {table(model.OVERSIKTSPLAN.name)}'
    parts = migration.plan_reference_sql(table, True, lambda _: True)
    parts += migration.relations_sql(table, True, lambda _: True)
    parts += migration.decisions_sql(table, True)
    parts += migration.documents_sql(table)
    parts += migration.catalog_renames_sql(table, True, catalog)
    parts += migration.replace_lookups_sql(table, catalog, geopackage.lookup_columns, plans)
    for name, removed in model.REMOVED_COLUMNS.items():
        parts += [f"ALTER TABLE {table(name)} DROP COLUMN IF EXISTS {quote(column)}" for column in removed]
    parts.append(f"UPDATE {quote(schema)}.{quote(model.META_TABLE)} SET \"value\" = {literal(catalog.version)} "
                 "WHERE \"key\" = 'opkatalog_version'")
    parts.append(f"UPDATE {quote(schema)}.{quote(model.META_TABLE)} SET \"value\" = "
                 f"{literal(model.DATABASMODELL)} WHERE \"key\" = 'databasmodell'")
    return parts


def upgrade_schema_sql(schema: str, epsg: int) -> str:
    """Uppgraderar ett schema i databasen till pluginets schemaversion: saknade tabeller och kolumner läggs till,
    datan flyttas till databasmodell 0.4 och alla planer i schemat (de delar tabeller) får den nya versionen. En
    transaktion: går något fel är schemat som förut."""
    version = literal(model.SCHEMA_VERSION)
    parts = [statement + ";" for statement in ensure_schema_sql(schema, epsg, create_schema=False)]
    parts += [statement + ";" for statement in migration_sql(schema)]
    parts.append(f'UPDATE {quote(schema)}.{quote(model.META_TABLE)} SET "value" = {version} '
                 "WHERE \"key\" = 'schema_version';")
    parts.append(f'UPDATE {quote(schema)}.{quote(SCHEMA_TABLE)} SET "value" = {version} WHERE "key" = '
                 "'schema_version';")
    return transaction_sql(parts)


def sql_value(value, kind: str) -> str:
    """En cell som SQL-värde för kolumntypen ``kind`` (se :mod:`model`)."""
    import datetime

    from qgis.core import NULL
    from qgis.PyQt.QtCore import QDate, QDateTime
    if value is None or value == NULL or (hasattr(value, "isNull") and value.isNull()):
        return "NULL"
    if kind == model.BOOL:
        return "true" if value in (True, 1, "1", "true", "True") else "false"
    if kind == model.INT:
        return str(int(value))
    if kind == model.REAL:
        return repr(float(value))
    if isinstance(value, QDateTime):
        return literal(value.toString("yyyy-MM-dd HH:mm:ss")) if value.isValid() else "NULL"
    if isinstance(value, QDate):
        return literal(value.toString("yyyy-MM-dd")) if value.isValid() else "NULL"
    if isinstance(value, datetime.datetime):
        return literal(value.strftime("%Y-%m-%d %H:%M:%S"))
    if isinstance(value, datetime.date):
        return literal(value.isoformat())
    return literal(value)


def replace_rows_sql(schema: str, plan_id: str, table: Table, rows: list[dict], keep: str = "",
                     epsg: int = model.EPSG) -> list[str]:
    """Tar bort planens rader i tabellen och lägger in ``rows`` (``{kolumn: värde}``, geometrin som WKT i ``geom``).
    Andra planers rader rörs inte. ``fid`` sätts inte: databasen ger nya, eftersom den lokala kopians fid börjar om
    på 1 och skulle krocka med andra planers rader; kopplingarna i planen går via objektidentitet, inte fid. ``keep``
    är ett extra villkor för rader som ska vara kvar (låset i metadatatabellen)."""
    name = f"{quote(schema)}.{quote(db_name(table.name))}"
    plan = literal(plan_id)
    parts = [f"DELETE FROM {name} WHERE \"plan\" = {plan}{' AND NOT (' + keep + ')' if keep else ''};"]
    columns = ["plan"] + (["geom"] if table.geometry else []) + [column for column, _ in table.columns]
    column_list = ", ".join(quote(c) for c in columns)
    for start in range(0, len(rows), BATCH):
        values = []
        for row in rows[start:start + BATCH]:
            cells = [plan]
            if table.geometry:
                wkt = row.get("geom")
                geometry = f"ST_GeomFromText({literal(wkt)}, {int(epsg)})"
                if wkt is not None and table.geometry.startswith("Multi"):
                    geometry = f"ST_Multi({geometry})"
                cells.append("NULL" if wkt is None else geometry)
            cells += [sql_value(row.get(column), kind) for column, kind in table.columns]
            values.append("(" + ", ".join(cells) + ")")
        parts.append(f"INSERT INTO {name} ({column_list}) VALUES {', '.join(values)};")
    return parts


def transaction_sql(parts: list[str]) -> str:
    """Ett ``DO``-block: allt körs i en transaktion, och går något fel rullas allt tillbaka."""
    body = " ".join(parts)
    tag, n = "op", 0
    while f"${tag}$" in body:  # dollarcitatet får inte förekomma i innehållet
        n += 1
        tag = f"op{n}"
    return f"DO ${tag}$ BEGIN {body} END ${tag}$"


def read_file_rows(path: Path, table: Table) -> list[dict]:
    """Raderna i en tabell i en GeoPackage: ``{kolumn: värde}`` och geometrin som WKT i ``geom``."""
    layer = QgsVectorLayer(f"{path.as_posix()}|layername={table.name}", table.name, "ogr")
    if not layer.isValid():
        raise PostgisError(f"Kunde inte läsa tabellen {table.name} i {path.name}.")
    rows = []
    for feature in layer.getFeatures():
        row = {}
        if table.geometry:
            geometry = feature.geometry()
            row["geom"] = None if geometry is None or geometry.isNull() or geometry.isEmpty() else geometry.asWkt(6)
        for column, _ in table.columns:
            row[column] = feature.attribute(column) if layer.fields().indexOf(column) >= 0 else None
        rows.append(row)
    return rows


# -- lagringssätt ---------------------------------------------------------------------------------------------------
def layer_address(uri: QgsDataSourceUri) -> str:
    """Lagrets adress, utan lösenord. Adressen sparas i projektfilen, så ett lösenord får aldrig stå i den: det skulle ligga
    i klartext för alla som får filen. En inloggningskonfiguration (``authcfg``) står kvar som en hänvisning, men skrivs
    inte ut som användarnamn och lösenord. Ett lösenord som anslutningen har sparat lämnas i stället till QGIS
    inloggningscache (bara i minnet, bara medan QGIS är igång), som lagren frågar innan de ber om lösenordet, så att man
    inte behöver skriva det igen. Öppnas projektet i ett nytt QGIS frågar QGIS en gång efter lösenordet, som vanligt."""
    user, password = uri.username(), uri.password()
    uri.setPassword("")
    if password:
        # nyckeln är adressen utan lösenord, så som QGIS letar upp den när lagret ansluter
        QgsCredentials.instance().put(uri.connectionInfo(False), user, password)
    return uri.uri(False)


class Storage:
    """Där en plans tabeller finns."""
    kind = ""
    read_only = False

    @property
    def key(self) -> str:  # sparas på planens grupp i lagerpanelen
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError

    def read_meta(self) -> dict[str, str]:
        raise NotImplementedError

    def write_meta(self, values: dict[str, str]) -> None:
        raise NotImplementedError

    def read_defaults(self) -> dict[str, str]:
        meta = self.read_meta()
        return {field: meta.get(key, model.DEFAULT_VALUES[key]) for field, key in model.DEFAULT_KEYS.items()}

    def write_defaults(self, defaults: dict[str, str]) -> None:
        self.write_meta({model.DEFAULT_KEYS[field]: value for field, value in defaults.items()})

    def read_lookup(self, lookup: model.LookupDef) -> list[str]:
        raise NotImplementedError

    @property
    def epsg(self) -> int:
        """Planens koordinatsystem (SWEREF 99 TM om metadatan inte säger annat)."""
        value = self.read_meta().get("epsg", "")
        return int(value) if value.isdigit() else model.EPSG

    def read_lookup_values(self, lookup: model.LookupDef) -> dict[str, dict[str, str]]:
        raise NotImplementedError

    def layer_source(self, layer_def: model.LayerDef) -> tuple[str, str]:
        """(adress, dataleverantör) för ett lager."""
        raise NotImplementedError


class GeoPackageStorage(Storage):
    kind = "geopackage"

    def __init__(self, path):
        # alltid absolut: en relativ sökväg tolkas mot processens arbetsmapp, som QGIS och filväljare byter, och då
        # går lagren inte att öppna för redigering ("Kan inte återöppna datakälla i uppdateringsläge")
        self.path = Path(os.path.abspath(path))

    @property
    def key(self) -> str:
        return str(self.path)

    @property
    def name(self) -> str:
        return self.path.stem

    def describe(self) -> str:
        return self.path.name

    def read_meta(self) -> dict[str, str]:
        return geopackage.read_meta(self.path)

    def write_meta(self, values: dict[str, str]) -> None:
        geopackage.write_meta(self.path, values)

    def read_lookup(self, lookup: model.LookupDef) -> list[str]:
        return geopackage.read_lookup(self.path, lookup)

    def read_lookup_values(self, lookup: model.LookupDef) -> dict[str, dict[str, str]]:
        return geopackage.read_lookup_values(self.path, lookup)

    def layer_source(self, layer_def: model.LayerDef) -> tuple[str, str]:
        return f"{self.path.as_posix()}|layername={layer_def.name}", "ogr"

    def __eq__(self, other):
        return isinstance(other, GeoPackageStorage) and other.path == self.path

    def __hash__(self):
        return hash(self.path)


def postgis_connections() -> dict:
    """QGIS sparade PostgreSQL-anslutningar (namn → anslutning)."""
    metadata = QgsProviderRegistry.instance().providerMetadata(PROVIDER)
    return dict(metadata.connections()) if metadata is not None else {}


class PostgisStorage(Storage):
    kind = "postgis"
    read_only = True  # ändras bara genom utcheckning

    def __init__(self, connection_name: str, schema: str, plan_id: str, connection=None):
        self.connection_name, self.schema, self.plan_id = connection_name, schema, plan_id
        self._connection = connection

    @classmethod
    def from_key(cls, key: str) -> "PostgisStorage":
        connection, schema, plan_id = json.loads(key[len(KEY_PREFIX):])
        return cls(connection, schema, plan_id)

    @property
    def key(self) -> str:
        return KEY_PREFIX + json.dumps([self.connection_name, self.schema, self.plan_id], ensure_ascii=False)

    @property
    def name(self) -> str:
        return self.plan_id

    def describe(self) -> str:
        return f"{self.connection_name} · {self.schema} · {self.plan_id}"

    @property
    def connection(self):
        if self._connection is None:
            found = postgis_connections().get(self.connection_name)
            if found is None:
                raise PostgisError(f"Databasanslutningen {self.connection_name} finns inte bland QGIS sparade "
                                   "anslutningar.")
            self._connection = found
        return self._connection

    def sql(self, statement: str):
        return _execute(self.connection, statement)

    def table(self, name: str) -> str:
        return f"{quote(self.schema)}.{quote(db_name(name))}"

    def read_meta(self) -> dict[str, str]:
        try:
            rows = self.sql(f'SELECT "key", "value" FROM {self.table(model.META_TABLE)} '
                            f'WHERE "plan" = {literal(self.plan_id)}')
        except PostgisError:
            return {}
        return {row[0]: row[1] for row in rows}

    def write_meta(self, values: dict[str, str]) -> None:
        raise PostgisError("Planen ligger i databasen och är skrivskyddad. Checka ut den först.")

    def upgrade(self) -> bool:
        """Uppgraderar schemat om planen är skapad med en äldre version av pluginet. Returnerar True om något
        ändrades. Kräver rätt att ändra tabellerna i schemat."""
        if self.read_meta().get("schema_version") not in UPGRADABLE:
            return False
        try:
            self.sql(upgrade_schema_sql(self.schema, self.epsg))
        except PostgisError as exc:
            raise PostgisError(f"Schemat {self.schema} är skapat med en äldre version av pluginet och behöver "
                               "uppgraderas (till Boverkets databasmodell 0.4), men det gick inte. Den som har rätt att ändra "
                               f"tabellerna i schemat behöver öppna en plan i det en gång. {exc}") from exc
        return True

    def read_lookup(self, lookup: model.LookupDef) -> list[str]:
        rows = self.sql(f'SELECT {quote(lookup.value_column)} FROM {self.table(lookup.name)} '
                        f'WHERE "plan" = {literal(self.plan_id)} ORDER BY "fid"')
        return [row[0] for row in rows]

    def read_lookup_values(self, lookup: model.LookupDef) -> dict[str, dict[str, str]]:
        rows = self.sql(f'SELECT {quote(lookup.value_column)}, "vardereferens", "grupp_varde", "gruppreferens" '
                        f'FROM {self.table(lookup.name)} WHERE "plan" = {literal(self.plan_id)} ORDER BY "fid"')
        return {row[0]: {"varde": row[0], "vardereferens": row[1], "grupp": row[2], "gruppreferens": row[3]}
                for row in rows if row[0]}

    def layer_uri(self, layer_def: model.LayerDef) -> str:
        uri = QgsDataSourceUri(self.connection.uri())
        uri.setDataSource(self.schema, db_name(layer_def.name), "geom" if layer_def.geometry else "",
                          f'"plan" = {literal(self.plan_id)}', "fid")
        if layer_def.geometry:
            uri.setSrid(str(self.epsg))
            uri.setWkbType(_WKB[layer_def.geometry])
        return layer_address(uri)

    def layer_source(self, layer_def: model.LayerDef) -> tuple[str, str]:
        return self.layer_uri(layer_def), PROVIDER

    def __eq__(self, other):
        return isinstance(other, PostgisStorage) and (other.connection_name, other.schema, other.plan_id) == \
            (self.connection_name, self.schema, self.plan_id)

    def __hash__(self):
        return hash((self.connection_name, self.schema, self.plan_id))


def from_key(key: str) -> Storage:
    return PostgisStorage.from_key(key) if key.startswith(KEY_PREFIX) else GeoPackageStorage(key)


def as_storage(source) -> Storage:
    """Tar emot en sökväg (GeoPackage) eller ett ``Storage``."""
    return source if isinstance(source, Storage) else GeoPackageStorage(source)


# -- databasen --------------------------------------------------------------------------------------------------------
def list_schemas(connection) -> list[str]:
    return [row[0] for row in _execute(connection, "SELECT schema_name FROM information_schema.schemata")]


def schema_exists(connection, schema: str) -> bool:
    """Om schemat finns i databasen. Frågar systemkatalogen, som visar alla scheman: ``information_schema`` visar bara
    dem som användaren har någon rätt i."""
    return bool(_execute(connection, f"SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = {literal(schema)}"))


def existing_relations(connection, schema: str) -> dict[str, bool]:
    """Tabeller, index och sekvenser som redan finns i schemat: namn -> om användaren har ägarens rätt till dem (är
    ägaren, ingår i den ägande rollen eller är administratör)."""
    rows = _execute(connection, "SELECT c.relname, pg_has_role(c.relowner, 'USAGE') FROM pg_catalog.pg_class c "
                                "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                                f"WHERE n.nspname = {literal(schema)}")
    return {row[0]: str(row[1]).lower() in ("true", "t", "1") for row in rows}


def existing_columns(connection, schema: str) -> set[tuple[str, str]]:
    """(tabell, kolumn) för kolumnerna i schemats tabeller."""
    rows = _execute(connection, "SELECT c.relname, a.attname FROM pg_catalog.pg_attribute a "
                                "JOIN pg_catalog.pg_class c ON c.oid = a.attrelid "
                                "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                                f"WHERE n.nspname = {literal(schema)} AND a.attnum > 0 AND NOT a.attisdropped")
    return {(row[0], row[1]) for row in rows}


def may_create(connection, schema: Optional[str] = None) -> Optional[bool]:
    """Om användaren får skapa tabeller i ``schema`` (som ska finnas), eller utan schema: skapa nya scheman i
    databasen. None när databasen inte svarar på frågan (då försöker pluginet ändå och visar databasens fel)."""
    return _yes_or_no(connection, f"SELECT has_schema_privilege({literal(schema)}, 'CREATE')" if schema
                      else "SELECT has_database_privilege(current_database(), 'CREATE')")


def may_write(connection, schema: str) -> Optional[bool]:
    """Om användaren får läsa och lägga till rader i ett schema som pluginet redan har tabeller i (prövat på
    metadatatabellen och dess sekvens, som ger nya rader sitt nummer). None när databasen inte svarar på frågan."""
    meta = db_name(model.META_TABLE)
    return _yes_or_no(connection,
                      "SELECT has_schema_privilege(n.oid, 'USAGE') AND has_table_privilege(c.oid, 'SELECT') AND "
                      "has_table_privilege(c.oid, 'INSERT') AND has_sequence_privilege(s.oid, 'USAGE, UPDATE') "
                      "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                      "JOIN pg_catalog.pg_class s ON s.relnamespace = n.oid "
                      f"AND s.relname = {literal(meta + '_fid_seq')} "
                      f"WHERE n.nspname = {literal(schema)} AND c.relname = {literal(meta)}")


def _yes_or_no(connection, sql: str) -> Optional[bool]:
    """Svaret på en ja/nej-fråga till databasen, eller None om den inte kan svara."""
    try:
        rows = _execute(connection, sql)
    except PostgisError:
        return None
    if not rows or rows[0][0] is None:
        return None
    return str(rows[0][0]).lower() in ("true", "t", "1")


def list_plugin_schemas(connection) -> list[str]:
    """Scheman som pluginet har skapat (har tabellen med schemats nycklar)."""
    rows = _execute(connection, "SELECT table_schema FROM information_schema.tables WHERE table_name = "
                                f"{literal(SCHEMA_TABLE)} ORDER BY table_schema")
    return [row[0] for row in rows]


def list_plans(connection, schema: str) -> list[tuple[str, str]]:
    """(plan-id, titel) för planerna i ett schema."""
    rows = _execute(connection, f'SELECT DISTINCT m."plan", p."planens_titel" FROM {quote(schema)}.'
                                f'{quote(model.META_TABLE)} m LEFT JOIN {quote(schema)}.'
                                f'{quote(model.OVERSIKTSPLAN.name)} p ON p."plan" = m."plan" ORDER BY m."plan"')
    return [(row[0], row[1] or "") for row in rows]


def plan_exists(connection, schema: str, plan_id: str) -> bool:
    return bool(_execute(connection, f'SELECT 1 FROM {quote(schema)}.{quote(model.META_TABLE)} '
                                     f'WHERE "plan" = {literal(plan_id)} LIMIT 1'))


def schema_epsg(connection, schema: str) -> Optional[int]:
    """Koordinatsystemet som ett befintligt schema har (gemensamt för alla planer i det), eller None."""
    try:
        rows = _execute(connection, f'SELECT "value" FROM {quote(schema)}.{quote(SCHEMA_TABLE)} WHERE "key" = '
                                    "'epsg'")
    except PostgisError:
        return None
    return int(rows[0][0]) if rows and str(rows[0][0]).isdigit() else None


def _needs_owner(schema: str) -> str:
    return (f"Schemat {schema} saknar något som pluginet behöver, och det gick inte att lägga till. Den som äger "
            "tabellerna i schemat (eller en databasadministratör) behöver skapa en plan i det en gång.")


def create_postgis_plan(connection_name: str, schema: str, plan_id: str, plan: geopackage.NewPlan,
                        connection=None) -> PostgisStorage:
    """Lägger in en ny plan i ett schema i databasen. Schemat och tabellerna skapas om de inte finns. Planen byggs
    först som en tillfällig GeoPackage (med ÖP-katalogen och planens uppgifter) och skrivs sedan till databasen i en
    enda transaktion. Avbryter utan ändringar om plan-id:t redan finns i schemat."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        path = geopackage.create_geopackage(Path(folder) / "ny.gpkg", plan)
        return create_postgis_plan_from_file(connection_name, schema, plan_id, path, plan.epsg, connection)


def create_postgis_plan_from_file(connection_name: str, schema: str, plan_id: str, path: Path, epsg: int,
                                  connection=None, skip_meta=()) -> PostgisStorage:
    """Lägger in planen i GeoPackage-filen ``path`` (koordinatsystem ``epsg``) som en ny plan i ett schema i databasen.
    Schemat och tabellerna skapas om de inte finns; finns schemat måste det ha samma koordinatsystem. Allt skrivs i en
    enda transaktion. Avbryter utan ändringar om plan-id:t redan finns i schemat. Metadatanycklarna i ``skip_meta`` (t.ex.
    en utcheckad kopias) tas inte med."""
    if not is_valid_schema(schema):
        raise PostgisError("Schemanamnet får bara innehålla gemener a–z, siffror och understreck och måste börja med "
                           "en bokstav.")
    if not is_valid_plan_id(plan_id):
        raise PostgisError("Planens id får bara innehålla gemener a–z, siffror och understreck och måste börja med "
                           "en bokstav.")
    target = PostgisStorage(connection_name, schema, plan_id, connection)
    try:
        target.sql("SELECT postgis_version()")
    except PostgisError as exc:
        raise PostgisError("Databasen saknar PostGIS (eller anslutningen fungerar inte). Tillägget aktiveras med "
                           f"CREATE EXTENSION postgis. {exc}") from exc
    existed = schema in list_plugin_schemas(target.connection)
    if existed:  # alla planer i ett schema delar tabeller och därmed koordinatsystem
        existing = schema_epsg(target.connection, schema) or model.EPSG
        if existing != epsg:
            raise PostgisError(f"Schemat {schema} har koordinatsystem EPSG:{existing}. Alla planer i samma schema "
                               f"delar koordinatsystem: välj EPSG:{existing}, eller ett annat schema.")
    schema_was_there = existed or schema_exists(target.connection, schema)  # då rör vi aldrig schemat i övrigt
    if existed and plan_exists(target.connection, schema, plan_id):
        raise PostgisError(f"Det finns redan en plan med id {plan_id} i schemat {schema}.")
    relations = existing_relations(target.connection, schema) if schema_was_there else {}
    if db_name(model.META_TABLE) in relations and may_write(target.connection, schema) is False:
        raise PostgisError(f"Du har inte rätt att lägga till planer i schemat {schema}. Be den som sköter databasen om "
                           "SELECT, INSERT, UPDATE och DELETE på tabellerna och USAGE på sekvenserna.")
    columns = existing_columns(target.connection, schema) if relations else None
    statements = ensure_schema_sql(schema, epsg, create_schema=not schema_was_there, existing=relations,
                                   existing_columns=columns)
    if schema_was_there and statements and may_create(target.connection, schema) is False:
        if db_name(model.META_TABLE) in relations:  # schemat har redan planer: något saknas i det
            raise PostgisError(_needs_owner(schema))
        raise PostgisError(f"Du har inte rätt att skapa tabeller i schemat {schema}. Välj ett schema där du har den "
                           "rätten, eller be den som sköter databasen om den (CREATE på schemat).")
    if not schema_was_there and may_create(target.connection) is False:
        raise PostgisError(f"Schemat {schema} finns inte, och du får inte skapa nya scheman i databasen. Välj ett "
                           "schema som redan finns och som du har rätt att skapa tabeller i, eller be den som sköter "
                           "databasen om ett.")
    try:
        try:
            for statement in statements:
                target.sql(statement)
        except PostgisError as exc:
            if not schema_was_there:
                raise
            raise PostgisError(f"{_needs_owner(schema)} {exc}") from exc
        if not existed:
            target.sql(f"INSERT INTO {target.table(SCHEMA_TABLE)} (\"key\", \"value\") VALUES "
                       f"('schema_version', {literal(model.SCHEMA_VERSION)}), ('epsg', {literal(epsg)}) "
                       "ON CONFLICT (\"key\") DO NOTHING")
        parts = []
        for table in tables():
            rows = read_file_rows(path, table)
            if table.name == model.META_TABLE:
                rows = [row for row in rows if row.get("key") not in skip_meta]
            parts += replace_rows_sql(schema, plan_id, table, rows, epsg=epsg)
        target.sql(transaction_sql(parts))
    except PostgisError:
        if not schema_was_there:  # ett halvskapat schema som vi själva skapade är värre än inget: ta bort det
            try:
                target.sql(f"DROP SCHEMA IF EXISTS {quote(schema)} CASCADE")
            except PostgisError:
                pass
        raise
    return target

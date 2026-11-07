"""Flytten av en plans data till Boverkets databasmodell 0.4 (pluginets schema 5) och uppgraderingen av planens
ÖP-katalog. Ren Python: funktionerna ger SQL, som :func:`geopackage.upgrade` kör i en GeoPackage och
:func:`storage.upgrade_schema_sql` i en PostGIS-databas (där alla planer i schemat delar tabeller och skiljs åt med
kolumnen ``plan``).

Vad som flyttas (Boverkets ändringsförteckning 0.3 till 0.4):
  * allt innehåll får ``oversiktsplan`` = planens objektidentitet;
  * *berör annat innehåll*: varje rad i ``innehall_op_beror_annat_innehall`` pekade på innehållet via
    ``beror_annat_innehall_id`` och på det berörda innehållet via ``beror_annat_innehal_uuid``; nu står båda
    objektidentiteterna i raden (``objektidentitet`` och ``beror_objektidentitet``);
  * beslut: ``beslutande_organisation`` blir ``beslutande_organisation_namn``, och datumen (fattat, överklagat, laga
    kraft) blir rader i ``beslut_op_handelse``;
  * dokumentreferenser: ``producentens_identitet`` får samma värde som ``identitet``, som Boverket anvisar.

Katalogen uppgraderas på värdenas id (``vardereferens``), som är oförändrade när ett värde byter namn (Fiske blir
Yrkesfiske i 2.3): ett värde i planen som i planens egen uppslagstabell har ett id som finns i den nya katalogen får
det nya namnet, och uppslagstabellerna fylls med den nya katalogens värden. Ett värde vars id saknas i den nya
katalogen lämnas som det är (exporten säger då till om det)."""
from __future__ import annotations

from typing import Callable, Optional

from . import model

Ref = Callable[[str], str]  # tabellnamn → SQL för tabellen (med schema i en databas)


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def literal(value) -> str:
    return "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"


def _same_plan(per_plan: bool, a: str, b: str) -> str:
    """Villkoret att två rader hör till samma plan (bara i en databas, där planerna delar tabeller)."""
    return f' AND {a}."plan" = {b}."plan"' if per_plan else ""


def plan_reference_sql(table: Ref, per_plan: bool, has_plan_column: Callable[[str], bool]) -> list[str]:
    """Allt innehåll pekar på planen (``oversiktsplan``)."""
    parts = []
    plan = table(model.OVERSIKTSPLAN.name)
    for layer_def in model.CONTENT_LAYERS:
        if not has_plan_column(layer_def.name):
            continue
        parts.append(f"UPDATE {table(layer_def.name)} AS u SET {quote(model.PLAN_FIELD)} = "
                     f'(SELECT o."objektidentitet" FROM {plan} AS o WHERE 1 = 1{_same_plan(per_plan, "o", "u")} '
                     f"LIMIT 1) WHERE u.{quote(model.PLAN_FIELD)} IS NULL")
    return parts


RELATIONS = "innehall_op_beror_annat_innehall"


def relations_sql(table: Ref, per_plan: bool, has_old_link: Callable[[str], bool]) -> list[str]:
    """*Berör annat innehåll*: innehållets objektidentitet i stället för länk-id:t. Rader som inte går att flytta
    (länken pekar inte på något innehåll, eller innehållet berör sig självt) tas bort."""
    sources = []
    for layer_def in model.CONTENT_LAYERS:
        if has_old_link(layer_def.name):
            plan_column = '"plan", ' if per_plan else ""
            sources.append(f'SELECT {plan_column}"objektidentitet", "beror_annat_innehall_id" '
                           f"FROM {table(layer_def.name)}")
    name = table(RELATIONS)
    parts = [f'UPDATE {name} AS u SET "beror_objektidentitet" = u."beror_annat_innehal_uuid" '
             'WHERE u."beror_objektidentitet" IS NULL']
    if sources:
        union = " UNION ALL ".join(sources)
        parts.append(f'UPDATE {name} AS u SET "objektidentitet" = (SELECT c."objektidentitet" FROM ({union}) AS c '
                     f'WHERE c."beror_annat_innehall_id" = u."beror_annat_innehall_id"{_same_plan(per_plan, "c", "u")} '
                     'LIMIT 1) WHERE u."objektidentitet" IS NULL')
    parts.append(f'DELETE FROM {name} WHERE "objektidentitet" IS NULL OR "beror_objektidentitet" IS NULL '
                 'OR "objektidentitet" = "beror_objektidentitet"')
    return parts


def decisions_sql(table: Ref, per_plan: bool) -> list[str]:
    """Beslutens organisation och datum (ur kolumnerna i schema 3 och 4)."""
    decisions = table(model.BESLUT.name)
    events = table(model.BESLUT_HANDELSE.name)
    plan_column = '"plan", ' if per_plan else ""
    parts = [f'UPDATE {decisions} SET "beslutande_organisation_namn" = "beslutande_organisation" '
             'WHERE "beslutande_organisation_namn" IS NULL']
    for column, kind in model.OLD_DECISION_DATES:
        parts.append(f'INSERT INTO {events} ({plan_column}"beslut_op_id", "handelsetyp", "datum") '
                     f'SELECT {plan_column}d."objektidentitet", {literal(kind)}, d.{quote(column)} '
                     f"FROM {decisions} AS d WHERE d.{quote(column)} IS NOT NULL AND NOT EXISTS "
                     f'(SELECT 1 FROM {events} AS e WHERE e."beslut_op_id" = d."objektidentitet" '
                     f'AND e."handelsetyp" = {literal(kind)})')  # inte två gånger, om uppgraderingen körs om
    return parts


def documents_sql(table: Ref) -> list[str]:
    return [f'UPDATE {table("dokumentreferens_op")} SET "producentens_identitet" = "identitet" '
            'WHERE "producentens_identitet" IS NULL AND "identitet" IS NOT NULL']


# -- katalogen --------------------------------------------------------------------------------------------------------
def _ref(expression: str) -> str:
    """Ett värdes id utan klamrar och med gemener (Boverkets mall 0.4 skriver {VERSALER}, katalogens API gemener)."""
    return f"lower(replace(replace({expression}, '{{', ''), '}}', ''))"


def lookup_users() -> dict[str, list[tuple[str, str]]]:
    """Uppslagstabell → (tabell, kolumn) som har värden ur den."""
    found: dict[str, list[tuple[str, str]]] = {}
    for layer_def in model.LAYERS:
        for field in layer_def.fields:
            if field.lookup:
                found.setdefault(field.lookup, []).append((layer_def.name, field.name))
    return found


def catalog_renames_sql(table: Ref, per_plan: bool, catalog) -> list[str]:
    """Ger planens värden den nya katalogens namn, där värdets id är detsamma (``catalog``: opkatalog.Catalog)."""
    parts = []
    users = lookup_users()
    for lookup in model.LOOKUPS:
        values = catalog.values(lookup.category, lookup.group, lookup.itself)
        lookup_table = table(lookup.name)
        for target, column in users.get(lookup.name, []):
            for value in values:
                parts.append(
                    f"UPDATE {table(target)} AS u SET {quote(column)} = {literal(value.varde)} "
                    f"WHERE u.{quote(column)} <> {literal(value.varde)} AND u.{quote(column)} IN "
                    f"(SELECT l.{quote(lookup.value_column)} FROM {lookup_table} AS l "
                    f'WHERE {_ref("l.vardereferens")} = {literal(value.vardereferens.lower())}'
                    f'{_same_plan(per_plan, "l", "u")})')
    return parts


def lookup_rows(lookup: model.LookupDef, catalog) -> list[tuple[str, ...]]:
    """Uppslagstabellens rader ur katalogen: (värde, vardereferens, grupp, gruppreferens, katalogversion)."""
    return [(v.varde, v.vardereferens, v.grupp, v.gruppreferens, catalog.version)
            for v in catalog.values(lookup.category, lookup.group, lookup.itself)]


def replace_lookups_sql(table: Ref, catalog, columns: Callable[[model.LookupDef], tuple[str, ...]],
                        plans_sql: Optional[str] = None) -> list[str]:
    """Fyller uppslagstabellerna med katalogens värden. I en databas (``plans_sql`` = en fråga som ger planernas id)
    får varje plan i schemat sina egna rader."""
    parts = []
    for lookup in model.LOOKUPS:
        name = table(lookup.name)
        column_list = ", ".join(quote(c) for c in columns(lookup))
        parts.append(f"DELETE FROM {name}")
        for row in lookup_rows(lookup, catalog):
            values = ", ".join(literal(v) for v in row)
            if plans_sql:
                parts.append(f'INSERT INTO {name} ("plan", {column_list}) SELECT p."plan", {values} '
                             f"FROM ({plans_sql}) AS p")
            else:
                parts.append(f"INSERT INTO {name} ({column_list}) VALUES ({values})")
    return parts

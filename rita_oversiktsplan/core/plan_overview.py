"""Översikt över planerna i en PostGIS-databas: en rad per översiktsplan med de uppgifter man vill se innan man öppnar den
(som i Rita Detaljplan).

Allt hämtas med några få frågor per schema (inte en per plan), så överblicken går snabbt även över nätet. Planens
geometri läses aldrig här. Saknas en tabell eller kolumn (ett äldre schema) lämnas fälten tomma i stället för att
överblicken misslyckas: bara listan över planer måste gå att läsa.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import checkout, model, storage
from .storage import PostgisError, literal, quote


@dataclass(frozen=True)
class PlanRow:
    connection: str
    schema: str
    plan_id: str
    titel: str = ""
    planhandelse: str = ""
    planhandelse_datum: str = ""
    paborjad: str = ""
    diarienummer: str = ""
    beslut_fattat: str = ""
    laga_kraft: str = ""
    lock: Optional[checkout.Lock] = None

    @property
    def locked(self) -> bool:
        return self.lock is not None

    @property
    def locked_by_me(self) -> bool:
        """Utcheckad av den här användaren på den här datorn (då kan utcheckningen tas upp igen)."""
        return self.lock is not None and checkout.is_own_lock(self.lock)


def _text(value) -> str:
    """Ett databasvärde som visningstext. NULL och None blir tom text, datum blir ÅÅÅÅ-MM-DD."""
    if value is None:
        return ""
    to_string = getattr(value, "toString", None)
    if callable(to_string):  # QDate / QDateTime
        if getattr(value, "isNull", lambda: False)():
            return ""
        return str(to_string("yyyy-MM-dd"))
    text = str(value).strip()
    if text in ("NULL", "None"):
        return ""
    return text[:10] if len(text) > 10 and text[4:5] == "-" and text[7:8] == "-" and text[:4].isdigit() \
        and text[10] in " T" else text


def _query(connection, sql: str) -> list:
    """En fråga där ett fel inte får stoppa överblicken (saknad tabell eller kolumn i ett äldre schema)."""
    try:
        return storage._execute(connection, sql)
    except PostgisError:
        return []


def _table(schema: str, name: str) -> str:
    return f"{quote(schema)}.{quote(storage.db_name(name))}"


def _locks(connection, schema: str) -> dict[str, checkout.Lock]:
    rows = _query(connection, f'SELECT "plan", "value" FROM {_table(schema, model.META_TABLE)} '
                              f'WHERE "key" = {literal(checkout.LOCK_KEY)}')
    locks = {}
    for row in rows:
        lock = checkout.Lock.from_json(_text(row[1]))
        if lock is not None:
            locks[_text(row[0])] = lock
    return locks


def _plan_fields(connection, schema: str) -> dict[str, dict[str, str]]:
    rows = _query(connection, 'SELECT "plan", "planens_titel", "planhandelse_varde", "planhandelse_datum", '
                              f'"datum_paborjat", "beslut" FROM {_table(schema, model.OVERSIKTSPLAN.name)}')
    keys = ("titel", "planhandelse", "planhandelse_datum", "paborjad", "beslut")
    return {_text(row[0]): dict(zip(keys, (_text(v) for v in row[1:]))) for row in rows}


def _decisions(connection, schema: str) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Beslutsraderna, dels per beslutets id (det planen pekar på) och dels per plan (den med senast fattade beslut, om
    planen inte pekar på något). Datumen står i beslut_op_handelse (databasmodell 0.4)."""
    rows = _query(connection, 'SELECT "plan", "objektidentitet", "diarienummer" '
                              f'FROM {_table(schema, model.BESLUT.name)} ORDER BY "plan"')
    events: dict[tuple[str, str], str] = {}  # (beslut, händelsetyp) → datum, ur beslut_op_handelse
    for row in _query(connection, 'SELECT "beslut_op_id", "handelsetyp", "datum" '
                                  f'FROM {_table(schema, model.BESLUT_HANDELSE.name)}'):
        events[(_text(row[0]), _text(row[1]))] = _text(row[2])
    by_id: dict[str, dict[str, str]] = {}
    by_plan: dict[str, dict[str, str]] = {}
    for row in rows:
        identity = _text(row[1])
        values = {"diarienummer": _text(row[2]), "beslut_fattat": events.get((identity, model.FATTAT), ""),
                  "laga_kraft": events.get((identity, model.LAGA_KRAFT), "")}
        by_id[_text(row[1])] = values
        plan = _text(row[0])
        if plan not in by_plan or values["beslut_fattat"] >= by_plan[plan]["beslut_fattat"]:
            by_plan[plan] = values
    return by_id, by_plan


def list_plans(connection_name: str, connection, schema: str) -> list[PlanRow]:
    """Alla planer i ett schema, med planens uppgifter och ev. utcheckning. Kastar ``PostgisError`` om det inte går att ens
    lista planerna."""
    listed = storage.list_plans(connection, schema)  # (plan-id, titel)
    locks = _locks(connection, schema)
    fields = _plan_fields(connection, schema)
    decisions_by_id, decisions_by_plan = _decisions(connection, schema)
    rows = []
    for plan_id, title in listed:
        own = dict(fields.get(plan_id, {}))
        decision = decisions_by_id.get(own.pop("beslut", ""), decisions_by_plan.get(plan_id, {}))
        own.setdefault("titel", "")
        own["titel"] = own["titel"] or title
        rows.append(PlanRow(connection_name, schema, plan_id, lock=locks.get(plan_id), **own, **decision))
    return rows

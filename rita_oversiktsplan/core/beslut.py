"""Beslutens händelser (fattat, överklagat, laga kraft) i Boverkets tabell ``beslut_op_handelse``: en rad per beslut och
händelse, med datum (databasmodell 0.4; i pluginets schema 3 och 4 var de tre kolumner i ``beslut_op``). Ett beslut
har högst en rad per händelsetyp här, även om tabellen tillåter flera."""
from __future__ import annotations

import datetime
from typing import Optional

from qgis.core import QgsGeometry, QgsVectorLayer, QgsVectorLayerUtils
from qgis.PyQt.QtCore import QDate

from . import model
from .content import plain
from .project import layer_in_group

Dates = dict[str, Optional[datetime.date]]  # händelsetyp → datum


def _date(value) -> Optional[datetime.date]:
    value = plain(value)
    if value is None:
        return None
    if hasattr(value, "toPyDate"):
        return value.toPyDate() if value.isValid() else None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def table(group) -> QgsVectorLayer:
    layer = layer_in_group(group, model.BESLUT_HANDELSE.name)
    if layer is None:
        raise ValueError(f"Tabellen {model.BESLUT_HANDELSE.alias} saknas i planen. Öppna planen på nytt.")
    return layer


def dates_from_rows(rows) -> dict[str, Dates]:
    """Beslutets objektidentitet → händelsetyp → datum, ur raderna i ``beslut_op_handelse``."""
    found: dict[str, Dates] = {}
    for row in rows:
        decision, kind, when = plain(row["beslut_op_id"]), plain(row["handelsetyp"]), _date(row["datum"])
        if decision and kind and when:
            found.setdefault(str(decision), {})[str(kind)] = when
    return found


def read(group, decision: str) -> Dates:
    """Händelserna för ett beslut."""
    return dates_from_rows(table(group).getFeatures()).get(decision, {})


def write(group, decision: str, dates: Dates) -> None:
    """Ersätter beslutets händelser med ``dates`` (tomma datum tas bort). Sparas direkt om tabellen inte
    redigerades, annars i redigeringsbufferten."""
    layer = table(group)
    started = not layer.isEditable() and layer.startEditing()
    layer.deleteFeatures([f.id() for f in layer.getFeatures() if str(plain(f["beslut_op_id"]) or "") == decision])
    for kind in model.BESLUT_HANDELSER:
        when = dates.get(kind)
        if when is None:
            continue
        values = {"beslut_op_id": decision, "handelsetyp": kind, "datum": QDate(when.year, when.month, when.day)}
        layer.addFeature(QgsVectorLayerUtils.createFeature(
            layer, QgsGeometry(), {layer.fields().indexOf(k): v for k, v in values.items()}))
    if started and not layer.commitChanges():
        raise ValueError("Kunde inte spara beslutets datum: " + "; ".join(layer.commitErrors()))

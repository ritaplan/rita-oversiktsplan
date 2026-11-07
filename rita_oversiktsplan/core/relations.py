"""Berör annat innehåll: att ett innehåll hänger ihop med ett annat (``berorAnnatInnehall`` i Lantmäteriets
*innehallOP*, en lista med objektidentiteter), till exempel en klimatrisk som berör ett område för bostadsbebyggelse.

I Boverkets databasmodell 0.4 är det en kopplingstabell, ``innehall_op_beror_annat_innehall``, med en rad per
koppling: innehållet som berör (``objektidentitet``) och innehållet som berörs (``beror_objektidentitet``). Samma
koppling finns bara en gång, och ett innehåll kan inte beröra sig självt. Ändringarna läggs i redigeringsbufferten, som
när man ritar."""
from __future__ import annotations

from qgis.core import QgsGeometry, QgsVectorLayer, QgsVectorLayerUtils

from .content import plain
from .project import layer_in_group

TABLE = "innehall_op_beror_annat_innehall"
SOURCE = "objektidentitet"
TARGET = "beror_objektidentitet"


def _table(group) -> QgsVectorLayer:
    layer = layer_in_group(group, TABLE)
    if layer is None:
        raise ValueError(f"Tabellen {TABLE} saknas i planen. Öppna planen på nytt.")
    return layer


def links(group) -> dict[str, set[str]]:
    """Objektidentitet → objektidentiteterna det berör."""
    found: dict[str, set[str]] = {}
    for row in _table(group).getFeatures():
        source, target = plain(row[SOURCE]), plain(row[TARGET])
        if source and target:
            found.setdefault(str(source), set()).add(str(target))
    return found


def related(group, layer: QgsVectorLayer, fid: int) -> set[str]:
    """Objektidentiteterna som ett innehåll berör."""
    identity = plain(layer.getFeature(fid)["objektidentitet"])
    return links(group).get(str(identity), set()) if identity else set()


def add(table: QgsVectorLayer, source: str, target: str) -> None:
    """Lägger till kopplingen i redigeringsbufferten (tabellen redigeras redan)."""
    table.addFeature(QgsVectorLayerUtils.createFeature(
        table, QgsGeometry(), {table.fields().indexOf(SOURCE): source, table.fields().indexOf(TARGET): target}))


def toggle(group, layer: QgsVectorLayer, fid: int, target: str) -> bool:
    """Lägger till kopplingen till ``target`` (en objektidentitet), eller tar bort den om den finns. Returnerar True
    om innehållet nu berör ``target``."""
    source = str(plain(layer.getFeature(fid)["objektidentitet"]) or "")
    if not source:
        raise ValueError("Innehållet saknar objektidentitet.")
    if source == target:
        raise ValueError("Ett innehåll kan inte beröra sig självt.")
    table = _table(group)
    if not table.isEditable():
        table.startEditing()
    existing = [row.id() for row in table.getFeatures()
                if str(plain(row[SOURCE])) == source and str(plain(row[TARGET])) == target]
    if existing:
        table.deleteFeatures(existing)
        return False
    add(table, source, target)
    return True

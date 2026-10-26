"""Kommunens yta som plangeometri: hämtas när en ny översiktsplan skapas (valfritt i dialogen Ny översiktsplan; den
som vill rita en mindre plangeometri själv kryssar ur rutan).

Källa: SCB:s öppna geodata, **DeSO 2025** (demografiska statistikområden) i SCB:s WFS
(``geodata.scb.se/geoserver/stat/wfs``, skiktet ``stat:DeSO_2025``, fältet ``kommunkod``). DeSO täcker hela landet
och följer kommungränserna, så kommunens yta är alla dess DeSO sammanslagna. Provat 2026-10-24: Lidköping 1 379 km²,
Munkfors 148 km², Stockholm 216 km², samma som Lantmäteriets kommunytor.

Tidigare (0.1.5–0.1.7) hämtades Lantmäteriets kommunytor ur länsstyrelsernas nationella visningstjänst
(``ext-geodata-nationella-visning.lansstyrelsen.se``), men den svarar sedan 2026-10-24 med 403 (förbjuden) för alla
frågor utifrån, även för en vanlig webbläsare.

Ytan skrivs in i planens GeoPackage när planen skapas (:func:`geopackage.create_geopackage`), så att det fungerar både
för en plan i en fil och i en databas. Sammanslagning och omräkning till planens koordinatsystem görs med GDAL (följer
med QGIS); modulen behöver inte QGIS utom :func:`plan_area`.
"""
from __future__ import annotations

import json
import urllib.parse
from typing import Callable, Optional

from .riksintressen import FetchError

WFS = "https://geodata.scb.se/geoserver/stat/wfs"
LAYER = "stat:DeSO_2025"
SOURCE_EPSG = 3006  # frågan görs alltid i SWEREF 99 TM (känd axelordning), och räknas sedan om
PLAN_AREA = "innehall_op_plangeometri"


def municipality_filter(kommunkod: str) -> str:
    if not (kommunkod.isdigit() and len(kommunkod) == 4):
        raise ValueError(f"Kommunkoden {kommunkod!r} har inte fyra siffror.")
    return f"kommunkod='{kommunkod}'"


def query_url(kommunkod: str) -> str:
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": LAYER,
              "outputFormat": "application/json", "srsName": f"EPSG:{SOURCE_EPSG}",
              "cql_filter": municipality_filter(kommunkod)}
    return f"{WFS}?" + urllib.parse.urlencode(params)


def merge(shapes: list[dict], epsg: int) -> dict:
    """DeSO-ytorna (GeoJSON i SWEREF 99 TM) sammanslagna till en yta i planens koordinatsystem."""
    from osgeo import ogr, osr
    collection = ogr.Geometry(ogr.wkbMultiPolygon)
    for shape in shapes:
        geometry = ogr.CreateGeometryFromJson(json.dumps(shape))
        for part in (geometry,) if geometry.GetGeometryType() == ogr.wkbPolygon else \
                (geometry.GetGeometryRef(i) for i in range(geometry.GetGeometryCount())):
            collection.AddGeometry(part)
    merged = collection.UnionCascaded()
    if epsg != SOURCE_EPSG:
        source, target = osr.SpatialReference(), osr.SpatialReference()
        source.ImportFromEPSG(SOURCE_EPSG)
        target.ImportFromEPSG(epsg)
        for srs in (source, target):
            srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        merged.Transform(osr.CoordinateTransformation(source, target))
    return json.loads(merged.ExportToJson())


def fetch_municipality(get: Callable[[str], str], kommunkod: str, epsg: int,
                       progress: Optional[Callable[[str], None]] = None) -> list[dict]:
    """Kommunens yta (en GeoJSON-geometri i planens koordinatsystem) ur SCB:s DeSO."""
    if progress:
        progress("Hämtar kommunens yta …")
    url = query_url(kommunkod)
    try:
        data = json.loads(get(url))
    except (ValueError, OSError) as exc:
        raise FetchError(f"Kunde inte läsa svaret från SCB:s tjänst: {exc}") from exc
    shapes = [f["geometry"] for f in data.get("features") or [] if f.get("geometry")]
    if not shapes:
        raise FetchError(f"Hittade ingen kommun med koden {kommunkod} i SCB:s DeSO.")
    return [merge(shapes, epsg)]


def plan_area(group):
    """Planens avgränsning: plangeometrins ytor sammanslagna (även osparade), eller None."""
    from qgis.core import QgsGeometry

    from .project import layer_in_group
    layer = layer_in_group(group, PLAN_AREA)
    shapes = [f.geometry() for f in layer.getFeatures() if f.hasGeometry()] if layer is not None else []
    return QgsGeometry.unaryUnion(shapes) if shapes else None

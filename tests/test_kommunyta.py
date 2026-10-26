"""Kommunens yta som plangeometri när en ny översiktsplan skapas: frågan till SCB:s DeSO, sammanslagningen, att ytan
skrivs in i planen, och valet i dialogen Ny översiktsplan. Nätverket byts mot en låtsasfunktion."""
import datetime
import json
import sqlite3
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import closing
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qgis_app import get_app  # noqa: E402

get_app()

from qgis.core import QgsProject  # noqa: E402

from rita_oversiktsplan import classFactory  # noqa: E402
from rita_oversiktsplan.core import geopackage, kommunyta, riksintressen  # noqa: E402
from rita_oversiktsplan.core.project import active_plan_group, load_plan  # noqa: E402
from rita_oversiktsplan.gui.new_plan_dialog import NewPlanDialog  # noqa: E402
from test_plugin import FakeIface  # noqa: E402
from test_riksintressen import feature, polygon  # noqa: E402

AREA = polygon(0, 0, 100, 100)
DESO = (polygon(0, 0, 100, 50), polygon(0, 50, 100, 100))  # två DeSO som tillsammans är AREA
PLAN = geopackage.NewPlan("1494", "Lidköping", "ÖP 2045", datetime.date(2027, 1, 1))


def fake_service(shapes=DESO):
    """Svarar som SCB:s WFS med kommunens DeSO-ytor för kommunkoden 1494."""
    urls = []

    def get(url):
        urls.append(url)
        where = dict(urllib.parse.parse_qsl(url.split("?", 1)[1]))["cql_filter"]
        return json.dumps({"type": "FeatureCollection",
                           "features": [feature(s, kommunkod="1494") for s in shapes] if "1494" in where else []})
    get.urls = urls
    return get


class FetchTests(unittest.TestCase):
    def test_the_municipality_is_its_deso_areas_merged(self):
        from qgis.core import QgsGeometry, QgsJsonUtils
        get = fake_service()
        (shape,) = kommunyta.fetch_municipality(get, "1494", 3006)
        merged = QgsJsonUtils.geometryFromGeoJson(json.dumps(shape))
        self.assertAlmostEqual(merged.area(), 10_000)
        self.assertEqual(len(merged.asGeometryCollection()), 1)  # en yta, inga inre gränser
        square = QgsGeometry.fromWkt("POLYGON((0 0, 100 0, 100 100, 0 100, 0 0))")
        self.assertAlmostEqual(merged.symDifference(square).area(), 0)  # samma område som kommunen
        params = dict(urllib.parse.parse_qsl(get.urls[0].split("?", 1)[1]))
        self.assertTrue(get.urls[0].startswith("https://geodata.scb.se/geoserver/stat/wfs?"))
        self.assertEqual((params["typeNames"], params["cql_filter"], params["srsName"]),
                         ("stat:DeSO_2025", "kommunkod='1494'", "EPSG:3006"))

    def test_a_plan_in_a_local_zone_gets_the_area_in_its_own_coordinates(self):
        far = (polygon(400000, 6500000, 401000, 6501000),)
        (shape,) = kommunyta.fetch_municipality(fake_service(far), "1494", 3007)
        x = shape["coordinates"][0][0][0]
        self.assertNotAlmostEqual(x, 400000, delta=1000)  # omräknad från SWEREF 99 TM

    def test_an_unknown_or_malformed_code_is_reported(self):
        with self.assertRaisesRegex(riksintressen.FetchError, "Hittade ingen kommun med koden 9999"):
            kommunyta.fetch_municipality(fake_service(), "9999", 3006)
        with self.assertRaisesRegex(ValueError, "fyra siffror"):
            kommunyta.fetch_municipality(fake_service(), "14' OR '1'='1", 3006)


class NewPlanAreaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_the_area_is_written_into_the_new_plan_as_plangeometri(self):
        path = geopackage.create_geopackage(self.dir / "op.gpkg", geopackage.NewPlan(
            "1494", "Lidköping", "ÖP", datetime.date(2027, 1, 1), plan_area=(AREA,)))
        with closing(sqlite3.connect(path)) as db:
            rows = db.execute("SELECT innehallstyp_varde, namn, illustrativa_granser, under_ersattning, "
                              "datum_paborjat, objektidentitet FROM innehall_op_plangeometri").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][:5], ("Plangeometri", "Lidköping", 1, 0, "2027-01-01"))
        self.assertEqual(len(rows[0][5]), 36)  # ett UUID
        project = QgsProject()
        self.addCleanup(project.clear)
        layers = load_plan(path, project)
        plan = layers[kommunyta.PLAN_AREA]
        self.assertEqual(plan.featureCount(), 1)
        self.assertEqual(next(plan.getFeatures()).geometry().wkbType(), plan.wkbType())  # multipolygon
        self.assertAlmostEqual(kommunyta.plan_area(active_plan_group(project)).area(), 10_000)

    def test_without_an_area_the_plangeometri_is_empty(self):
        path = geopackage.create_geopackage(self.dir / "op.gpkg", PLAN)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM innehall_op_plangeometri").fetchone()[0], 0)


class NewPlanCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.iface = FakeIface()
        self.plugin = classFactory(self.iface)
        self.plugin.initGui()
        self.addCleanup(self.plugin.unload)
        QgsProject.instance().clear()
        self.addCleanup(QgsProject.instance().clear)

    def create(self, fetch_area: bool, get):
        def fill(dialog):
            dialog.kommun.set_kommun("Lidköping")
            dialog.titel.setText("ÖP 2045")
            dialog.folder.setFilePath(str(self.dir))
            dialog.municipality_area.setChecked(fetch_area)
            return True
        with mock.patch.object(NewPlanDialog, "exec", new=fill), \
                mock.patch("rita_oversiktsplan.plugin.qgis_get", new=get):
            self.plugin.new_plan()
        layer = next(layer for layer in QgsProject.instance().mapLayers().values()
                     if layer.name() == "Plangeometri")
        return layer

    def messages(self):
        return [call.args[1] for call in self.iface.bar.pushMessage.call_args_list]

    def test_the_box_is_ticked_from_the_start(self):
        dialog = NewPlanDialog()
        self.addCleanup(dialog.deleteLater)
        self.assertTrue(dialog.municipality_area.isChecked())

    def test_a_new_plan_gets_the_municipality_as_plangeometri(self):
        layer = self.create(True, fake_service())
        self.assertEqual(layer.featureCount(), 1)
        self.assertIn("Kommunens yta är plangeometri.", self.messages()[-1])

    def test_unticked_the_plangeometri_is_left_to_draw(self):
        get = fake_service()
        layer = self.create(False, get)
        self.assertEqual(layer.featureCount(), 0)
        self.assertEqual(get.urls, [])

    def test_if_the_service_fails_the_plan_is_created_anyway(self):
        def broken(url):
            raise OSError("tjänsten svarar inte")
        layer = self.create(True, broken)
        self.assertEqual(layer.featureCount(), 0)
        self.assertTrue(any("Kunde inte hämta kommunens yta" in text for text in self.messages()))
        self.assertIn("plangeometrin saknas", self.messages()[-1])


if __name__ == "__main__":
    unittest.main()

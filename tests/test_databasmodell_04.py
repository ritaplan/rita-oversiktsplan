"""Boverkets databasmodell 0.4 (pluginets schema 5): en plan från schema 4 (databasmodell 0.3, ÖP-katalogen 2.2)
uppgraderas när den öppnas, och SQL:en för samma uppgradering i en PostGIS-databas."""
import datetime
import sqlite3
import sys
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qgis_app import get_app  # noqa: E402

get_app()

from osgeo import ogr  # noqa: E402
from qgis.core import QgsProject  # noqa: E402

from rita_oversiktsplan.core import export_lm, geopackage, migration, model, opkatalog, storage  # noqa: E402
from rita_oversiktsplan.core.project import active_plan_group, load_plan  # noqa: E402

PLAN = geopackage.NewPlan("0484", "Eskilstuna", "ÖP 2040", datetime.date(2027, 1, 1))
MVA = "innehall_op_markochvattenanvandning_polygon"


def _sql(value) -> str:
    return "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"


def make_schema4(path: Path) -> dict[str, str]:
    """Gör en ny plan till en plan från schema 4 (som 0.1.14 skapade den) med två innehåll, en koppling, ett beslut med
    datum och en dokumentreferens. Genom GDAL, eftersom GeoPackagens triggrar behöver dess funktioner. Returnerar
    id:na."""
    ids = {"a": str(uuid.uuid4()), "b": str(uuid.uuid4()), "link": str(uuid.uuid4()), "beslut": str(uuid.uuid4()),
           "doc": str(uuid.uuid4())}
    ds = ogr.Open(str(path), 1)
    try:
        def field(table: str, name: str) -> None:
            ds.GetLayerByName(table).CreateField(ogr.FieldDefn(name, ogr.OFTString))

        def drop(table: str, name: str) -> None:
            layer = ds.GetLayerByName(table)
            layer.DeleteField(layer.GetLayerDefn().GetFieldIndex(name))

        for table, columns in model.REMOVED_COLUMNS.items():
            for column in columns:
                field(table, column)
        for table, columns in model.ADDED_COLUMNS.items():
            for column in columns:
                if column not in ("precisering", model.ARROW_FIELD):  # de kom i schema 4
                    drop(table, column)
        for layer_def in (model.BESLUT_HANDELSE, model.BESLUT_DOKUMENT):
            ds.DeleteLayer(next(i for i in range(ds.GetLayerCount()) if ds.GetLayer(i).GetName() == layer_def.name))
        plan = ds.GetLayerByName("oversiktsplan").GetNextFeature()["objektidentitet"]
        ids["plan"] = plan
        for statement in (
                f'INSERT INTO "{MVA}" (objektidentitet, innehallstyp_varde, namn, planhandelse_varde, '
                f'beror_annat_innehall_id, dokument_id, under_ersattning, illustrativa_granser) VALUES '
                f"({_sql(ids['a'])}, 'Fiske', 'Hamnen', 'Antagen', {_sql(ids['link'])}, {_sql(ids['a'])}, 0, 1)",
                f'INSERT INTO "{MVA}" (objektidentitet, innehallstyp_varde, namn, planhandelse_varde, under_ersattning, '
                f"illustrativa_granser) VALUES ({_sql(ids['b'])}, 'Bostadsbebyggelse', 'Norr', 'Antagen', 0, 1)",
                'INSERT INTO "innehall_op_beror_annat_innehall" (beror_annat_innehall_id, beror_annat_innehal_uuid) '
                f"VALUES ({_sql(ids['link'])}, {_sql(ids['b'])})",
                'INSERT INTO "beslut_op" (objektidentitet, rubrik, diarienummer, beslutande_organisation, '
                f"beslutande_instans, datum_fattat, datum_laga_kraft) VALUES ({_sql(ids['beslut'])}, 'Antagande', "
                "'KS 2027/1', 'Eskilstuna', 'kommunfullmäktige', '2027-05-01', '2027-06-01')",
                f"UPDATE oversiktsplan SET beslut = {_sql(ids['beslut'])}, dokument_id = {_sql(plan)}",
                'INSERT INTO "dokumentreferens_op" (namn, kortnamn, dokumentreferens_id, identitet) VALUES '
                f"('plan.docx', 'Planhandling', {_sql(ids['doc'])}, {_sql(ids['doc'])})",
                "UPDATE innehall_op_markochvattenanvandning_lookup SET innehallstyp_varde = 'Fiske', "
                "version_opkatalogen = '2.2' WHERE innehallstyp_varde = 'Yrkesfiske'",
                f"UPDATE {model.META_TABLE} SET value = '4' WHERE key = 'schema_version'",
                f"UPDATE {model.META_TABLE} SET value = '0.3' WHERE key = 'databasmodell'",
                f"UPDATE {model.META_TABLE} SET value = '2.2' WHERE key = 'opkatalog_version'"):
            ds.ExecuteSQL(statement)
    finally:
        ds = None
    return ids


class GeoPackageUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.path = geopackage.create_geopackage(Path(self.tmp.name) / "plan.gpkg", PLAN)
        self.ids = make_schema4(self.path)
        self.project = QgsProject()
        self.addCleanup(self.project.clear)

    def query(self, sql: str, args=()) -> list:
        with closing(sqlite3.connect(self.path)) as con:
            return con.execute(sql, args).fetchall()

    def columns(self, table: str) -> set[str]:
        return {row[1] for row in self.query(f'PRAGMA table_info("{table}")')}

    def test_the_test_file_really_looks_like_schema_4(self):
        self.assertIn("beror_annat_innehall_id", self.columns(MVA))
        self.assertNotIn(model.PLAN_FIELD, self.columns(MVA))
        self.assertIn("datum_fattat", self.columns("beslut_op"))
        self.assertEqual(geopackage.read_meta(self.path)["schema_version"], "4")

    def test_opening_the_plan_upgrades_it_and_keeps_a_copy_of_the_old_file(self):
        load_plan(self.path, self.project)
        meta = geopackage.read_meta(self.path)
        self.assertEqual((meta["schema_version"], meta["databasmodell"], meta["opkatalog_version"]),
                         (str(model.SCHEMA_VERSION), "0.4", opkatalog.bundled().version))
        self.assertEqual(meta["opkatalog_version_fore_uppgradering"], "2.2")
        backup = geopackage.backup_path(self.path)
        self.assertEqual(backup.name, "plan_fore_uppgradering.gpkg")
        self.assertEqual(geopackage.read_meta(backup)["schema_version"], "4")

    def test_the_tables_then_have_the_same_columns_as_a_new_plan(self):
        geopackage.upgrade(self.path)
        new = geopackage.create_geopackage(Path(self.tmp.name) / "ny.gpkg", PLAN)
        with closing(sqlite3.connect(new)) as con:
            for layer_def in model.LAYERS:
                expected = {row[1] for row in con.execute(f'PRAGMA table_info("{layer_def.name}")')}
                self.assertEqual(self.columns(layer_def.name), expected, layer_def.name)

    def test_content_points_at_the_plan_and_renamed_catalog_values_get_their_new_names(self):
        geopackage.upgrade(self.path)
        rows = self.query(f'SELECT namn, innehallstyp_varde, oversiktsplan FROM "{MVA}" ORDER BY namn')
        self.assertEqual(rows, [("Hamnen", "Yrkesfiske", self.ids["plan"]), ("Norr", "Bostadsbebyggelse", self.ids["plan"])])
        self.assertEqual(self.query('SELECT count(*) FROM innehall_op_markochvattenanvandning_lookup '
                                    "WHERE innehallstyp_varde = 'Fiske'"), [(0,)])
        versions = self.query("SELECT DISTINCT version_opkatalogen FROM innehall_op_markochvattenanvandning_lookup")
        self.assertEqual(versions, [(opkatalog.bundled().version,)])

    def test_the_relation_and_the_decision_dates_are_moved_into_their_new_tables(self):
        geopackage.upgrade(self.path)
        self.assertEqual(self.query("SELECT objektidentitet, beror_objektidentitet FROM innehall_op_beror_annat_innehall"),
                         [(self.ids["a"], self.ids["b"])])
        self.assertEqual(self.query("SELECT beslutande_organisation_namn, diarienummer, rubrik FROM beslut_op"),
                         [("Eskilstuna", "KS 2027/1", "Antagande")])
        self.assertEqual(self.query("SELECT beslut_op_id, handelsetyp, datum FROM beslut_op_handelse ORDER BY datum"),
                         [(self.ids["beslut"], "fattat", "2027-05-01"), (self.ids["beslut"], "laga kraft", "2027-06-01")])
        self.assertEqual(self.query("SELECT producentens_identitet FROM dokumentreferens_op"), [(self.ids["doc"],)])

    def test_upgrading_twice_changes_nothing_the_second_time(self):
        self.assertTrue(geopackage.upgrade(self.path))
        self.assertFalse(geopackage.upgrade(self.path))
        self.assertEqual(len(self.query("SELECT * FROM beslut_op_handelse")), 2)

    def test_the_upgraded_plan_is_exported_with_the_relation_and_the_decision(self):
        load_plan(self.path, self.project)
        data, _ = export_lm.export(active_plan_group(self.project))
        props = [f["properties"] for f in data["features"]]
        decision = next(p for p in props if p["feature:typ"] == "beslutOP")
        self.assertEqual(decision["beslutandeOrganisation"], {"organisationsnamn": "Eskilstuna"})
        self.assertEqual(decision["handelse"], [{"handelsetyp": "fattat", "datum": "2027-05-01"},
                                                {"handelsetyp": "laga kraft", "datum": "2027-06-01"}])
        harbour = next(p for p in props if p.get("namn") == "Hamnen")
        self.assertEqual(harbour["berorAnnatInnehall"], [self.ids["b"]])
        self.assertEqual(harbour["innehallstyp"]["varde"], "Yrkesfiske")


class NewPlanTests(unittest.TestCase):
    def test_new_content_points_at_the_plan(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = geopackage.create_geopackage(Path(tmp) / "plan.gpkg", PLAN)
            project = QgsProject.instance()  # standardvärdet slår upp planens lager i projektet
            layers = load_plan(path, project)
            plan = next(layers["oversiktsplan"].getFeatures())["objektidentitet"]
            layer = layers[MVA]
            from qgis.core import QgsGeometry, QgsVectorLayerUtils
            feature = QgsVectorLayerUtils.createFeature(layer, QgsGeometry(), {})
            self.assertEqual(feature[model.PLAN_FIELD], plan)
            project.clear()


class PostgisMigrationTests(unittest.TestCase):
    def setUp(self):
        self.sql = storage.upgrade_schema_sql("planer", 3006)

    def test_it_is_one_transaction_that_adds_moves_and_then_drops(self):
        self.assertTrue(self.sql.startswith("DO $op$ BEGIN"))
        add = self.sql.index('ADD COLUMN IF NOT EXISTS "oversiktsplan"')
        move = self.sql.index('UPDATE "planer"."innehall_op_beror_annat_innehall" AS u SET "objektidentitet"')
        drop = self.sql.index('DROP COLUMN IF EXISTS "beror_annat_innehall_id"')
        self.assertLess(add, move)
        self.assertLess(move, drop)

    def test_rows_are_matched_within_the_same_plan(self):
        self.assertIn('o."plan" = u."plan"', self.sql)
        self.assertIn('c."plan" = u."plan"', self.sql)
        self.assertIn('l."plan" = u."plan"', self.sql)

    def test_the_long_table_name_is_shortened_as_elsewhere_in_the_database(self):
        long = "innehall_op_sarskiltvardefullabyggnadsverkallmannaplatserochbebyggelseomraden_polygon"
        self.assertNotIn(f'"{long}"', self.sql)
        self.assertIn(f'"{storage.db_name(long)}"', self.sql)

    def test_every_plan_in_the_schema_gets_its_own_catalog_rows(self):
        self.assertIn('INSERT INTO "planer"."planhandelse_lookup" ("plan", ', self.sql)
        self.assertIn('SELECT p."plan", ', self.sql)

    def test_both_schema_3_and_4_can_be_upgraded(self):
        self.assertEqual(storage.UPGRADABLE, ("3", "4"))


class CatalogRenameTests(unittest.TestCase):
    def test_values_are_renamed_by_their_id_and_braces_and_case_do_not_matter(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE t (innehallstyp_varde TEXT)")
        con.execute("CREATE TABLE l (innehallstyp_varde TEXT, vardereferens TEXT)")
        con.execute("INSERT INTO t VALUES ('Fiske'), ('Bostadsbebyggelse'), ('Påhittat')")
        ref = opkatalog.bundled().find("Mark- och vattenanvändning", "Yrkesfiske").vardereferens
        con.execute("INSERT INTO l VALUES ('Fiske', ?)", ("{" + ref.upper() + "}",))
        update = (f"UPDATE t AS u SET innehallstyp_varde = 'Yrkesfiske' WHERE u.innehallstyp_varde <> 'Yrkesfiske' "
                  f"AND u.innehallstyp_varde IN (SELECT l.innehallstyp_varde FROM l AS l "
                  f"WHERE {migration._ref('l.vardereferens')} = '{ref.lower()}')")
        con.execute(update)
        self.assertEqual(sorted(r[0] for r in con.execute("SELECT * FROM t")),
                         ["Bostadsbebyggelse", "Påhittat", "Yrkesfiske"])


if __name__ == "__main__":
    unittest.main()

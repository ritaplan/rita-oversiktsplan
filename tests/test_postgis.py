"""Planer i PostGIS: lagringen, en ny plan i databasen, öppna skrivskyddat, checka ut och checka in (kräver QGIS).

Ingen riktig databas används. En GeoPackage står för databasens tabeller (lagren läses därifrån), och en
låtsasanslutning svarar på pluginets frågor (metadata, uppslagstabeller, lås) och sparar den SQL som skickas.
Att SQL:en fungerar mot en riktig PostgreSQL med PostGIS är alltså inte provat här, samma upplägg som i Rita
Detaljplan."""
import datetime
import json
import re
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qgis_app import get_app  # noqa: E402

get_app()

from qgis.core import QgsFeature, QgsGeometry, QgsProject  # noqa: E402

from rita_oversiktsplan import classFactory  # noqa: E402
from rita_oversiktsplan.core import checkout as co  # noqa: E402
from rita_oversiktsplan.core import geopackage, model, storage  # noqa: E402
from rita_oversiktsplan.core.project import (active_plan_group, draft_layers, is_read_only, layer_in_group,  # noqa: E402
                                             load_plan, plan_storage, PlanError)
from rita_oversiktsplan.gui.checkout_actions import CHECK_IN, DISCARD, CheckoutActions  # noqa: E402
from rita_oversiktsplan.gui.new_plan_dialog import NewPlanDialog  # noqa: E402
from test_plugin import FakeIface  # noqa: E402

PLAN = geopackage.NewPlan("0484", "Eskilstuna", "ÖP 2040", datetime.date(2027, 1, 1))
SQUARE = "MULTIPOLYGON(((0 0, 100 0, 100 100, 0 100, 0 0)))"


class FakePg:
    """Låtsasdatabas: läser ur en GeoPackage (``database``), håller planens metadata med lås och loggar SQL:en."""

    def __init__(self, database: Path, schemas=("oversiktsplan",)):
        self.database = database
        self.meta = geopackage.read_meta(database) if database.exists() else {}
        self.schemas = list(schemas)
        self.sql: list[str] = []
        self.checkins: list[str] = []
        self.postgis = True
        self.epsg = None  # schemats koordinatsystem, om schemat redan finns
        self.refuse_upgrade = False  # som en användare utan rätt att ändra tabellerna
        self.may_create_schemas = True  # rätten CREATE på databasen
        self.may_create_tables = True  # rätten CREATE på scheman som finns

    def uri(self):
        return "dbname='planer' host=localhost port=5432 user='eric' sslmode=disable"

    def executeSql(self, sql):  # noqa: N802 - samma namn som QGIS anslutningar
        self.sql.append(sql)
        if sql == "SELECT postgis_version()":
            if not self.postgis:
                raise RuntimeError('function postgis_version() does not exist')
            return [["3.4"]]
        if "information_schema." in sql:
            return [[s] for s in self.schemas]
        if "pg_namespace" in sql:  # schema_exists
            return [[1]] if re.search(r"nspname = '([^']*)'", sql).group(1) in self.schemas else []
        if sql.startswith("SELECT has_database_privilege"):
            return [[self.may_create_schemas]]
        if sql.startswith("SELECT has_schema_privilege"):
            return [[self.may_create_tables]]
        if sql.startswith("CREATE SCHEMA") and not self.may_create_schemas:  # som PostgreSQL, även om schemat finns
            raise RuntimeError("permission denied for database planer")
        if sql.startswith('SELECT "value" FROM') and "rita_oversiktsplan_schema" in sql:
            return [[str(self.epsg)]] if self.epsg else []
        if sql.startswith('SELECT "key", "value" FROM'):
            return [[k, v] for k, v in self.meta.items()]
        if sql.startswith("SELECT 1 FROM"):  # plan_exists
            plan = re.search(r"\"plan\" = '([^']*)'", sql).group(1)
            return [[1]] if plan == "op_2040" and self.meta else []
        if sql.startswith("SELECT DISTINCT m.\"plan\""):
            return [["op_2040", "ÖP 2040"]] if self.meta else []
        if sql.startswith("SELECT") and "_lookup" in sql:
            table = re.search(r'FROM "[^"]+"\."([^"]+)"', sql).group(1)
            table = {storage.db_name(t.name): t.name for t in storage.tables()}.get(table, table)  # GeoPackagens namn
            columns = sql[len("SELECT "):sql.index(" FROM")]
            with closing(sqlite3.connect(str(self.database))) as con:
                return [list(r) for r in con.execute(f'SELECT {columns} FROM "{table}" ORDER BY fid')]
        if sql.startswith("DO $op$ BEGIN LOCK TABLE") and "kan inte skrivskyddas" in sql:  # skrivskydda planen
            if "checkout" in self.meta:
                raise RuntimeError("Planen är utcheckad och kan inte skrivskyddas. Checka in den eller bryt låset först.")
            match = re.search(r"VALUES \('[^']*', 'skrivskydd', '(.*)'\); END IF", sql)
            if "skrivskydd" not in self.meta:
                self.meta["skrivskydd"] = match.group(1).replace("''", "'")
            return []
        if sql.startswith("DO $op$ BEGIN LOCK TABLE"):  # låsa planen: går inte om den är låst eller skrivskyddad
            match = re.search(r"VALUES \('[^']*', 'checkout', '(.*)'\); END IF", sql)
            if "checkout" not in self.meta and "skrivskydd" not in self.meta:
                self.meta["checkout"] = match.group(1).replace("''", "'")
            return []
        if sql.startswith("DO $op") and "ADD COLUMN IF NOT EXISTS" in sql:  # uppgradering av schemat
            if self.refuse_upgrade:
                raise RuntimeError("must be owner of table innehall_op_plangeometri")
            version = re.search(r"SET \"value\" = '(\d+)' WHERE \"key\" = 'schema_version'", sql).group(1)
            self.meta["schema_version"] = version
            return []
        if sql.startswith("DO $op") and "RAISE EXCEPTION" in sql:  # incheckning
            token = re.search(r'"token": "([0-9a-f]+)"', sql).group(1)
            held = json.loads(self.meta["checkout"])["token"] if "checkout" in self.meta else None
            if held != token:
                raise RuntimeError("Låset på planen tillhör inte längre dig. Planen har inte checkats in.")
            self.checkins.append(sql)
            del self.meta["checkout"]
            return []
        if sql.startswith("DELETE FROM") and "'skrivskydd'" in sql:  # bryt skrivskyddet
            self.meta.pop("skrivskydd", None)
            return []
        if sql.startswith("DELETE FROM") and "'checkout'" in sql:
            token = re.search(r'"token": "([0-9a-f]+)"', sql)
            if "checkout" in self.meta and (token is None or json.loads(self.meta["checkout"])["token"] == token.group(1)):
                del self.meta["checkout"]
            return []
        return []


def other_lock():
    return co.Lock("f" * 32, "anna", "ANNAS-DATOR", "2026-10-17T09:00:00")


class PostgisCase(unittest.TestCase):
    """En plan i 'databasen' (en GeoPackage bakom en låtsasanslutning), öppnad i projektet."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.database = geopackage.create_geopackage(self.dir / "databas.gpkg", PLAN)
        self.conn = FakePg(self.database)
        self.copies = self.dir / "kopior"
        database = self.database

        def layer_uri(plan, table):
            return f"{database.as_posix()}|layername={table.name}"

        patches = [
            mock.patch.object(storage, "PROVIDER", "ogr"),
            mock.patch.object(storage.PostgisStorage, "layer_uri", layer_uri),
            mock.patch.object(storage, "postgis_connections", lambda: {"planer": self.conn}),
            mock.patch.object(co, "checkouts_dir", lambda: self.copies),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.plan = storage.PostgisStorage("planer", "oversiktsplan", "op_2040")
        self.project = QgsProject.instance()
        self.addCleanup(self._clear)
        self.layers = load_plan(self.plan, self.project)
        self.group = active_plan_group(self.project)

    def _clear(self):
        for layer in self.project.mapLayers().values():
            if layer.isEditable():
                layer.rollBack()
        self.project.clear()

    def layer(self, table):
        return layer_in_group(self.group, table)

    def draw(self, wkt=SQUARE):
        layer = draft_layers(self.group)["polygon"]
        self.assertTrue(layer.startEditing())
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        layer.addFeature(feature)
        self.assertTrue(layer.commitChanges())
        return layer


class StorageTests(unittest.TestCase):
    def test_names_become_identifiers(self):
        self.assertEqual(storage.identifier("ÖP 2040 – Eskilstuna"), "op_2040_eskilstuna")
        self.assertEqual(storage.identifier("2040"), "op_2040")
        self.assertFalse(storage.is_valid_schema("public"))
        self.assertFalse(storage.is_valid_plan_id("Stor bokstav"))

    def test_the_key_on_the_group_round_trips(self):
        plan = storage.PostgisStorage("Kommunens databas", "oversiktsplan", "op_2040")
        self.assertEqual(storage.from_key(plan.key), plan)
        self.assertEqual(storage.from_key(r"C:\planer\op.gpkg"), storage.GeoPackageStorage(r"C:\planer\op.gpkg"))

    def test_every_table_gets_a_plan_column_and_the_geometry_type(self):
        sql = "\n".join(storage.ensure_schema_sql("oversiktsplan"))
        for table in storage.tables():
            self.assertIn(f'CREATE TABLE IF NOT EXISTS "oversiktsplan"."{storage.db_name(table.name)}" ("fid" serial PRIMARY KEY, '
                          '"plan" text NOT NULL', sql)
        self.assertIn('"geom" geometry(MultiPolygon, 3006)', sql)
        self.assertIn('"geom" geometry(Point, 3006)', sql)
        self.assertIn('"oversiktsplan"."planhandelse_lookup" ("fid" serial PRIMARY KEY, "plan" text NOT NULL, '
                      '"planhandelse_varde" text, "vardereferens" text', sql)

    def test_names_too_long_for_postgresql_are_shortened_and_never_collide(self):
        names = [storage.db_name(t.name) for t in storage.tables()]
        self.assertTrue(all(len(n.encode("utf-8")) <= 63 for n in names))
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(storage.db_name("innehall_op_sarskiltvardefullabyggnadsverkallmannaplatserochbebyggelseomraden"
                                         "_polygon"), "innehall_op_sarskiltvardefullkulturmiljo_polygon")
        self.assertEqual(storage.db_name("oversiktsplan"), "oversiktsplan")
        sql = storage.ensure_schema_sql("oversiktsplan")
        created = [re.search(r'"oversiktsplan"\."([^"]+)"', s).group(1) for s in sql if s.startswith("CREATE TABLE")]
        indexes = [re.search(r'INDEX IF NOT EXISTS "([^"]+)"', s).group(1) for s in sql if "INDEX" in s]
        for name in created + indexes:
            self.assertLessEqual(len(name.encode("utf-8")), 63, name)
        self.assertEqual(len(indexes), len(set(indexes)))

    def test_rows_are_written_as_sql_values(self):
        table = storage.Table("innehall", "MultiPolygon", [("namn", model.TEXT), ("under_ersattning", model.BOOL),
                                                         ("datum_paborjat", model.DATE)])
        parts = storage.replace_rows_sql("s", "p", table, [
            {"geom": "POLYGON((0 0,1 0,1 1,0 0))", "namn": "Ån's strand", "under_ersattning": 1,
             "datum_paborjat": datetime.date(2027, 1, 2)},
            {"geom": None, "namn": None, "under_ersattning": None, "datum_paborjat": None}])
        self.assertEqual(parts[0], 'DELETE FROM "s"."innehall" WHERE "plan" = \'p\';')
        self.assertIn("(\'p\', ST_Multi(ST_GeomFromText('POLYGON((0 0,1 0,1 1,0 0))', 3006)), 'Ån''s strand', true, "
                      "'2027-01-02')", parts[1])
        self.assertIn("('p', NULL, NULL, NULL, NULL)", parts[1])
        self.assertTrue(storage.transaction_sql(["SELECT '$op$';"]).startswith("DO $op1$"))


class NewDatabasePlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.conn = FakePg(Path(self.tmp.name) / "saknas.gpkg", schemas=())

    def test_a_new_plan_creates_the_schema_and_writes_the_plan_in_one_transaction(self):
        plan = storage.create_postgis_plan("planer", "oversiktsplan", "op_2040", PLAN, self.conn)
        self.assertEqual(plan.key, storage.PostgisStorage("planer", "oversiktsplan", "op_2040").key)
        self.assertIn('CREATE SCHEMA IF NOT EXISTS "oversiktsplan"', self.conn.sql)
        block = self.conn.sql[-1]
        self.assertTrue(block.startswith("DO $op$ BEGIN"))
        self.assertIn('INSERT INTO "oversiktsplan"."oversiktsplan"', block)
        self.assertIn("'ÖP 2040'", block)
        self.assertIn("'Bostadsbebyggelse'", block)  # ÖP-katalogens värden följer med planen
        self.assertIn(f"'schema_version', '{model.SCHEMA_VERSION}'", block)

    def test_a_plan_id_that_exists_is_refused(self):
        self.conn = FakePg(geopackage.create_geopackage(Path(self.tmp.name) / "d.gpkg", PLAN))
        with self.assertRaises(storage.PostgisError) as caught:
            storage.create_postgis_plan("planer", "oversiktsplan", "op_2040", PLAN, self.conn)
        self.assertIn("finns redan", str(caught.exception))

    def test_a_local_zone_is_used_for_the_tables_and_an_existing_schema_must_match(self):
        zone = geopackage.NewPlan("1494", "Lidköping", "ÖP", datetime.date(2027, 1, 1), epsg=3010)
        storage.create_postgis_plan("planer", "oversiktsplan", "op_ny", zone, self.conn)
        self.assertTrue(any('"geom" geometry(MultiPolygon, 3010)' in sql for sql in self.conn.sql))
        self.assertIn("('epsg', '3010')", " ".join(self.conn.sql))
        self.conn = FakePg(geopackage.create_geopackage(Path(self.tmp.name) / "d.gpkg", PLAN))
        self.conn.epsg = 3006
        with self.assertRaises(storage.PostgisError) as caught:
            storage.create_postgis_plan("planer", "oversiktsplan", "op_annan", zone, self.conn)
        self.assertIn("EPSG:3006", str(caught.exception))

    def test_a_database_without_postgis_says_so(self):
        self.conn.postgis = False
        with self.assertRaises(storage.PostgisError) as caught:
            storage.create_postgis_plan("planer", "oversiktsplan", "op_2040", PLAN, self.conn)
        self.assertIn("CREATE EXTENSION postgis", str(caught.exception))

    def test_a_failed_new_schema_is_removed_again_but_an_existing_schema_is_never_dropped(self):
        original = self.conn.executeSql

        def fail_on_insert(sql):
            if sql.startswith("DO $op$"):
                raise RuntimeError('Felaktig fråga: DO ... returnerade 7 [ERROR: column "x" does not exist\n'
                                   'LINE 1: ...]')
            return original(sql)

        self.conn.executeSql = fail_on_insert
        with self.assertRaises(storage.PostgisError) as caught:
            storage.create_postgis_plan("planer", "oversiktsplan", "op_2040", PLAN, self.conn)
        self.assertEqual(str(caught.exception), 'Databasen svarade med ett fel: column "x" does not exist')
        self.assertIn('DROP SCHEMA IF EXISTS "oversiktsplan" CASCADE', self.conn.sql)
        self.conn.sql.clear()
        self.conn.schemas = ["oversiktsplan"]  # schemat fanns redan (till exempel med annat innehåll)
        with self.assertRaises(storage.PostgisError):
            storage.create_postgis_plan("planer", "oversiktsplan", "op_2040", PLAN, self.conn)
        self.assertFalse(any(sql.startswith("DROP") for sql in self.conn.sql))

    def test_a_plan_in_an_own_schema_works_without_the_right_to_create_schemas(self):
        self.conn.schemas = ["lukas"]  # ett tomt schema som användaren fått av kommunen
        self.conn.may_create_schemas = False
        storage.create_postgis_plan("planer", "lukas", "op_2040", PLAN, self.conn)
        self.assertFalse(any(sql.startswith("CREATE SCHEMA") for sql in self.conn.sql))
        self.assertIn('CREATE TABLE IF NOT EXISTS "lukas"."oversiktsplan"', " ".join(self.conn.sql))
        self.assertIn('INSERT INTO "lukas"."oversiktsplan"', self.conn.sql[-1])

    def test_without_the_right_to_create_schemas_a_missing_schema_is_explained(self):
        self.conn.may_create_schemas = False
        with self.assertRaisesRegex(storage.PostgisError, "får inte skapa nya scheman"):
            storage.create_postgis_plan("planer", "oversiktsplan", "op_2040", PLAN, self.conn)
        self.assertFalse(any(sql.startswith("CREATE") for sql in self.conn.sql))

    def test_without_the_right_to_create_tables_an_existing_schema_is_explained(self):
        self.conn.schemas = ["lukas"]
        self.conn.may_create_tables = False
        with self.assertRaisesRegex(storage.PostgisError, "rätt att skapa tabeller i schemat lukas"):
            storage.create_postgis_plan("planer", "lukas", "op_2040", PLAN, self.conn)
        self.assertFalse(any(sql.startswith(("CREATE", "DROP")) for sql in self.conn.sql))

    def test_an_upgrade_never_tries_to_create_the_schema(self):
        self.assertNotIn("CREATE SCHEMA", storage.upgrade_schema_sql("lukas", 3006))

    def test_bad_names_are_refused_before_anything_is_sent(self):
        with self.assertRaises(storage.PostgisError):
            storage.create_postgis_plan("planer", "public", "op_2040", PLAN, self.conn)
        self.assertEqual(self.conn.sql, [])


class SchemaUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        database = geopackage.create_geopackage(Path(self.tmp.name) / "databas.gpkg", PLAN)
        self.conn = FakePg(database)

        def layer_uri(plan, table):
            return f"{database.as_posix()}|layername={table.name}"

        for patcher in (mock.patch.object(storage, "PROVIDER", "ogr"),
                        mock.patch.object(storage.PostgisStorage, "layer_uri", layer_uri),
                        mock.patch.object(storage, "postgis_connections", lambda: {"planer": self.conn})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(QgsProject.instance().clear)

    def open(self):
        return load_plan(storage.PostgisStorage("planer", "oversiktsplan", "op_2040"), QgsProject.instance())

    def test_a_schema_from_version_3_gets_the_new_column_when_a_plan_is_opened(self):
        self.conn.meta["schema_version"] = "3"
        self.open()
        upgrade = next(sql for sql in self.conn.sql if "ADD COLUMN IF NOT EXISTS" in sql)
        self.assertIn('ALTER TABLE "oversiktsplan"."innehall_op_plangeometri" ADD COLUMN IF NOT EXISTS '
                      '"precisering" text', upgrade)
        self.assertTrue(upgrade.startswith("DO $op$ BEGIN"))  # en transaktion
        self.assertIn("rita_oversiktsplan_schema", upgrade)  # schemats version också
        self.assertEqual(self.conn.meta["schema_version"], str(model.SCHEMA_VERSION))

    def test_a_current_schema_is_left_alone(self):
        self.open()
        self.assertFalse([sql for sql in self.conn.sql if "ALTER TABLE" in sql])

    def test_without_the_right_to_change_the_tables_the_plan_is_refused_with_an_explanation(self):
        self.conn.meta["schema_version"] = "3"
        self.conn.refuse_upgrade = True
        with self.assertRaisesRegex(PlanError, "äldre version av pluginet"):
            self.open()

    def test_a_new_plan_in_an_old_schema_also_adds_the_column(self):
        sql = storage.ensure_schema_sql("oversiktsplan")
        self.assertIn('ALTER TABLE "oversiktsplan"."innehall_op_plangeometri" ADD COLUMN IF NOT EXISTS '
                      '"precisering" text', sql)


class OpenTests(PostgisCase):
    def test_a_database_plan_is_read_only_and_reads_lookups_from_the_database(self):
        self.assertEqual(co.state(self.group), co.DATABASE)
        self.assertTrue(is_read_only(self.group))
        self.assertTrue(all(layer.readOnly() for layer in self.layers.values()))
        self.assertIn("Bostadsbebyggelse", plan_storage(self.group).read_lookup(
            next(lookup for lookup in model.LOOKUPS if lookup.name == "innehall_op_markochvattenanvandning_lookup")))
        self.assertEqual(self.group.name(), "Översiktsplan – ÖP 2040")

    def test_the_same_plan_cannot_be_opened_twice(self):
        with self.assertRaises(Exception):
            load_plan(storage.PostgisStorage("planer", "oversiktsplan", "op_2040"), self.project)


class CheckoutTests(PostgisCase):
    def test_check_out_locks_the_plan_and_makes_it_editable_in_a_local_copy(self):
        path = co.check_out(self.group)
        self.assertEqual(co.state(self.group), co.LOCAL)
        self.assertTrue(path.exists())
        self.assertEqual(json.loads(self.conn.meta["checkout"])["token"], self.group.customProperty(
            co.TOKEN_PROPERTY))
        layer = self.layer("innehall_op_markochvattenanvandning_polygon")
        self.assertFalse(layer.readOnly())
        self.assertIn(path.name, layer.source())
        self.assertEqual(self.layer("oversiktsplan").featureCount(), 1)  # planens rad följde med
        self.assertIn("Bostadsbebyggelse", plan_storage(self.group).read_lookup(
            next(lookup for lookup in model.LOOKUPS if lookup.name == "innehall_op_markochvattenanvandning_lookup")))
        self.assertNotIn("checkout", geopackage.read_meta(path))  # låsraden kopieras inte
        self.assertEqual(geopackage.read_meta(path)["checkout_token"], self.group.customProperty(co.TOKEN_PROPERTY))

    def test_check_in_writes_the_plan_back_in_one_transaction_and_releases_the_lock(self):
        path = co.check_out(self.group)
        self.draw()
        copy, removed = co.check_in(self.group)
        self.assertEqual(copy, path)
        self.assertEqual(co.state(self.group), co.DATABASE)
        self.assertNotIn("checkout", self.conn.meta)
        sql = self.conn.checkins[-1]
        self.assertIn('DELETE FROM "oversiktsplan"."rita_otilldelad_yta" WHERE "plan" = \'op_2040\';', sql)
        self.assertIn('INSERT INTO "oversiktsplan"."rita_otilldelad_yta"', sql)
        self.assertIn("ST_Multi(ST_GeomFromText('MultiPolygon", sql)
        self.assertNotIn('"innehall_op_markochvattenanvandning_lookup"', sql)  # katalogen ändras inte
        self.assertIn("AND NOT (\"key\" = 'checkout')", sql)  # låset tas bort sist, inte med metadatan
        self.assertNotIn("checkout_token", sql)
        self.assertTrue(all(layer.readOnly() for layer in self.layers.values()))

    def test_a_plan_checked_out_by_someone_else_cannot_be_checked_out(self):
        self.conn.meta["checkout"] = other_lock().to_json()
        with self.assertRaises(co.LockedError) as caught:
            co.check_out(self.group)
        self.assertIn("anna på ANNAS-DATOR", str(caught.exception))
        self.assertEqual(co.state(self.group), co.DATABASE)

    def test_check_in_fails_safely_when_the_lock_was_broken(self):
        path = co.check_out(self.group)
        self.conn.meta["checkout"] = other_lock().to_json()
        with self.assertRaises(co.CheckoutError):
            co.check_in(self.group)
        self.assertEqual(co.state(self.group), co.LOCAL)
        self.assertTrue(path.exists())

    def test_discard_releases_the_lock_without_writing(self):
        co.check_out(self.group)
        co.discard(self.group)
        self.assertEqual(co.state(self.group), co.DATABASE)
        self.assertNotIn("checkout", self.conn.meta)
        self.assertEqual(self.conn.checkins, [])

    def test_an_interrupted_checkout_can_be_resumed(self):
        path = co.check_out(self.group)
        self.group.setCustomProperty(co.PATH_PROPERTY, "")  # som om QGIS kraschat och projektet öppnats igen
        self.group.setCustomProperty(co.TOKEN_PROPERTY, "")
        found = co.resumable_copy(self.plan)
        self.assertEqual(found[0], path)


class ProtectionTests(PostgisCase):
    """Skrivskydd: en plan som inte får ändras kan inte checkas ut förrän skyddet bryts."""

    def test_a_plan_is_protected_with_who_when_and_why(self):
        self.assertIsNone(co.read_protection(self.plan))
        protection = co.protect(self.plan, "  Antagen 2026-10-01  ")
        self.assertEqual(co.read_protection(self.plan), protection)
        self.assertTrue(protection.user)
        self.assertRegex(protection.since, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")
        self.assertEqual(protection.reason, "Antagen 2026-10-01", "skälet trimmas")
        self.assertIn("sedan", protection.describe())
        self.assertTrue(protection.describe().endswith(": Antagen 2026-10-01"))

    def test_the_reason_is_optional(self):
        protection = co.protect(self.plan)
        self.assertEqual(protection.reason, "")
        self.assertEqual(protection.describe(),
                         f"{protection.user} på {protection.host} sedan {protection.since.replace('T', ' ')}")

    def test_protecting_is_done_while_the_meta_table_is_locked_and_checks_the_lock_in_the_same_step(self):
        co.protect(self.plan)
        sql = next(s for s in self.conn.sql if "kan inte skrivskyddas" in s)
        self.assertIn('LOCK TABLE "oversiktsplan".', sql)
        self.assertIn("IN EXCLUSIVE MODE", sql)
        self.assertLess(sql.index("'checkout'"), sql.index("'skrivskydd'"), "låset kontrolleras före skyddet läggs in")

    def test_a_protected_plan_stays_as_it_was_protected_if_protected_again(self):
        first = co.protect(self.plan, "första")
        second = co.protect(self.plan, "andra")
        self.assertEqual(second, first)
        self.assertEqual(co.read_protection(self.plan).reason, "första")

    def test_a_checked_out_plan_cannot_be_protected(self):
        self.conn.meta["checkout"] = other_lock().to_json()
        with self.assertRaisesRegex(co.CheckoutError, "utcheckad och kan inte skrivskyddas"):
            co.protect(self.plan)
        self.assertIsNone(co.read_protection(self.plan))
        self.assertEqual(co.read_lock(self.plan), other_lock(), "den andras lås är orört")

    def test_a_plan_that_is_not_in_the_database_cannot_be_protected(self):
        self.conn.meta.clear()
        with self.assertRaisesRegex(co.CheckoutError, "finns inte"):
            co.protect(self.plan)

    def test_a_protected_plan_cannot_be_locked_and_the_error_says_who_protected_it(self):
        co.protect(self.plan, "Antagen")
        with self.assertRaises(co.ProtectedError) as caught:
            co.acquire_lock(self.plan)
        self.assertEqual(caught.exception.protection, co.read_protection(self.plan))
        self.assertIn("skrivskyddad av", str(caught.exception))
        self.assertIn("Antagen", str(caught.exception))
        self.assertIn("Bryt skrivskyddet", str(caught.exception))
        self.assertIsNone(co.read_lock(self.plan), "inget lås lades in")

    def test_the_lock_is_only_taken_if_the_plan_is_neither_locked_nor_protected(self):
        co.protect(self.plan)
        with self.assertRaises(co.ProtectedError):
            co.acquire_lock(self.plan)
        sql = [s for s in self.conn.sql if s.startswith("DO $op$ BEGIN LOCK TABLE") and "'checkout', '{" in s][-1]
        self.assertIn("IN ('checkout', 'skrivskydd')", sql, "skyddet kontrolleras i samma steg som låset läggs in")

    def test_a_plan_open_from_the_database_cannot_be_checked_out_while_protected(self):
        co.protect(self.plan, "Antagen")
        with self.assertRaises(co.ProtectedError):
            co.check_out(self.group)
        self.assertEqual(co.state(self.group), co.DATABASE)
        self.assertIsNone(co.read_lock(self.plan))
        self.assertFalse(self.copies.exists() and list(self.copies.iterdir()), "ingen kopia lämnas kvar")

    def test_lifting_the_protection_lets_the_plan_be_checked_out_again(self):
        co.protect(self.plan)
        co.unprotect(self.plan)
        self.assertIsNone(co.read_protection(self.plan))
        co.check_out(self.group)
        self.assertEqual(co.state(self.group), co.LOCAL)

    def test_lifting_a_protection_that_is_not_there_does_nothing(self):
        co.unprotect(self.plan)
        self.assertIsNone(co.read_protection(self.plan))

    def test_a_protection_row_that_cannot_be_read_still_protects(self):
        self.conn.meta["skrivskydd"] = "skräp"
        protection = co.read_protection(self.plan)
        self.assertIsNotNone(protection)
        self.assertEqual(protection.user, "okänd")
        with self.assertRaises(co.ProtectedError):
            co.acquire_lock(self.plan)

    def test_the_protection_is_not_copied_to_the_local_copy(self):
        self.conn.meta["skrivskydd"] = co.Protection("anna", "ANNAS-DATOR", "2026-11-01T09:00:00", "x").to_json()
        path = co.copy_to_geopackage(self.plan, self.dir / "kopia.gpkg")
        self.assertNotIn("skrivskydd", geopackage.read_meta(path))

    def test_database_errors_become_checkout_errors(self):
        original = self.conn.executeSql

        def failing(sql):
            if "LOCK TABLE" in sql:
                raise RuntimeError("syntaxfel nära LOCK")
            return original(sql)

        with mock.patch.object(self.conn, "executeSql", failing):
            with self.assertRaises(co.CheckoutError):
                co.protect(self.plan)


class ActionTests(PostgisCase):
    def actions(self, answers=True, check_in=CHECK_IN):
        self.messages = []
        actions = CheckoutActions(lambda text, warning: self.messages.append((text, warning)))
        actions.ask_yes_no = lambda *a, **k: answers
        actions.ask_check_in = lambda: check_in
        actions.ask_break_lock = lambda lock: answers
        return actions

    def test_a_locked_plan_can_be_taken_over_by_breaking_the_lock(self):
        self.conn.meta["checkout"] = other_lock().to_json()
        self.assertTrue(self.actions().check_out(self.group))
        self.assertEqual(co.state(self.group), co.LOCAL)

    def test_a_protected_plan_is_not_checked_out_and_the_reason_is_reported(self):
        co.protect(self.plan, "Antagen")
        actions = self.actions()
        self.assertFalse(actions.check_out(self.group))
        self.assertEqual(co.state(self.group), co.DATABASE)
        text, warning = self.messages[-1]
        self.assertTrue(warning)
        self.assertIn("skrivskyddad", text)
        self.assertIn("Antagen", text)
        self.assertIsNone(co.read_lock(self.plan))

    def test_discarding_asks_and_leaves_the_database_unchanged(self):
        actions = self.actions(check_in=DISCARD)
        actions.check_out(self.group)
        self.assertTrue(actions.check_in(self.group))
        self.assertEqual(self.conn.checkins, [])
        self.assertIn("Kastade", self.messages[-1][0])


class PluginTests(PostgisCase):
    def setUp(self):
        super().setUp()
        self.iface = FakeIface()
        self.iface.active = self.layer("oversiktsplan")
        self.plugin = classFactory(self.iface)
        self.plugin.initGui()
        self.addCleanup(self.plugin.unload)

    def test_the_button_follows_where_the_plan_is(self):
        self.plugin.refresh_tools()
        self.assertEqual(self.plugin.toolbar.act_checkout.text(), "Checka ut")
        self.assertTrue(self.plugin.toolbar.act_checkout.isEnabled())
        with mock.patch.object(CheckoutActions, "ask_yes_no", return_value=True):
            self.assertTrue(self.plugin.toggle_checkout())
        self.assertEqual(self.plugin.toolbar.act_checkout.text(), "Checka in")
        with mock.patch.object(CheckoutActions, "ask_check_in", return_value=CHECK_IN):
            self.assertTrue(self.plugin.toggle_checkout())
        self.assertEqual(co.state(self.group), co.DATABASE)
        self.assertEqual(self.plugin.toolbar.act_checkout.text(), "Checka ut")

    def test_drawing_in_a_database_plan_offers_to_check_it_out_first(self):
        with mock.patch.object(CheckoutActions, "ask_yes_no", return_value=False) as asked:
            self.plugin.draw("polygon")
        asked.assert_called_once()
        self.assertFalse(draft_layers(self.group)["polygon"].isEditable())
        with mock.patch.object(CheckoutActions, "ask_yes_no", return_value=True):
            self.plugin.draw("polygon")
        self.assertEqual(co.state(self.group), co.LOCAL)
        self.assertTrue(draft_layers(self.group)["polygon"].isEditable())

    def test_open_shows_a_menu_with_file_and_database(self):
        from qgis.PyQt.QtWidgets import QMenu

        from rita_oversiktsplan.gui.database_manager_dialog import DatabaseManagerDialog

        texts = []

        def choose_database(menu, *args):
            texts.extend(a.text() for a in menu.actions())
            return menu.actions()[1]

        with mock.patch.object(QMenu, "exec", new=choose_database),                 mock.patch.object(DatabaseManagerDialog, "exec", return_value=False) as dialog:
            self.plugin.open_plan()
        self.assertEqual(texts, ["Lokal fil (GeoPackage)…", "PostGIS-databas…"])
        dialog.assert_called_once()

    def open_from_dialog(self, checkout_requested, lock=None, checked_out=True, plan_ids=("op_2040",), load=True,
                         protection=None):
        with mock.patch("rita_oversiktsplan.plugin.DatabaseManagerDialog") as dialog_cls,                 mock.patch.object(type(self.plugin), "_load", return_value=load) as loaded,                 mock.patch("rita_oversiktsplan.plugin.checkout.read_lock", return_value=lock),                 mock.patch("rita_oversiktsplan.plugin.checkout.read_protection", return_value=protection),                 mock.patch("rita_oversiktsplan.plugin.find_plan_group", return_value=self.group),                 mock.patch.object(self.plugin.checkout, "check_out", return_value=checked_out) as check_out:
            dialog_cls.return_value.exec.return_value = True
            dialog_cls.return_value.selections.return_value = [("planer", "oversiktsplan", p) for p in plan_ids]
            dialog_cls.return_value.checkout_requested = checkout_requested
            result = self.plugin.open_database_manager()
        self.loaded, self.result = loaded, result
        return check_out

    def messages_text(self):
        return [c.args[1] for c in self.iface.bar.pushMessage.call_args_list]

    def test_checking_out_from_the_dialog_checks_the_plan_out_without_asking_again(self):
        check_out = self.open_from_dialog(True)
        check_out.assert_called_once_with(self.group, ask=False)
        self.assertTrue(self.result)
        self.assertFalse(any("skrivskyddad" in t for t in self.messages_text()))

    def test_opening_read_only_from_the_dialog_does_not_check_out(self):
        check_out = self.open_from_dialog(False)
        check_out.assert_not_called()
        self.assertTrue(any("skrivskyddad" in t for t in self.messages_text()))

    def test_a_plan_taken_by_someone_else_in_the_meantime_is_opened_read_only(self):
        check_out = self.open_from_dialog(True, lock=other_lock())
        check_out.assert_not_called()
        self.assertTrue(any("anna" in t and "skrivskyddad" in t for t in self.messages_text()))

    def test_a_protected_plan_is_opened_read_only_even_if_checkout_was_asked_for(self):
        protection = co.Protection("anna", "ANNAS-DATOR", "2026-11-01T09:00:00", "Antagen")
        check_out = self.open_from_dialog(True, protection=protection)
        check_out.assert_not_called()
        self.assertTrue(any("skrivskyddad" in t and "anna på ANNAS-DATOR" in t and "Antagen" in t
                            and "Databashanteraren" in t for t in self.messages_text()), self.messages_text())

    def test_several_plans_where_one_is_protected_check_out_the_others(self):
        protection = co.Protection("anna", "ANNAS-DATOR", "2026-11-01T09:00:00", "Antagen")
        values = {"a": None, "b": protection}
        with mock.patch("rita_oversiktsplan.plugin.DatabaseManagerDialog") as dialog_cls, \
                mock.patch.object(type(self.plugin), "_load", return_value=True), \
                mock.patch("rita_oversiktsplan.plugin.checkout.read_lock", return_value=None), \
                mock.patch("rita_oversiktsplan.plugin.checkout.read_protection",
                           side_effect=lambda plan: values[plan.plan_id]), \
                mock.patch("rita_oversiktsplan.plugin.find_plan_group", return_value=self.group), \
                mock.patch.object(self.plugin.checkout, "check_out", return_value=True) as check_out:
            dialog_cls.return_value.exec.return_value = True
            dialog_cls.return_value.selections.return_value = [("planer", "oversiktsplan", p) for p in ("a", "b")]
            dialog_cls.return_value.checkout_requested = True
            self.plugin.open_database_manager()
        self.assertEqual(check_out.call_count, 1, "bara den oskyddade planen checkas ut")
        self.assertTrue(any("b är skrivskyddad" in t for t in self.messages_text()), self.messages_text())

    def test_a_declined_or_failed_checkout_leaves_the_plan_open_read_only(self):
        self.open_from_dialog(True, checked_out=False)
        self.assertTrue(any("skrivskyddad" in t for t in self.messages_text()))

    def test_several_plans_are_opened_in_turn(self):
        check_out = self.open_from_dialog(False, plan_ids=("a", "b", "c"))
        self.assertEqual([c.args[0].plan_id for c in self.loaded.call_args_list], ["a", "b", "c"])
        check_out.assert_not_called()
        self.assertTrue(any("Öppnade 3 planer" in t and "3 skrivskyddade" in t for t in self.messages_text()))

    def test_several_plans_can_be_checked_out_one_after_the_other(self):
        check_out = self.open_from_dialog(True, plan_ids=("a", "b"))
        self.assertEqual(check_out.call_count, 2)
        self.assertTrue(any("2 utcheckade" in t for t in self.messages_text()))

    def test_the_map_is_not_redrawn_while_several_plans_load(self):
        canvas = self.iface.mapCanvas()
        with mock.patch.object(canvas, "freeze", wraps=canvas.freeze) as freeze:
            self.open_from_dialog(False, plan_ids=("a", "b"))
            self.assertEqual([c.args[0] for c in freeze.call_args_list], [True, False])
        self.assertFalse(canvas.isFrozen(), "kartan är upptinad igen")

    def test_a_plan_that_cannot_be_opened_does_not_stop_the_others(self):
        with mock.patch("rita_oversiktsplan.plugin.DatabaseManagerDialog") as dialog_cls,                mock.patch.object(type(self.plugin), "_load", side_effect=[True, False, True]) as loaded,                 mock.patch("rita_oversiktsplan.plugin.checkout.read_lock", return_value=None), mock.patch("rita_oversiktsplan.plugin.checkout.read_protection", return_value=None):
            dialog_cls.return_value.exec.return_value = True
            dialog_cls.return_value.selections.return_value = [("planer", "oversiktsplan", p) for p in "abc"]
            dialog_cls.return_value.checkout_requested = False
            self.assertTrue(self.plugin.open_database_manager())
        self.assertEqual(loaded.call_count, 3)
        self.assertTrue(any("Öppnade 2 planer" in t for t in self.messages_text()))

    def test_nothing_is_opened_when_the_dialog_is_cancelled(self):
        with mock.patch("rita_oversiktsplan.plugin.DatabaseManagerDialog") as dialog_cls,                 mock.patch.object(type(self.plugin), "_load") as loaded:
            dialog_cls.return_value.exec.return_value = False
            self.assertFalse(self.plugin.open_database_manager())
        loaded.assert_not_called()

    def test_a_new_plan_can_be_created_in_the_database(self):
        def fill(dialog):
            dialog.kommun.set_kommun("Eskilstuna")
            dialog.titel.setText("ÖP Nord")
            dialog.use_postgis.setChecked(True)
            dialog.municipality_area.setChecked(False)  # inget nätverk i testerna
            dialog.folder.setFilePath(str(self.dir))
            self.assertTrue(dialog.is_valid())
            return True

        created = []
        with mock.patch.object(NewPlanDialog, "exec", new=fill), \
                mock.patch.object(storage, "create_postgis_plan",
                                  side_effect=lambda *a: created.append(a) or storage.PostgisStorage(*a[:3])), \
                mock.patch.object(type(self.plugin), "_load", return_value=True):
            self.plugin.new_plan()
        self.assertEqual(created[0][:3], ("planer", "oversiktsplan", "op_nord"))

    def test_the_database_button_is_shown_for_a_plan_in_the_database(self):
        self.plugin.refresh_tools()
        self.assertTrue(self.plugin.toolbar.act_checkout.isVisible())


if __name__ == "__main__":
    unittest.main()

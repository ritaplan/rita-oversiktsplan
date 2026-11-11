"""Flytta planer mellan en GeoPackage och en databas, och kopiera och ta bort dem, samt databashanterarens knappar (kräver
QGIS). Samma upplägg som i Rita Detaljplan.

Ingen riktig databas används: låtsasanslutningar tar emot och tolkar den SQL som pluginet skickar. Att SQL:en fungerar mot en
riktig PostgreSQL med PostGIS är därför inte provat här, men importen använder samma SQL som skapandet av en ny plan och
incheckningen."""
import json
import re
import sqlite3
import sys
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qgis_app import get_app  # noqa: E402

get_app()

from qgis.PyQt.QtCore import QItemSelectionModel  # noqa: E402

from rita_oversiktsplan import json_transfer  # noqa: E402
from rita_oversiktsplan.core import checkout as co  # noqa: E402
from rita_oversiktsplan.core import geopackage, model, storage, transfer  # noqa: E402
from rita_oversiktsplan.core.plan_overview import PlanRow  # noqa: E402
from rita_oversiktsplan.gui import database_manager_dialog as manager  # noqa: E402
from rita_oversiktsplan.gui.copy_plan_dialog import CopyPlanDialog, CopyValues  # noqa: E402
from rita_oversiktsplan.gui.database_manager_dialog import ROW_ROLE, DatabaseManagerDialog  # noqa: E402
from rita_oversiktsplan.gui.import_plan_dialog import ImportPlanDialog, ImportValues  # noqa: E402
from test_open_dialog import detailed  # noqa: E402
from test_postgis import PLAN, PostgisCase, other_lock  # noqa: E402

TABLES = {storage.db_name(t.name): t for t in storage.tables()}


class ImportPg:
    """Låtsasdatabas för import och kopiering: håller scheman och planer, räknar raderna i importens SQL och tar emot
    borttagningen vid en misslyckad import."""

    def __init__(self, schemas=(), epsg=None, plans=()):
        self.sql = []
        self.schemas = list(schemas)  # scheman skapade med pluginet
        self.epsg = epsg
        self.plans = set(plans)
        self.inserted = {}
        self.writes = []  # transaktionerna som skrev planens rader
        self.deleted = []
        self.count_override = {}

    def uri(self):
        return "dbname='planer' host=localhost port=5432 user='eric' sslmode=disable"

    def executeSql(self, sql):  # noqa: N802 - samma namn som QGIS anslutningar
        self.sql.append(sql)
        if "postgis_version" in sql:
            return [["3.4"]]
        if "information_schema.tables" in sql:
            return [[s] for s in self.schemas]
        if "information_schema.schemata" in sql:
            return [[s] for s in self.schemas]
        if sql.startswith('SELECT "value" FROM') and "rita_oversiktsplan_schema" in sql:
            return [[str(self.epsg)]] if self.epsg else []
        if sql.startswith("SELECT 1 FROM"):
            plan = re.search(r"\"plan\" = '([^']*)'", sql).group(1)
            return [[1]] if plan in self.plans else []
        if sql.startswith("DO $op") and "INSERT INTO" in sql:  # planens rader skrivs
            plan = re.search(r"\"plan\" = '([^']*)'", sql).group(1)
            self.writes.append(sql)
            self.plans.add(plan)
            for part in sql.split("INSERT INTO ")[1:]:
                table = TABLES[re.match(r'"[^"]+"\."([^"]+)"', part).group(1)].name
                self.inserted[table] = self.inserted.get(table, 0) + part.count(f"('{plan}', ")
            return []
        match = re.match(r'SELECT count\(\*\) FROM "[^"]+"\."([^"]+)"', sql)
        if match:
            name = TABLES[match.group(1)].name
            return [[self.count_override.get(name, self.inserted.get(name, 0))]]
        if sql.startswith("DELETE FROM"):
            self.deleted.append(sql)
            plan = re.search(r"\"plan\" = '([^']*)'", sql).group(1)
            self.plans.discard(plan)
            return []
        return []


def counts_in(path):
    """Antal rader per tabell i en GeoPackage."""
    return {table.name: len(storage.read_file_rows(path, table)) for table in storage.tables()}


class ImportTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.path = geopackage.create_geopackage(self.dir / "ÖP 2040.gpkg", PLAN)
        self.expected = counts_in(self.path)
        self.conn = ImportPg()

    def import_it(self, path=None, plan_id="ny_plan", schema="op_ny"):
        return transfer.import_plan(path or self.path, "db", schema, plan_id, self.conn)

    def test_the_plan_is_added_with_every_row_and_the_schema_gets_the_coordinate_system(self):
        result = self.import_it()
        self.assertEqual(result.counts, self.expected)
        self.assertEqual(result.total, sum(self.expected.values()))
        self.assertGreater(self.expected[model.OVERSIKTSPLAN.name], 0, "planens uppgifter följer med")
        self.assertEqual(result.plan, storage.PostgisStorage("db", "op_ny", "ny_plan"))
        self.assertIn("'epsg'", "".join(self.conn.sql), "schemat får sitt koordinatsystem")
        self.assertEqual(len(self.conn.writes), 1, "alla rader skrivs i en enda transaktion")

    def test_the_details_of_a_checked_out_copy_are_not_taken_into_the_database(self):
        storage.GeoPackageStorage(self.path).write_meta({"checkout_token": "abc", "checkout_storage": "x",
                                                         "checkout_since": "2026-01-01T00:00:00"})
        self.import_it()
        self.assertNotIn("checkout_token", self.conn.writes[0])
        self.assertNotIn("checkout_since", self.conn.writes[0])

    def test_a_protection_in_the_file_does_not_make_the_new_plan_protected(self):
        storage.GeoPackageStorage(self.path).write_meta({"skrivskydd": "{}"})
        self.import_it()
        self.assertNotIn("skrivskydd", self.conn.writes[0])

    def test_a_row_count_that_does_not_match_removes_the_plan_again(self):
        self.conn.count_override = {model.OVERSIKTSPLAN.name: self.expected[model.OVERSIKTSPLAN.name] + 1}
        with self.assertRaisesRegex(transfer.TransferError, "inte komplett"):
            self.import_it()
        self.assertEqual(len(self.conn.deleted), len(storage.tables()), "alla tabeller städas")
        self.assertNotIn("ny_plan", self.conn.plans)

    def test_a_plan_id_that_is_taken_is_refused_and_the_existing_plan_is_left_alone(self):
        self.conn = ImportPg(schemas=["op_ny"], epsg=model.EPSG, plans=["ny_plan"])
        with self.assertRaisesRegex(storage.PostgisError, "finns redan en plan"):
            self.import_it()
        self.assertEqual(self.conn.deleted, [])
        self.assertEqual(self.conn.writes, [])

    def test_a_schema_with_another_coordinate_system_is_refused_without_changes(self):
        self.conn = ImportPg(schemas=["op_ny"], epsg=3007 if model.EPSG != 3007 else 3006)
        with self.assertRaisesRegex(storage.PostgisError, "koordinatsystem"):
            self.import_it()
        self.assertEqual((self.conn.deleted, self.conn.writes), ([], []))

    def test_a_file_that_is_no_plan_is_refused_before_the_database_is_touched(self):
        text = self.dir / "inte_en_plan.gpkg"
        text.write_text("detta är ingen databas")
        for path in (text, self.dir / "finns_inte.gpkg"):
            with self.assertRaisesRegex(transfer.TransferError, "ingen översiktsplan"):
                self.import_it(path)
        self.assertEqual(self.conn.sql, [])

    def set_version(self, value):
        with closing(sqlite3.connect(str(self.path))) as con:
            con.execute(f'UPDATE "{model.META_TABLE}" SET value = ? WHERE key = ?', (str(value), "schema_version"))
            con.commit()

    def test_a_plan_made_with_a_newer_version_is_refused(self):
        self.set_version(int(model.SCHEMA_VERSION) + 1)
        with self.assertRaisesRegex(transfer.TransferError, "nyare version"):
            self.import_it()
        self.assertEqual(self.conn.sql, [])

    def test_an_older_plan_must_be_opened_in_the_plugin_first(self):
        self.set_version(3)
        with self.assertRaisesRegex(transfer.TransferError, "äldre version.*Öppna den i pluginet"):
            self.import_it()
        self.assertEqual(self.conn.sql, [])


class ExportTests(PostgisCase):
    """Exporterar planen i 'databasen' (en GeoPackage bakom en låtsasanslutning)."""

    def test_a_plan_is_saved_as_a_new_geopackage_with_every_row(self):
        path = transfer.export_plan(self.plan, self.dir / "ut.gpkg")
        meta = geopackage.read_meta(path)
        self.assertEqual(meta["schema_version"], geopackage.read_meta(self.database)["schema_version"])
        self.assertFalse([key for key in meta if key.startswith("checkout")])
        self.assertEqual(counts_in(path), counts_in(self.database))

    def test_the_file_is_complete_without_its_wal_file(self):
        path = transfer.export_plan(self.plan, self.dir / "ut.gpkg")
        wal = Path(str(path) + "-wal")
        self.assertFalse(wal.exists() and wal.stat().st_size > 0)

    def test_a_plan_checked_out_by_someone_else_is_exported_as_it_is_and_stays_locked(self):
        self.conn.meta["checkout"] = other_lock().to_json()
        path = transfer.export_plan(self.plan, self.dir / "ut.gpkg")
        self.assertFalse([key for key in geopackage.read_meta(path) if key.startswith("checkout")])
        self.assertEqual(co.read_lock(self.plan), other_lock())

    def test_a_protected_plan_can_be_exported_and_the_file_carries_no_protection(self):
        self.conn.meta["skrivskydd"] = co.Protection("anna", "ANNAS-DATOR", "2026-11-01T09:00:00", "Laga kraft").to_json()
        path = transfer.export_plan(self.plan, self.dir / "ut.gpkg")
        self.assertNotIn("skrivskydd", geopackage.read_meta(path))
        self.assertIn("skrivskydd", self.conn.meta, "originalet är fortfarande skyddat")

    def test_a_file_that_exists_is_never_overwritten(self):
        target = self.dir / "ut.gpkg"
        target.write_text("min egen fil")
        with self.assertRaisesRegex(transfer.TransferError, "finns redan"):
            transfer.export_plan(self.plan, target)
        self.assertEqual(target.read_text(), "min egen fil")

    def test_a_failed_export_leaves_no_half_file(self):
        target = self.dir / "ut.gpkg"

        def broken(_source, _target, _skip=None):  # en vanlig funktion: en mock sparar lagren och håller filen öppen
            raise co.CheckoutError("tabellen är trasig")

        with mock.patch.object(co, "_copy_rows", broken):
            with self.assertRaisesRegex(transfer.TransferError, "trasig"):
                transfer.export_plan(self.plan, target)
        self.assertEqual([p.name for p in self.dir.glob("ut.gpkg*")], [])

    def test_a_plan_that_is_not_in_the_database_cannot_be_exported(self):
        self.conn.meta.clear()
        target = self.dir / "ut.gpkg"
        with self.assertRaisesRegex(transfer.TransferError, "finns inte"):
            transfer.export_plan(self.plan, target)
        self.assertFalse(target.exists())

    def test_file_names_are_the_plan_ids_with_the_schema_in_front_when_two_plans_share_an_id(self):
        plans = [storage.PostgisStorage("db", "a", "kv"), storage.PostgisStorage("db", "b", "kv"),
                 storage.PostgisStorage("db", "a", "annan")]
        names = [path.name for _plan, path in transfer.unique_export_paths(self.dir, plans)]
        self.assertEqual(names, ["a_kv.gpkg", "b_kv.gpkg", "annan.gpkg"])
        self.assertEqual([p.name for _plan, p in transfer.unique_export_paths(self.dir, plans[2:], ".json")], ["annan.json"])


class DeliveryExportTests(PostgisCase):
    """Exporterar planen som en leverans (JSON), utan att röra projektet eller databasen."""

    def test_a_plan_is_exported_as_a_delivery_in_the_format_of_the_open_plan(self):
        from rita_oversiktsplan.core import export_lm
        path = json_transfer.export_delivery(self.plan, self.dir / "ut.json")
        exported = json.loads(path.read_text(encoding="utf-8"))
        opened, _problems = export_lm.export(self.group)
        self.assertEqual(exported["feature:mediatyp"], opened["feature:mediatyp"])
        self.assertEqual(export_lm.counts(exported), export_lm.counts(opened))

    def test_the_open_project_and_the_database_are_untouched(self):
        before = (sorted(self.conn.meta.items()), len(self.project.mapLayers()))
        json_transfer.export_delivery(self.plan, self.dir / "ut.json")
        self.assertEqual((sorted(self.conn.meta.items()), len(self.project.mapLayers())), before)

    def test_a_file_that_exists_is_never_overwritten(self):
        target = self.dir / "ut.json"
        target.write_text("min egen fil")
        with self.assertRaisesRegex(transfer.TransferError, "finns redan"):
            json_transfer.export_delivery(self.plan, target)
        self.assertEqual(target.read_text(), "min egen fil")

    def test_a_plan_that_is_not_in_the_database_cannot_be_exported(self):
        self.conn.meta.clear()
        target = self.dir / "ut.json"
        with self.assertRaisesRegex(transfer.TransferError, "finns inte"):
            json_transfer.export_delivery(self.plan, target)
        self.assertFalse(target.exists())


class CopyTests(PostgisCase):
    """Kopierar planen i 'databasen' till en annan databas."""

    def setUp(self):
        super().setUp()
        self.target = ImportPg()

    def test_a_plan_is_copied_with_every_row_to_another_database(self):
        result = transfer.copy_plan(self.plan, "db2", "op_kopia", "kopia", self.target)
        self.assertEqual(result.counts, counts_in(self.database))
        self.assertEqual(result.plan, storage.PostgisStorage("db2", "op_kopia", "kopia"))
        self.assertEqual(len(self.target.writes), 1)

    def test_a_protected_plan_can_be_copied_and_the_copy_is_not_protected(self):
        protection = co.Protection("anna", "ANNAS-DATOR", "2026-11-01T09:00:00", "Antagen")
        self.conn.meta["skrivskydd"] = protection.to_json()
        transfer.copy_plan(self.plan, "db2", "op_kopia", "kopia", self.target)
        self.assertNotIn("skrivskydd", self.target.writes[0], "kopian är en ny plan som får ändras")
        self.assertEqual(co.read_protection(self.plan), protection, "originalet är fortfarande skyddat")

    def test_the_source_is_not_changed_and_a_lock_is_not_copied(self):
        self.conn.meta["checkout"] = other_lock().to_json()
        before = len(self.conn.sql)
        transfer.copy_plan(self.plan, "db2", "op_kopia", "kopia", self.target)
        self.assertEqual(co.read_lock(self.plan), other_lock(), "den andras lås är orört")
        self.assertNotIn('"checkout"', self.target.writes[0].replace("'checkout'", "x").replace('"checkout_', ""))
        self.assertFalse([q for q in self.conn.sql[before:] if q.startswith(("DELETE", "INSERT", "DO"))],
                         "inget skrivs till källan")

    def test_a_plan_id_that_is_taken_is_refused_and_nothing_is_overwritten(self):
        self.target = ImportPg(schemas=["op_kopia"], epsg=model.EPSG, plans=["kopia"])
        with self.assertRaisesRegex(storage.PostgisError, "finns redan en plan"):
            transfer.copy_plan(self.plan, "db2", "op_kopia", "kopia", self.target)
        self.assertEqual((self.target.deleted, self.target.writes), ([], []))


class DeletePg:
    """Låtsasdatabas för borttagning: planernas metadata (med lås) per schema, och borttagningens SQL."""

    def __init__(self, meta):
        self.meta = meta  # schema -> plan -> {nyckel: värde}
        self.sql = []
        self.removals = []

    def uri(self):
        return "dbname='planer' host=localhost port=5432 user='eric' sslmode=disable"

    def executeSql(self, sql):  # noqa: N802 - samma namn som QGIS anslutningar
        self.sql.append(sql)
        schema = (re.search(r'"([^"]+)"\."', sql) or [None, ""])[1]
        if sql.startswith('SELECT "key", "value" FROM'):
            plan = re.search(r"\"plan\" = '([^']*)'", sql).group(1)
            return [[k, v] for k, v in self.meta.get(schema, {}).get(plan, {}).items()]
        if sql.startswith("SELECT 1 FROM"):
            plan = re.search(r"\"plan\" = '([^']*)'", sql).group(1)
            return [[1]] if plan in self.meta.get(schema, {}) else []
        if sql.startswith("DELETE FROM") and "'skrivskydd'" in sql:  # bryt skrivskyddet
            plan = re.search(r"\"plan\" = '([^']*)'", sql).group(1)
            self.meta[schema][plan].pop("skrivskydd", None)
            return []
        if sql.startswith("DO $op") and "LOCK TABLE" in sql and "kan inte skrivskyddas" in sql:  # skrivskydda planen
            plan, value = re.search(r"VALUES \('([^']*)', 'skrivskydd', '(.*)'\); END IF", sql).groups()
            if "checkout" in self.meta[schema][plan]:
                raise RuntimeError("Planen är utcheckad och kan inte skrivskyddas. Checka in den eller bryt låset först.")
            self.meta[schema][plan].setdefault("skrivskydd", value.replace("''", "'"))
            return []
        if sql.startswith("DO $op") and "RAISE EXCEPTION" in sql and "LOCK TABLE" in sql:
            plan = re.search(r"\"plan\" = '([^']*)'", sql).group(1)
            if "checkout" in self.meta[schema][plan]:
                raise RuntimeError(transfer.LOCKED_MESSAGE)
            if "skrivskydd" in self.meta[schema][plan]:
                raise RuntimeError(transfer.PROTECTED_MESSAGE)
            self.removals.append(sql)
            del self.meta[schema][plan]
        return []


class DeleteTests(unittest.TestCase):
    def setUp(self):
        self.conn = DeletePg({"op_a": {"op_1": {"epsg": "3006", "schema_version": "5"},
                                       "op_2": {"epsg": "3006", "schema_version": "5"}}})
        self.plan = storage.PostgisStorage("db", "op_a", "op_1", self.conn)

    def test_a_plan_is_removed_from_every_table_in_one_transaction_and_other_plans_are_untouched(self):
        transfer.delete_plan(self.plan)
        self.assertNotIn("op_1", self.conn.meta["op_a"])
        self.assertIn("op_2", self.conn.meta["op_a"])
        sql, = self.conn.removals
        self.assertIn(f'LOCK TABLE "op_a"."{model.META_TABLE}" IN EXCLUSIVE MODE', sql)
        for table in storage.tables():
            self.assertIn(f'DELETE FROM "op_a"."{storage.db_name(table.name)}" WHERE "plan" = \'op_1\'', sql)
        self.assertNotIn("op_2", sql)

    def test_a_checked_out_plan_is_never_removed_not_even_the_users_own(self):
        for held in (other_lock(), co.new_lock()):
            self.conn.meta["op_a"]["op_1"]["checkout"] = held.to_json()
            with self.assertRaisesRegex(transfer.TransferError, "utcheckad av .*bryt låset"):
                transfer.delete_plan(self.plan)
        self.assertIn("op_1", self.conn.meta["op_a"])
        self.assertEqual(self.conn.removals, [])

    def test_a_lock_taken_just_before_the_removal_stops_it(self):
        """Någon hinner checka ut planen mellan kontrollen och borttagningen: databasen vägrar."""
        self.conn.meta["op_a"]["op_1"]["checkout"] = other_lock().to_json()
        with mock.patch.object(co, "read_lock", return_value=None):
            with self.assertRaisesRegex(transfer.TransferError, "utcheckad och kan inte tas bort"):
                transfer.delete_plan(self.plan)
        self.assertIn("op_1", self.conn.meta["op_a"])

    def test_a_protected_plan_is_never_removed_until_the_protection_is_lifted(self):
        co.protect(self.plan, "Antagen")
        with self.assertRaisesRegex(transfer.TransferError, "skrivskyddad av .*Antagen.*Bryt skrivskyddet"):
            transfer.delete_plan(self.plan)
        self.assertIn("op_1", self.conn.meta["op_a"])
        self.assertEqual(self.conn.removals, [])
        co.unprotect(self.plan)
        transfer.delete_plan(self.plan)
        self.assertNotIn("op_1", self.conn.meta["op_a"])

    def test_a_protection_set_just_before_the_removal_stops_it(self):
        """Någon hinner skydda planen mellan kontrollen och borttagningen: databasen vägrar."""
        self.conn.meta["op_a"]["op_1"]["skrivskydd"] = co.Protection("anna", "ANNAS-DATOR", "2026-11-01T09:00:00").to_json()
        with mock.patch.object(co, "read_protection", return_value=None):
            with self.assertRaisesRegex(transfer.TransferError, "skrivskyddad och kan inte tas bort"):
                transfer.delete_plan(self.plan)
        self.assertIn("op_1", self.conn.meta["op_a"])

    def test_the_removal_sql_checks_the_protection_while_the_meta_table_is_locked(self):
        sql = transfer.delete_sql(self.plan)
        self.assertLess(sql.index("LOCK TABLE"), sql.index("'skrivskydd'"))
        self.assertLess(sql.index("'skrivskydd'"), sql.index('DELETE FROM "op_a"."'))

    def test_a_plan_that_does_not_exist_cannot_be_removed(self):
        with self.assertRaisesRegex(transfer.TransferError, "finns inte"):
            transfer.delete_plan(storage.PostgisStorage("db", "op_a", "spöke", self.conn))
        self.assertEqual(self.conn.removals, [])

    def test_a_plan_that_is_still_there_after_the_removal_is_reported(self):
        with mock.patch.object(storage, "plan_exists", return_value=True):
            with self.assertRaisesRegex(transfer.TransferError, "finns kvar"):
                transfer.delete_plan(self.plan)


class CopyPlanDialogTests(unittest.TestCase):
    def rows(self, *plan_ids):
        return [PlanRow("a", "op_a", plan_id, titel=plan_id.upper()) for plan_id in plan_ids]

    def dialog(self, rows):
        conn = ImportPg(schemas=["op_a", "op_b"])
        dialog = CopyPlanDialog(None, {"a": conn}, rows)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def ok(self, dialog):
        return dialog.buttons.button(dialog.buttons.StandardButton.Ok).isEnabled()

    def test_a_copy_in_the_same_place_suggests_another_plan_id_and_a_copy_elsewhere_keeps_the_id(self):
        dialog = self.dialog(self.rows("op_1"))
        self.assertEqual(dialog.plan_id.text(), "op_1_kopia")
        self.assertTrue(self.ok(dialog))
        dialog.target.schema.setCurrentText("op_b")
        self.assertEqual(dialog.plan_id.text(), "op_1")
        self.assertEqual(dialog.values(), CopyValues("a", "op_b", ["op_1"]))

    def test_a_plan_cannot_be_copied_onto_itself(self):
        dialog = self.dialog(self.rows("op_1"))
        dialog.plan_id.textEdited.emit("op_1")
        dialog.plan_id.setText("op_1")
        self.assertFalse(self.ok(dialog))
        self.assertIn("finns redan där", dialog.info.text())

    def test_several_plans_keep_their_plan_ids_and_need_another_schema(self):
        dialog = self.dialog(self.rows("op_1", "op_2"))
        self.assertEqual(dialog.windowTitle(), "Kopiera 2 planer")
        self.assertFalse(self.ok(dialog), "samma schema: planerna skulle krocka med sig själva")
        dialog.target.schema.setCurrentText("op_b")
        self.assertTrue(self.ok(dialog))
        self.assertEqual(dialog.values().plan_ids, ["op_1", "op_2"])


class ImportPlanDialogTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def dialog(self, **kwargs):
        dialog = ImportPlanDialog(None, {"a": ImportPg(schemas=["op_a", "op_b"])}, **kwargs)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def ok(self, dialog):
        return dialog.buttons.button(dialog.buttons.StandardButton.Ok).isEnabled()

    def test_nothing_can_be_imported_before_a_file_is_chosen(self):
        self.assertFalse(self.ok(self.dialog()))

    def test_a_plan_file_gives_a_suggested_plan_id_and_shows_its_coordinate_system(self):
        dialog = self.dialog()
        path = geopackage.create_geopackage(self.dir / "ÖP 2040.gpkg", PLAN)
        dialog.file.setFilePath(str(path))
        self.assertEqual(dialog.plan_id.text(), "op_2040")
        self.assertIn("EPSG:", dialog.info.text())
        self.assertTrue(self.ok(dialog))
        self.assertEqual(dialog.values(), ImportValues(path, "a", "op_a", "op_2040"))

    def test_a_file_that_is_no_plan_is_explained_and_cannot_be_imported(self):
        dialog = self.dialog()
        other = self.dir / "annat.gpkg"
        other.write_text("inte en plan")
        dialog.file.setFilePath(str(other))
        self.assertIn("ingen översiktsplan", dialog.info.text())
        self.assertFalse(self.ok(dialog))

    def test_the_schema_list_holds_the_databases_schemas_and_a_new_schema_can_be_written(self):
        dialog = self.dialog(schema="op_b")
        self.assertEqual([dialog.schema.itemText(i) for i in range(dialog.schema.count())], ["op_a", "op_b"])
        self.assertEqual(dialog.schema.currentText(), "op_b")
        dialog.file.setFilePath(str(geopackage.create_geopackage(self.dir / "p.gpkg", PLAN)))
        dialog.schema.setCurrentText("Ogiltigt Namn")
        self.assertFalse(self.ok(dialog), "schemanamnet är ogiltigt")
        dialog.schema.setCurrentText("nytt_schema")
        self.assertTrue(self.ok(dialog))


class DatabaseManagerTests(unittest.TestCase):
    def manager(self, connections=None):
        conn = detailed()
        dialog = DatabaseManagerDialog(None, {"a": conn} if connections is None else connections)
        self.addCleanup(dialog.deleteLater)
        return dialog, conn

    def select(self, dialog, *plan_ids):
        dialog.table.clearSelection()
        visible = [dialog.model.item(dialog.proxy.mapToSource(dialog.proxy.index(i, 0)).row(), 0).data(ROW_ROLE).plan_id
                   for i in range(dialog.proxy.rowCount())]
        for plan_id in plan_ids:
            dialog.table.selectionModel().select(
                dialog.proxy.index(visible.index(plan_id), 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)

    def test_the_dialog_is_the_database_manager_with_import_and_export_buttons(self):
        dialog, _conn = self.manager()
        self.assertEqual(dialog.windowTitle(), "Databashanteraren")
        self.assertEqual((dialog.import_plan.text(), dialog.export_plans.text()), ("Importera plan…", "Exportera valda"))
        self.assertEqual([a.text() for a in dialog.export_plans.menu().actions()],
                         ["Som GeoPackage (.gpkg)…", "Som leverans, JSON (.json)…"])

    def protected_manager(self):
        dialog, conn = self.manager()
        conn.plans["op_a"]["op_10"]["protection"] = co.Protection("anna", "ANNAS-DATOR", "2026-11-01T09:00:00", "Antagen")
        dialog.reload()
        return dialog, conn

    def rows_by_id(self, dialog):
        return {row.plan_id: row for row in dialog._rows}

    def shown(self, dialog):
        return sorted(dialog.model.item(dialog.proxy.mapToSource(dialog.proxy.index(i, 0)).row(), 0).data(ROW_ROLE).plan_id
                      for i in range(dialog.proxy.rowCount()))

    def test_the_overview_shows_which_plans_are_protected_and_by_whom(self):
        dialog, _conn = self.protected_manager()
        rows = self.rows_by_id(dialog)
        self.assertFalse(rows["op_2"].protected)
        self.assertTrue(rows["op_10"].protected)
        self.assertEqual(rows["op_10"].protection.reason, "Antagen")
        shield, key = manager.COLUMN_FIELDS.index("skrivskydd"), manager.COLUMN_FIELDS.index("plan_id")
        texts = {dialog.model.item(r, key).text(): dialog.model.item(r, shield).text() for r in range(dialog.model.rowCount())}
        self.assertEqual(texts, {"op_10": "Skrivskyddad", "op_2": "", "gammal": ""})
        row = next(r for r in range(dialog.model.rowCount()) if dialog.model.item(r, key).text() == "op_10")
        self.assertIn("Skrivskyddad av anna på ANNAS-DATOR", dialog.model.item(row, shield).toolTip())

    def test_the_filter_shows_only_protected_or_only_editable_plans(self):
        dialog, _conn = self.protected_manager()
        self.assertEqual(self.shown(dialog), ["gammal", "op_10", "op_2"])
        dialog.filter_protect.setCurrentIndex(dialog.filter_protect.findData(manager.PROTECTED))
        self.assertEqual(self.shown(dialog), ["op_10"])
        dialog.filter_protect.setCurrentIndex(dialog.filter_protect.findData(manager.EDITABLE))
        self.assertEqual(self.shown(dialog), ["gammal", "op_2"])

    def test_the_protect_buttons_follow_the_selection(self):
        dialog, _conn = self.protected_manager()  # op_10 är skyddad och ledig, op_2 utcheckad av någon annan
        buttons = (dialog.protect_plans, dialog.unprotect_plans, dialog.delete_plans, dialog.open_checkout, dialog.open_readonly)
        self.assertEqual([b.isEnabled() for b in buttons], [False, False, False, False, False], "inget valt")
        self.select(dialog, "op_10")
        self.assertEqual([b.isEnabled() for b in buttons], [False, True, False, False, True],
                         "skyddad: kan inte tas bort eller checkas ut, men öppnas skrivskyddad")
        self.select(dialog, "op_2")
        self.assertEqual([b.isEnabled() for b in buttons], [True, False, False, False, True], "utcheckad och oskyddad")
        self.select(dialog, "op_10", "op_2")
        self.assertEqual([b.isEnabled() for b in buttons], [True, True, False, False, True], "en skyddad bland de valda")
        free, _conn = self.manager()
        self.select(free, "op_10")
        self.assertEqual([b.isEnabled() for b in (free.protect_plans, free.unprotect_plans, free.delete_plans, free.open_checkout)],
                         [True, False, True, True], "ledig och oskyddad")

    def test_the_hint_explains_why_a_protected_plan_cannot_be_checked_out(self):
        dialog, _conn = self.protected_manager()
        self.select(dialog, "op_10")
        self.assertIn("skrivskyddad", dialog.hint.text())
        self.assertIn("Antagen", dialog.hint.text())

    def test_a_protected_plan_is_not_checked_out_from_the_dialog(self):
        dialog, _conn = self.protected_manager()
        self.select(dialog, "op_10")
        dialog._accept_with(True)
        self.assertFalse(dialog.checkout_requested)
        self.assertNotEqual(dialog.result(), dialog.DialogCode.Accepted)

    def test_a_protected_plan_is_never_passed_to_the_removal(self):
        dialog, _conn = self.protected_manager()
        self.select(dialog, "op_10")
        with mock.patch.object(manager.transfer, "delete_plan") as deleted, \
                mock.patch.object(dialog, "_confirm_delete") as confirm:
            dialog._delete_plans()
        deleted.assert_not_called()
        confirm.assert_not_called()

    def test_selected_plans_are_protected_with_the_reason_and_the_list_is_reloaded(self):
        dialog, _conn = self.manager()
        self.select(dialog, "op_10", "gammal")
        with mock.patch.object(dialog, "_ask_protect", return_value="Antagen") as ask, \
                mock.patch.object(manager.checkout, "protect") as protect:
            dialog.protect_plans.click()
        self.assertEqual(sorted(r.plan_id for r in ask.call_args.args[0]), ["gammal", "op_10"])
        self.assertEqual(sorted((c.args[0].plan_id, c.args[1]) for c in protect.call_args_list),
                         [("gammal", "Antagen"), ("op_10", "Antagen")])
        self.assertIn("Skrivskyddade 2 av 2 planer", dialog.notice.text())
        self.assertEqual(dialog.error.text(), "")

    def test_cancelling_the_question_protects_nothing(self):
        dialog, _conn = self.manager()
        self.select(dialog, "op_10")
        with mock.patch.object(dialog, "_ask_protect", return_value=None), \
                mock.patch.object(manager.checkout, "protect") as protect:
            dialog.protect_plans.click()
        protect.assert_not_called()

    def test_plans_that_are_already_protected_are_left_out_when_protecting(self):
        dialog, _conn = self.protected_manager()
        self.select(dialog, "op_10", "gammal")
        with mock.patch.object(dialog, "_ask_protect", return_value="") as ask, \
                mock.patch.object(manager.checkout, "protect") as protect:
            dialog.protect_plans.click()
        self.assertEqual([r.plan_id for r in ask.call_args.args[0]], ["gammal"])
        self.assertEqual([c.args[0].plan_id for c in protect.call_args_list], ["gammal"])

    def test_a_plan_that_cannot_be_protected_is_reported_and_the_others_are_still_protected(self):
        dialog, _conn = self.manager()
        self.select(dialog, "op_10", "gammal")

        def protect(plan, reason):
            if plan.plan_id == "gammal":
                raise manager.checkout.CheckoutError("Planen är utcheckad och kan inte skrivskyddas.")

        with mock.patch.object(dialog, "_ask_protect", return_value=""), \
                mock.patch.object(manager.checkout, "protect", side_effect=protect):
            dialog.protect_plans.click()
        self.assertIn("Skrivskyddade 1 av 2", dialog.notice.text())
        self.assertIn("Gammal ÖP: Planen är utcheckad och kan inte skrivskyddas.", dialog.error.text())

    def test_the_protection_is_lifted_only_after_confirming(self):
        dialog, _conn = self.protected_manager()
        self.select(dialog, "op_10")
        with mock.patch.object(dialog, "_confirm_unprotect", return_value=True) as confirm, \
                mock.patch.object(manager.checkout, "unprotect") as lift:
            dialog.unprotect_plans.click()
        self.assertEqual([r.plan_id for r in confirm.call_args.args[0]], ["op_10"])
        lift.assert_called_once()
        self.assertEqual(lift.call_args.args[0].plan_id, "op_10")
        self.assertIn("Bröt skrivskyddet på 1 av 1 planer", dialog.notice.text())

    def test_declining_the_confirmation_leaves_the_protection_alone(self):
        dialog, _conn = self.protected_manager()
        self.select(dialog, "op_10")
        with mock.patch.object(dialog, "_confirm_unprotect", return_value=False), \
                mock.patch.object(manager.checkout, "unprotect") as lift:
            dialog.unprotect_plans.click()
        lift.assert_not_called()

    def test_protecting_and_lifting_work_against_the_database_and_show_in_the_list(self):
        dialog, conn = self.manager()
        self.select(dialog, "op_10")
        with mock.patch.object(dialog, "_ask_protect", return_value="Antagen"):
            dialog.protect_plans.click()
        self.assertTrue(self.rows_by_id(dialog)["op_10"].protected)
        self.assertIn("Antagen", conn.plans["op_a"]["op_10"]["protection"])
        self.select(dialog, "op_10")
        with mock.patch.object(dialog, "_confirm_unprotect", return_value=True):
            dialog.unprotect_plans.click()
        self.assertFalse(self.rows_by_id(dialog)["op_10"].protected)
        self.assertNotIn("protection", conn.plans["op_a"]["op_10"])

    def test_a_checked_out_plan_is_refused_by_the_database_when_protecting(self):
        dialog, conn = self.manager()
        self.select(dialog, "op_2")
        with mock.patch.object(dialog, "_ask_protect", return_value=""):
            dialog.protect_plans.click()
        self.assertEqual(dialog.notice.text(), "")
        self.assertIn("utcheckad och kan inte skrivskyddas", dialog.error.text())
        self.assertNotIn("protection", conn.plans["op_a"]["op_2"])

    def test_the_buttons_follow_the_selection_and_the_locks(self):
        dialog, _conn = self.manager()  # op_10 är ledig, op_2 utcheckad av någon annan
        buttons = (dialog.export_plans, dialog.copy_plans, dialog.delete_plans, dialog.break_locks)
        self.assertEqual([b.isEnabled() for b in buttons], [False, False, False, False], "inget valt")
        self.assertTrue(dialog.import_plan.isEnabled())
        self.select(dialog, "op_10")
        self.assertEqual([b.isEnabled() for b in buttons], [True, True, True, False], "ledig plan")
        self.select(dialog, "op_2")
        self.assertEqual([b.isEnabled() for b in buttons], [True, True, False, True], "utcheckad: kan inte tas bort")
        empty, _ = self.manager(connections={})
        self.assertFalse(empty.import_plan.isEnabled())

    def test_selected_plans_are_exported_as_geopackages_or_deliveries_one_file_each(self):
        dialog, conn = self.manager()
        self.select(dialog, "op_10", "op_2")
        exported = []
        with mock.patch.object(manager.QFileDialog, "getExistingDirectory", return_value="C:/ut"), \
                mock.patch.object(manager.transfer, "export_plan",
                                  side_effect=lambda plan, path: exported.append((plan.plan_id, path.name))):
            dialog.export_geopackage.trigger()
        self.assertEqual(sorted(exported), [("op_10", "op_10.gpkg"), ("op_2", "op_2.gpkg")])
        self.assertIn("Exporterade 2 av 2 planer", dialog.notice.text())
        exported.clear()
        with mock.patch.object(manager.QFileDialog, "getExistingDirectory", return_value="C:/ut"), \
                mock.patch.object(manager.json_transfer, "export_delivery",
                                  side_effect=lambda plan, path: exported.append((plan.plan_id, path.name))):
            dialog.export_json.trigger()
        self.assertEqual(sorted(exported), [("op_10", "op_10.json"), ("op_2", "op_2.json")])

    def test_a_plan_that_cannot_be_exported_is_reported_and_the_others_are_still_exported(self):
        dialog, _conn = self.manager()
        self.select(dialog, "op_10", "op_2")

        def export(plan, path):
            if plan.plan_id == "op_10":
                raise transfer.TransferError("op_10.gpkg finns redan.")

        with mock.patch.object(manager.QFileDialog, "getExistingDirectory", return_value="C:/ut"), \
                mock.patch.object(manager.transfer, "export_plan", side_effect=export):
            dialog.export_geopackage.trigger()
        self.assertIn("Exporterade 1 av 2", dialog.notice.text())
        self.assertIn("op_10.gpkg: op_10.gpkg finns redan.", dialog.error.text())

    def test_cancelling_the_folder_dialog_exports_nothing(self):
        dialog, _conn = self.manager()
        self.select(dialog, "op_10")
        with mock.patch.object(manager.QFileDialog, "getExistingDirectory", return_value=""), \
                mock.patch.object(manager.transfer, "export_plan") as export:
            dialog.export_geopackage.trigger()
        export.assert_not_called()

    def run_import(self, dialog, conn, result):
        fake = mock.MagicMock()
        fake.exec.return_value = True
        fake.values.return_value = ImportValues(self.path_in, "a", "op_a", "ny_plan")

        def import_plan(path, connection, schema, plan_id, connection_object):
            if isinstance(result, Exception):
                raise result
            conn.plans["op_a"][plan_id] = {"titel": "Ny"}
            return result

        with mock.patch.object(manager, "ImportPlanDialog", return_value=fake), \
                mock.patch.object(manager.transfer, "import_plan", side_effect=import_plan) as run:
            dialog.import_plan.click()
        return run

    path_in = Path("C:/in/Ny plan.gpkg")

    def test_an_imported_plan_shows_up_in_the_list_selected_with_a_message(self):
        dialog, conn = self.manager()
        imported = transfer.Imported(storage.PostgisStorage("a", "op_a", "ny_plan"), {"oversiktsplan": 1, "lookup": 40})
        run = self.run_import(dialog, conn, imported)
        run.assert_called_once_with(self.path_in, "a", "op_a", "ny_plan", conn)
        self.assertEqual([r.plan_id for r in dialog.selected_rows()], ["ny_plan"])
        self.assertIn("Importerade Ny plan.gpkg som ny_plan i schemat op_a: 41 rader.", dialog.notice.text())

    def test_a_failed_import_shows_the_reason_and_adds_nothing(self):
        dialog, conn = self.manager()
        self.run_import(dialog, conn, storage.PostgisError("Det finns redan en plan med id ny_plan i schemat op_a."))
        self.assertIn("Kunde inte importera Ny plan.gpkg: Det finns redan en plan", dialog.error.text())
        self.assertEqual(dialog.notice.text(), "")
        self.assertEqual(sorted(r.plan_id for r in dialog._rows), ["gammal", "op_10", "op_2"])

    def copy_with(self, dialog, values, copy):
        fake = mock.MagicMock()
        fake.exec.return_value = True
        fake.values.return_value = values
        with mock.patch.object(manager, "CopyPlanDialog", return_value=fake), \
                mock.patch.object(manager.transfer, "copy_plan", side_effect=copy) as run:
            dialog.copy_plans.click()
        return run

    def test_selected_plans_are_copied_one_by_one_and_the_copy_is_shown_selected(self):
        dialog, conn = self.manager()
        self.select(dialog, "op_10")

        def copy(plan, connection, schema, plan_id, connection_object):
            conn.plans.setdefault(schema, {})[plan_id] = {"titel": "Kopia"}

        run = self.copy_with(dialog, CopyValues("a", "op_c", ["op_10_ny"]), copy)
        run.assert_called_once_with(storage.PostgisStorage("a", "op_a", "op_10"), "a", "op_c", "op_10_ny", conn)
        self.assertEqual([r.plan_id for r in dialog.selected_rows()], ["op_10_ny"])
        self.assertIn("Kopierade 1 av 1 planer till schemat op_c", dialog.notice.text())

    def test_a_plan_that_cannot_be_copied_is_reported_and_the_others_are_still_copied(self):
        dialog, conn = self.manager()
        self.select(dialog, "op_10", "op_2")

        def copy(plan, connection, schema, plan_id, connection_object):
            if plan.plan_id == "op_10":
                raise storage.PostgisError("Det finns redan en plan med id op_10 i schemat op_c.")
            conn.plans.setdefault(schema, {})[plan_id] = {"titel": "Kopia"}

        self.copy_with(dialog, CopyValues("a", "op_c", ["op_10", "op_2"]), copy)
        self.assertIn("Kopierade 1 av 2", dialog.notice.text())
        self.assertIn("op_10: Det finns redan en plan", dialog.error.text())

    def delete_with(self, dialog, confirm, directory="", export=None, delete=None):
        with mock.patch.object(dialog, "_confirm_delete", return_value=confirm), \
                mock.patch.object(manager.QFileDialog, "getExistingDirectory", return_value=directory), \
                mock.patch.object(manager.transfer, "export_plan", side_effect=export or (lambda plan, path: None)) as exported, \
                mock.patch.object(manager.transfer, "delete_plan", side_effect=delete or (lambda plan: None)) as deleted:
            dialog.delete_plans.click()
        return exported, deleted

    def test_cancelling_the_confirmation_removes_nothing(self):
        dialog, _conn = self.manager()
        self.select(dialog, "op_10")
        exported, deleted = self.delete_with(dialog, None)
        deleted.assert_not_called()
        exported.assert_not_called()

    def test_a_plan_is_saved_as_a_backup_before_it_is_removed(self):
        dialog, conn = self.manager()
        self.select(dialog, "op_10")
        order = []

        def delete(plan):
            order.append(("delete", plan.plan_id))
            del conn.plans[plan.schema][plan.plan_id]

        self.delete_with(dialog, True, "C:/kopior", export=lambda plan, path: order.append(("export", path.name)), delete=delete)
        self.assertEqual(order, [("export", "op_10.gpkg"), ("delete", "op_10")])
        self.assertIn("Tog bort 1 av 1 planer.", dialog.notice.text())
        self.assertIn("C:/kopior", dialog.notice.text(), "var säkerhetskopiorna ligger")

    def test_a_plan_whose_backup_failed_is_not_removed(self):
        dialog, conn = self.manager()
        conn.plans["op_a"]["op_2"].pop("lock")  # båda planerna i op_a är lediga
        dialog.reload()
        self.select(dialog, "op_10", "op_2")

        def export(plan, path):
            if plan.plan_id == "op_10":
                raise transfer.TransferError("op_10.gpkg finns redan.")

        removed = []
        self.delete_with(dialog, True, "C:/kopior", export=export, delete=lambda plan: removed.append(plan.plan_id))
        self.assertEqual(removed, ["op_2"], "bara planen som fick en säkerhetskopia")
        self.assertIn("Tog bort 1 av 2", dialog.notice.text())
        self.assertIn("op_10: op_10.gpkg finns redan.", dialog.error.text())

    def test_a_backup_without_a_folder_removes_nothing(self):
        dialog, _conn = self.manager()
        self.select(dialog, "op_10")
        exported, deleted = self.delete_with(dialog, True, directory="")
        deleted.assert_not_called()

    def test_a_checked_out_plan_is_never_passed_to_the_removal(self):
        dialog, _conn = self.manager()
        self.select(dialog, "op_10", "op_2")
        with mock.patch.object(manager.transfer, "delete_plan") as deleted, \
                mock.patch.object(dialog, "_confirm_delete") as confirm:
            dialog._delete_plans()  # även om knappen skulle trigga trots att den är avstängd
        deleted.assert_not_called()
        confirm.assert_not_called()

    def test_the_lock_of_a_checked_out_plan_can_be_broken_after_confirming(self):
        dialog, _conn = self.manager()
        self.select(dialog, "op_10", "op_2")
        with mock.patch.object(dialog, "_confirm_break_locks", return_value=True) as confirm, \
                mock.patch.object(manager.checkout, "break_lock") as broken:
            dialog.break_locks.click()
        self.assertEqual([r.plan_id for r in confirm.call_args.args[0]], ["op_2"], "bara de utcheckade planerna")
        self.assertEqual([c.args[0].plan_id for c in broken.call_args_list], ["op_2"])
        self.assertIn("Bröt låset på 1 av 1 planer", dialog.notice.text())

    def test_declining_the_confirmation_leaves_the_lock_alone(self):
        dialog, _conn = self.manager()
        self.select(dialog, "op_2")
        with mock.patch.object(dialog, "_confirm_break_locks", return_value=False), \
                mock.patch.object(manager.checkout, "break_lock") as broken:
            dialog.break_locks.click()
        broken.assert_not_called()


if __name__ == "__main__":
    unittest.main()

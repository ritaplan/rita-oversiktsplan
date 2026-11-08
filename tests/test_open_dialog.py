"""Dialogen för att öppna en översiktsplan ur en databas: översikt med kolumner, sortering, filter och val av flera planer
(kräver QGIS). Samma upplägg som i Rita Detaljplan, med översiktsplanens uppgifter.

En låtsasanslutning svarar på frågorna om scheman, planer, planens uppgifter, beslut och lås."""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qgis_app import get_app  # noqa: E402

get_app()

from qgis.PyQt.QtCore import QItemSelectionModel, Qt  # noqa: E402

from rita_oversiktsplan.core import checkout as co  # noqa: E402
from rita_oversiktsplan.core import plan_overview  # noqa: E402
from rita_oversiktsplan.gui.postgis_plan_dialog import (COLUMN_FIELDS, LOCK_FREE, LOCK_TAKEN, ROW_ROLE,  # noqa: E402
                                                        PostgisPlanDialog, lock_text, natural_key)


class OverviewConnection:
    """Låtsasanslutning: ``plans`` är schema -> plan-id -> uppgifter, ``decisions`` schema -> rader
    [plan, objektidentitet, diarienummer, fattat, laga kraft]."""

    def __init__(self, plans=None, decisions=None, fail_on=None):
        self.plans = plans or {}
        self.decisions = decisions or {}
        self.fail_on = fail_on
        self.sql = []

    def executeSql(self, sql):  # noqa: N802 - samma namn som QGIS anslutningar
        self.sql.append(sql)
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("syntaxfel nära " + self.fail_on)
        if "information_schema.tables" in sql:
            return [[schema] for schema in sorted(self.plans)]
        match = re.search(r'"([^"]+)"\."', sql)
        schema = match.group(1) if match else ""
        plans = self.plans.get(schema, {})
        if sql.startswith('SELECT DISTINCT m."plan"'):
            return [[plan_id, p.get("titel")] for plan_id, p in sorted(plans.items())]
        if sql.startswith('SELECT "plan", "value"') and "'checkout'" in sql:
            return [[plan_id, p["lock"].to_json()] for plan_id, p in sorted(plans.items()) if p.get("lock")]
        if sql.startswith('SELECT "plan", "planens_titel"'):
            return [[plan_id, p.get("titel"), p.get("planhandelse"), p.get("planhandelse_datum"), p.get("paborjad"),
                     p.get("beslut")] for plan_id, p in sorted(plans.items())]
        if sql.startswith('SELECT "plan", "objektidentitet"'):
            return [row[:3] for row in self.decisions.get(schema, [])]
        if sql.startswith('SELECT "beslut_op_id"'):  # beslutens datum står i beslut_op_handelse
            return [[row[1], kind, when] for row in self.decisions.get(schema, [])
                    for kind, when in (("fattat", row[3]), ("laga kraft", row[4])) if when]
        return []


def detailed():
    """Två scheman med tre planer: en ledig, en utcheckad av någon annan och en av den här användaren."""
    others = co.Lock("t1", "annan", "annan-dator", "2026-10-01T09:30:00")
    mine = co.new_lock()
    return OverviewConnection(
        plans={
            "op_a": {
                "op_10": {"titel": "ÖP 10", "planhandelse": "samråd", "planhandelse_datum": "2026-05-02",
                          "paborjad": "2025-09-01", "beslut": ""},
                "op_2": {"titel": "ÖP 2", "planhandelse": "antagen", "planhandelse_datum": None, "paborjad": "2020-01-01",
                         "beslut": "b2", "lock": others},
            },
            "op_b": {"gammal": {"titel": "Gammal ÖP", "planhandelse": "antagen", "planhandelse_datum": "2010-06-01",
                                "paborjad": None, "beslut": "", "lock": mine}},
        },
        decisions={"op_a": [
            ["op_2", "b2", "KF 2021/7", "2021-03-01", "2021-04-01"],
            ["op_2", "b-annat", "KF 2019/1", "2019-01-01", None],
            ["op_10", "b10-gammalt", "KS 2024/1", "2024-01-15", None],
            ["op_10", "b10-nytt", "KS 2025/9", "2025-11-20", None],
        ]})


class OverviewTests(unittest.TestCase):
    def rows(self):
        conn = detailed()
        return {r.plan_id: r for r in plan_overview.list_plans("db", conn, "op_a")}

    def test_the_plans_uppgifter_come_from_the_plan_and_its_decision(self):
        rows = self.rows()
        ten, two = rows["op_10"], rows["op_2"]
        self.assertEqual((ten.titel, ten.planhandelse, ten.planhandelse_datum, ten.paborjad),
                         ("ÖP 10", "samråd", "2026-05-02", "2025-09-01"))
        # planen pekar på sitt beslut (b2), inte på något annat beslut: diarienumret är det beslutets
        self.assertEqual((two.diarienummer, two.beslut_fattat, two.laga_kraft), ("KF 2021/7", "2021-03-01", "2021-04-01"))
        self.assertEqual(two.planhandelse_datum, "")

    def test_without_a_pointer_the_latest_decision_of_the_plan_is_used(self):
        ten = self.rows()["op_10"]
        self.assertEqual((ten.diarienummer, ten.beslut_fattat, ten.laga_kraft), ("KS 2025/9", "2025-11-20", ""))

    def test_a_plan_without_details_is_still_listed_with_its_title(self):
        conn = OverviewConnection(plans={"s": {"p": {"titel": "Bara titel"}}})
        row = plan_overview.list_plans("db", conn, "s")[0]
        self.assertEqual((row.titel, row.planhandelse, row.diarienummer, row.laga_kraft), ("Bara titel", "", "", ""))

    def test_a_table_that_cannot_be_read_does_not_stop_the_overview(self):
        conn = detailed()
        conn.fail_on = "beslut_op"
        rows = plan_overview.list_plans("db", conn, "op_a")
        self.assertEqual(sorted(r.plan_id for r in rows), ["op_10", "op_2"])
        self.assertEqual(rows[0].diarienummer, "")

    def test_locks_are_told_apart_from_the_users_own(self):
        conn = detailed()
        taken = {r.plan_id: r for r in plan_overview.list_plans("db", conn, "op_a")}["op_2"]
        mine = plan_overview.list_plans("db", conn, "op_b")[0]
        self.assertTrue(taken.locked_by_other)
        self.assertTrue(mine.locked_by_me)
        self.assertIn("annan", lock_text(taken))
        self.assertTrue(lock_text(mine).startswith("Du"))

    def test_the_overview_uses_a_few_queries_per_schema_not_one_per_plan(self):
        conn = detailed()
        plan_overview.list_plans("db", conn, "op_a")
        self.assertEqual(len(conn.sql), 5, conn.sql)  # planer, lås, uppgifter, beslut och beslutens datum

    def test_the_lock_check_matches_the_user_and_the_computer(self):
        self.assertTrue(co.is_own_lock(co.new_lock()))
        self.assertFalse(co.is_own_lock(co.Lock("t", "annan", co._host(), "2026-01-01T00:00:00")))
        self.assertFalse(co.is_own_lock(co.Lock("t", co._user(), "en-annan-dator", "2026-01-01T00:00:00")))


class DialogTests(unittest.TestCase):
    def dialog(self, connections):
        dialog = PostgisPlanDialog(None, connections)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def visible_ids(self, dialog):
        return [dialog.model.item(dialog.proxy.mapToSource(dialog.proxy.index(i, 0)).row(), 0).data(ROW_ROLE).plan_id
                for i in range(dialog.proxy.rowCount())]

    def select(self, dialog, *plan_ids):
        dialog.table.clearSelection()
        visible = self.visible_ids(dialog)
        for plan_id in plan_ids:
            self.assertIn(plan_id, visible)
            dialog.table.selectionModel().select(
                dialog.proxy.index(visible.index(plan_id), 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)

    def test_all_plans_of_all_plugin_schemas_are_listed(self):
        dialog = self.dialog({"a": detailed()})
        self.assertEqual(sorted(self.visible_ids(dialog)), ["gammal", "op_10", "op_2"])
        self.assertIn("Synliga: 3 av 3", dialog.count.text())
        self.assertEqual(dialog.selections(), [])
        self.assertFalse(dialog.open_checkout.isEnabled())
        self.assertFalse(dialog.open_readonly.isEnabled())

    def test_the_list_starts_sorted_on_the_title_with_numbers_as_numbers(self):
        dialog = self.dialog({"a": detailed()})
        self.assertEqual(COLUMN_FIELDS[0], "titel")
        self.assertEqual(dialog.table.horizontalHeader().sortIndicatorSection(), 0)
        self.assertEqual(self.visible_ids(dialog), ["gammal", "op_2", "op_10"], "Gammal ÖP, ÖP 2, ÖP 10 (inte ÖP 10 före ÖP 2)")
        dialog.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.assertEqual(self.visible_ids(dialog), ["op_10", "op_2", "gammal"])

    def test_the_natural_key_compares_numbers_by_value_and_puts_empty_last(self):
        ordered = ["1", "2", "9", "10", "100", "1002", "a1", "A2", "a10"]
        self.assertEqual(sorted(ordered, key=natural_key), ordered)
        self.assertLess(natural_key("1002"), natural_key(""))

    def test_selecting_a_plan_gives_connection_schema_and_plan(self):
        dialog = self.dialog({"a": detailed()})
        self.select(dialog, "op_10")
        self.assertEqual(dialog.selections(), [("a", "op_a", "op_10")])
        self.assertTrue(dialog.open_checkout.isEnabled())
        self.assertTrue(dialog.open_readonly.isEnabled())

    def test_a_plan_checked_out_by_someone_else_can_only_be_opened_read_only(self):
        dialog = self.dialog({"a": detailed()})
        self.select(dialog, "op_2")
        self.assertFalse(dialog.open_checkout.isEnabled())
        self.assertTrue(dialog.open_readonly.isEnabled())
        self.assertIn("annan", dialog.hint.text())
        dialog._accept_with(True)  # ska inte gå att tvinga fram
        self.assertEqual(dialog.result(), 0)
        self.assertFalse(dialog.checkout_requested)

    def test_the_users_own_checkout_can_be_taken_up_again(self):
        dialog = self.dialog({"a": detailed()})
        self.select(dialog, "gammal")
        self.assertTrue(dialog.open_checkout.isEnabled())

    def test_the_two_buttons_tell_whether_the_plan_should_be_checked_out(self):
        for check_out in (True, False):
            dialog = self.dialog({"a": detailed()})
            self.select(dialog, "op_10")
            dialog._accept_with(check_out)
            self.assertEqual(dialog.result(), 1)
            self.assertEqual(dialog.checkout_requested, check_out)

    def test_several_plans_can_be_chosen_at_once(self):
        dialog = self.dialog({"a": detailed()})
        self.select(dialog, "op_10", "gammal")
        self.assertEqual(sorted(dialog.selections()), [("a", "op_a", "op_10"), ("a", "op_b", "gammal")])
        self.assertIn("Valda: 2", dialog.count.text())
        self.assertIn("2 planer valda", dialog.hint.text())
        self.assertTrue(dialog.open_checkout.isEnabled())

    def test_checking_out_several_needs_all_to_be_free_or_the_users_own(self):
        dialog = self.dialog({"a": detailed()})
        self.select(dialog, "op_10", "op_2")  # den andra är utcheckad av någon annan
        self.assertFalse(dialog.open_checkout.isEnabled())
        self.assertTrue(dialog.open_readonly.isEnabled())
        self.assertIn("ÖP 2", dialog.hint.text(), "namnger den som någon annan har")
        dialog._accept_with(True)
        self.assertEqual(dialog.result(), 0)
        dialog._accept_with(False)
        self.assertEqual(dialog.result(), 1)
        self.assertEqual(len(dialog.selections()), 2)

    def test_filtering_by_text_planhandelse_schema_and_lock(self):
        dialog = self.dialog({"a": detailed()})
        dialog.filter_text.setText("kf 2021")  # ur beslutets diarienummer
        self.assertEqual(self.visible_ids(dialog), ["op_2"])
        self.assertIn("Synliga: 1 av 3", dialog.count.text())
        dialog.filter_text.setText("öp 10 samråd")  # flera ord, i valfri ordning och kolumn
        self.assertEqual(self.visible_ids(dialog), ["op_10"])
        dialog.filter_text.setText("")
        for combo, text, expected in ((dialog.filter_status, "antagen", ["gammal", "op_2"]),
                                      (dialog.filter_schema, "op_b", ["gammal"])):
            combo.setCurrentIndex(combo.findText(text))
            self.assertEqual(sorted(self.visible_ids(dialog)), expected, text)
            combo.setCurrentIndex(0)
        dialog.filter_lock.setCurrentIndex(dialog.filter_lock.findData(LOCK_FREE))
        self.assertEqual(self.visible_ids(dialog), ["op_10"])
        dialog.filter_lock.setCurrentIndex(dialog.filter_lock.findData(LOCK_TAKEN))
        self.assertEqual(sorted(self.visible_ids(dialog)), ["gammal", "op_2"])
        self.assertIn("Synliga: 2 av 3", dialog.count.text())

    def test_the_filter_lists_hold_the_values_that_exist_and_no_municipality_is_offered(self):
        dialog = self.dialog({"a": detailed()})

        def items(combo):
            return [combo.itemText(i) for i in range(1, combo.count())]
        self.assertEqual(items(dialog.filter_status), ["antagen", "samråd"])
        self.assertEqual(items(dialog.filter_schema), ["op_a", "op_b"])
        self.assertFalse(hasattr(dialog, "filter_kommun"), "en databas hör till en kommun: inget val av kommun")

    def test_the_schema_filter_sits_next_to_the_database_choice(self):
        dialog = self.dialog({"a": detailed()})
        top = dialog.layout().itemAt(0).layout()
        widgets = [top.itemAt(i).widget() for i in range(top.count()) if top.itemAt(i).widget() is not None]
        self.assertEqual(widgets.index(dialog.filter_schema), widgets.index(dialog.connection) + 1)

    def test_the_connection_chooses_which_database_is_shown(self):
        a = OverviewConnection(plans={"s": {"p1": {"titel": "A"}}})
        b = OverviewConnection(plans={"s": {"p9": {"titel": "B"}}})
        dialog = self.dialog({"a": a, "b": b})
        self.assertEqual(self.visible_ids(dialog), ["p1"])
        dialog.connection.setCurrentIndex(1)
        self.assertEqual(self.visible_ids(dialog), ["p9"])

    def test_an_empty_database_and_a_failing_one_are_explained(self):
        self.assertIn("inga scheman", self.dialog({"a": OverviewConnection()}).error.text())
        self.assertIn("inga planer", self.dialog({"a": OverviewConnection(plans={"s": {}})}).error.text())
        broken = mock.Mock()
        broken.executeSql.side_effect = RuntimeError("timeout")
        dialog = self.dialog({"a": broken})
        self.assertIn("timeout", dialog.error.text())
        self.assertEqual(dialog.proxy.rowCount(), 0)
        self.assertIn("Synliga: 0 av 0", dialog.count.text())


if __name__ == "__main__":
    unittest.main()

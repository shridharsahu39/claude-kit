"""Tests for suggest.py: which checks a diff recommends."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from suggest import recommend, changes


class Recommend(unittest.TestCase):
    def test_text_only_recommends_nothing(self):
        self.assertEqual(recommend(["README.md", "app/translations/hi.csv", "docs/guide.md"], ["new words"]), {})

    def test_nothing_changed(self):
        self.assertEqual(recommend([], []), {})

    def test_plain_code_change(self):
        rec = recommend(["app/utils/format.py"], ["return round(x, 2)"])
        self.assertEqual(set(rec), {"quality", "tests"})

    def test_whitelisted_method_needs_security(self):
        rec = recommend(["app/api/orders.py"], ["@frappe.whitelist()", "def cancel(name):"])
        self.assertIn("security", rec)
        self.assertIn("@frappe.whitelist", rec["security"])

    def test_hooks_file_is_outside_callers(self):
        self.assertIn("security", recommend(["app/hooks.py"], ['"daily": ["app.tasks.sync"]']))

    def test_doctype_json_needs_migration_and_performance(self):
        rec = recommend(["app/fund/doctype/order/order.json"], ['"fieldname": "status"'])
        self.assertIn("migration", rec)
        self.assertNotIn("performance", rec)  # JSON isn't code; nothing to time
        rec = recommend(["app/fund/doctype/order/order.json", "app/fund/doctype/order/order.py"], ["x = 1"])
        self.assertIn("performance", rec)

    def test_frontend_component_needs_browser_qa(self):
        rec = recommend(["src/pages/Orders.tsx"], ["<Table rows={rows} />"])
        self.assertIn("browser", rec)

    def test_query_in_code_suggests_performance(self):
        rec = recommend(["app/report.py"], ['rows = frappe.get_all("Order", fields=["name"])'])
        self.assertIn("performance", rec)

    def test_dependency_change_needs_security(self):
        self.assertIn("security", recommend(["package.json"], ['"left-pad": "1.3.0"']))

    def test_never_recommends_cloudflare(self):
        rec = recommend(["app/api.py", "src/App.tsx", "app/hooks.py"], ["@frappe.whitelist()"])
        self.assertNotIn("cloudflare", rec)


class Changes(unittest.TestCase):
    def test_reads_committed_uncommitted_and_untracked(self):
        with tempfile.TemporaryDirectory() as d:
            run = lambda *a: subprocess.run(["git", "-C", d, *a], check=True, capture_output=True)
            run("init", "-q", "-b", "main")
            run("config", "user.email", "qa+1@example.com")
            run("config", "user.name", "Test")
            Path(d, "a.py").write_text("x = 1\n")
            run("add", ".")
            run("commit", "-qm", "base")
            run("checkout", "-qb", "feature")
            Path(d, "a.py").write_text("x = 2\n")
            Path(d, "new.py").write_text("@frappe.whitelist()\n")
            names, lines = changes(d, "main")
            self.assertEqual(names, ["a.py", "new.py"])
            self.assertIn("@frappe.whitelist()", lines)
            self.assertIn("security", recommend(names, lines))


if __name__ == "__main__":
    unittest.main()

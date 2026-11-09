"""Tests for load.py. Run: python3 -m unittest discover -s plugins/sm-kit/skills/performance"""
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load  # noqa: E402

SEEN = []


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        SEEN.append(dict(self.headers))
        status, body = (500 if self.path == "/fail" else 200), b"ok"
        if self.path == "/api/method/frappe.auth.get_logged_user":
            users = {"sid=qa-fake": "qa-desk@example.com", "sid=other": "someone@example.com"}
            user = users.get(self.headers.get("Cookie", ""))
            status, body = (200, json.dumps({"message": user}).encode()) if user else (403, b"{}")
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Load(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.qa_sites = tempfile.TemporaryDirectory()
        Path(cls.qa_sites.name, "qa.localhost.qa-site").write_text("")
        Path(cls.qa_sites.name, "qa.localhost.md").write_text("# QA personas\n\n- qa-desk@example.com\n")
        Path(cls.qa_sites.name, "sm16.localhost.md").write_text("# a personas file alone doesn't make a QA site\n")
        cls.real_qa_sites, load.QA_SITES = load.QA_SITES, cls.qa_sites.name

    def header_file(self, text):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(text)
        os.chmod(f.name, 0o600)
        self.addCleanup(os.unlink, f.name)
        return f.name

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        load.QA_SITES = cls.real_qa_sites
        cls.qa_sites.cleanup()

    def run_load(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(load.main(list(argv)), 0)
        return json.loads(out.getvalue())

    def test_counts_and_percentiles(self):
        levels = self.run_load(f"{self.base}/", "--concurrency", "1,4", "--requests", "40", "--json")
        self.assertEqual([r["requests"] for r in levels], [40, 40])
        self.assertEqual([r["ok"] for r in levels], [40, 40])
        self.assertTrue(all(r["p50_ms"] <= r["p95_ms"] <= r["max_ms"] for r in levels))

    def test_errors_by_status(self):
        [level] = self.run_load(f"{self.base}/fail", "--concurrency", "2", "--requests", "6", "--json")
        self.assertEqual(level["errors"], {"500": 6})

    def test_fresh_header_and_header_file(self):
        SEEN.clear()
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("Cookie: sid=qa-fake\n")
        os.chmod(f.name, 0o600)
        try:
            self.run_load(f"{self.base}/", "--concurrency", "1", "--requests", "3",
                          "--header-file", f.name, "--fresh-ms-header", "x-timestamp", "--json")
        finally:
            os.unlink(f.name)
        self.assertEqual(len(SEEN), 3)
        self.assertTrue(all(h.get("Cookie") == "sid=qa-fake" and h.get("x-timestamp", "").isdigit() for h in SEEN))

    def test_a_localhost_name_goes_to_this_machine_with_its_host(self):
        SEEN.clear()
        port = self.server.server_port
        self.run_load(f"http://qa.localhost:{port}/", "--concurrency", "1", "--requests", "2", "--json",
                      "--header-file", self.header_file("Cookie: sid=qa-fake\n"))
        self.assertEqual([h.get("Host") for h in SEEN], [f"qa.localhost:{port}"] * 3)  # the site check, then 2

    def test_the_server_must_answer_as_a_qa_persona(self):
        url = f"http://qa.localhost:{self.server.server_port}/"
        with redirect_stderr(io.StringIO()):
            for extra in ([], ["--header-file", self.header_file("Cookie: sid=other\n")]):
                with self.assertRaises(SystemExit, msg=extra):
                    load.main([url, "--requests", "1", "--concurrency", "1", *extra])

    def test_plain_query_and_body_pass(self):
        SEEN.clear()
        self.run_load(f"{self.base}/?fund=QA1&page=2", "--concurrency", "1", "--requests", "1", "--json")
        self.run_load(f"{self.base}/", "--data", '{"fund": "QA1"}', "--method", "GET", "--concurrency", "1",
                      "--requests", "1", "--json")
        self.assertEqual(len(SEEN), 2)

    def test_refusals(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("Cookie: x\npwd=y\n")
        os.chmod(f.name, 0o644)
        refused = [
            ["https://example.com/api"], ["http://example.com/"], ["http://qa.test:8000/"],
            ["http://10.0.0.5:8000/"], ["https://localhost:8000/"], ["http://user:pw@localhost:8000/"],
            [f"{self.base}/", "--allow-host", "example.com"],
            [f"{self.base}/", "--header", "Cookie: sid=x"], [f"{self.base}/", "--header", "Authorization: x"],
            [f"{self.base}/", "--header", "Host: sm.localhost"],
            [f"{self.base}/", "--header", "X-Frappe-Site-Name: sm.localhost"],
            [f"{self.base}/", "--requests", "0"], [f"{self.base}/", "--requests", "100000"],
            [f"{self.base}/", "--timeout", "999"], [f"{self.base}/", "--concurrency", "1,2,3,4,5,6,7,8,9,10,11"],
            [f"{self.base}/", "--header-file", f.name],
            [f"http://sm16.localhost:{self.server.server_port}/"],
            [f"http://mfrehearsal.localhost:{self.server.server_port}/"],
            [f"{self.base}/app?sid=x"], [f"{self.base}/api?api_key=x"], [f"{self.base}/login?usr=a&pwd=b"],
            [f"{self.base}/", "--data", '{"usr": "a", "pwd": "b"}'], [f"{self.base}/", "--data", "otp=123456"],
            [f"{self.base}/", "--data", '{"usr": "a", "p\\u0077d": "b"}'],
            [f"{self.base}/", "--data", '{"cmd": "x", "args": "{\\"pwd\\": \\"b\\"}"}'],
            [f"{self.base}/", "--data", f"@{f.name}"],
        ]
        try:
            with redirect_stderr(io.StringIO()):
                for argv in refused:
                    with self.assertRaises(SystemExit, msg=argv):
                        load.main(argv)
        finally:
            os.unlink(f.name)

    def test_loopback_address(self):
        self.assertEqual(load.loopback_address("qa.localhost"), "127.0.0.1")
        self.assertEqual(load.loopback_address("localhost"), "127.0.0.1")
        self.assertEqual(load.loopback_address("::1"), "::1")
        self.assertEqual(load.loopback_address("127.0.0.2"), "127.0.0.2")
        for host in ("bseindia.com", "qa.test", "10.0.0.1", "", None):
            self.assertIsNone(load.loopback_address(host), host)


if __name__ == "__main__":
    unittest.main()

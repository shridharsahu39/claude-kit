#!/usr/bin/env python3
"""A small load generator for local performance checks. Standard library only.

Usage:
  load.py URL [--method GET] [--data JSON | --data @FILE]
          [--header "Name: value" ...] [--header-file FILE]
          [--fresh-ms-header NAME] [--concurrency 1,5,10,25,50]
          [--requests 200 | --duration SECONDS] [--timeout 30] [--json]

It runs each concurrency level in turn, each worker on its own keep-alive
connection, and prints for each level: requests, errors by status,
throughput, and latency p50, p95, p99 and max in milliseconds.

It loads only this machine, over plain HTTP. The URL's host must be localhost,
a *.localhost name (always sent to 127.0.0.1, whatever a resolver says) or a
loopback address, and there is no override: load on a shared or partner system
is an attack, whoever runs it, so such a target needs the owner's go-ahead in
chat and another tool. The URL also picks the site: a Host header, or an
X-Frappe-Site-Name naming another site, is refused. A *.localhost site takes
load only when setup-machine has marked it a QA site
(~/.claude/qa-sites/<site>.qa-site), and only once the server has answered a
first request as one of that site's QA personas: a server started for one site
(the dev stack's `bench serve`, say) serves it whatever the Host header says,
and only the QA site knows a QA persona's session. A localhost or loopback
target (the relay, the frontend) gets no such check: point it only at a server
the run started.

Secrets (a session cookie, a token) come only from --header-file, kept at mode
600, so they never appear in a command line or its output. A secret-looking
query parameter or inline --data field is refused: send it in the header file,
or in a body file at mode 600 (--data @FILE). --fresh-ms-header sets that
header to the current time in milliseconds on every request, as the relay's
replay check needs (x-timestamp).
"""
import argparse
import http.client
import ipaddress
import json
import os
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlsplit

MAX_CONCURRENCY = 200
MAX_LEVELS = 10
MAX_REQUESTS = 20_000
MAX_DURATION = 300
MAX_TIMEOUT = 120
MAX_TOTAL = 900
QA_SITES = os.path.expanduser("~/.claude/qa-sites")
SECRET_NAME = re.compile(
    r"cookie|authori[sz]ation|token|secret|key|session|csrf|pass(?:word|wd)|pwd|signature|^sid$|(?:^|[_-])otp",
    re.IGNORECASE,
)


def secret_fields(body):
    """The field names in a body that look like they carry a secret: JSON keys at any depth,
    JSON held in a string (as Frappe's `args` is) included, form fields, and anything else
    written like `name: value` or `name=value`."""
    names = re.findall(r"([A-Za-z_][\w.-]*)[\"']?\s*[:=]", body)

    def walk(value, depth=0):
        if depth > 8:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                names.append(str(key))
                walk(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                walk(item, depth + 1)
        elif isinstance(value, str) and value.lstrip()[:1] in ("{", "["):
            try:
                walk(json.loads(value), depth + 1)
            except ValueError:
                pass

    try:
        walk(json.loads(body))
    except ValueError:
        names.extend(name for name, _ in parse_qsl(body, keep_blank_values=True))
    return [name for name in names if SECRET_NAME.search(name)]


def check_site(url, address, headers, host, parser):
    """Refuse unless the server answers as one of the QA site's personas.

    Only the QA site knows a QA persona's session, so the answer shows which
    site the port really serves, whatever the Host header says.
    """
    parts = urlsplit(url)
    conn = http.client.HTTPConnection(address, parts.port or 80, timeout=10)
    try:
        conn.request("GET", "/api/method/frappe.auth.get_logged_user", headers={"Host": parts.netloc, **headers})
        response = conn.getresponse()
        status, body = response.status, response.read(65536)
    except (OSError, http.client.HTTPException) as exc:
        status, body = type(exc).__name__, b""
    finally:
        conn.close()
    try:
        user = json.loads(body).get("message")
    except (ValueError, AttributeError):
        user = None
    try:
        with open(os.path.join(QA_SITES, host + ".md"), encoding="utf-8") as f:
            personas = f.read()
    except OSError:
        personas = ""
    if status != 200 or not isinstance(user, str) or not user or user not in personas:
        parser.error(f"{parts.netloc} didn't answer as one of {host}'s QA personas ({status}): load.py loads a "
                     "site only once a QA persona's session (in --header-file) shows the port serves that site")


def loopback_address(host):
    """The address to connect to for host, or None when host isn't this machine."""
    host = (host or "").lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        return "127.0.0.1"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return None
    return str(address) if address.is_loopback else None


def read_headers(args, parser, host):
    for line in args.header or []:
        name = line.partition(":")[0].strip()
        if SECRET_NAME.search(name):
            parser.error(f"{name} looks like a secret: put it in --header-file (mode 600), not on the command line")
    lines = list(args.header or [])
    if args.header_file:
        with open(args.header_file, encoding="utf-8") as f:
            lines += [line.strip() for line in f if line.strip() and not line.startswith("#")]
    headers = {}
    for line in lines:
        name, _, value = line.partition(":")
        name, value = name.strip(), value.strip()
        if name.lower() == "host" or (name.lower() == "x-frappe-site-name" and value.lower() != host):
            parser.error(f"the URL picks the host and the site: drop the {name} header")
        headers[name] = value
    return headers


def read_body(data, parser):
    if not data:
        return None
    if data.startswith("@"):
        with open(data[1:], "rb") as f:
            body = f.read()
        if secret_fields(body.decode("utf-8", "replace")) and os.stat(data[1:]).st_mode & 0o077:
            parser.error(f"{data[1:]} holds a secret-looking field and is readable by others: chmod 600 it first")
        return body
    if secret_fields(data):
        parser.error("--data holds a secret-looking field: put the body in a file at mode 600 and pass --data @FILE")
    return data.encode()


class Worker:
    """One connection to this machine, reused across requests, reopened after a failure."""

    def __init__(self, url, address, timeout):
        parts = urlsplit(url)
        self.address = address
        self.port = parts.port or 80
        self.host = parts.netloc
        self.timeout = timeout
        self.path = parts.path or "/"
        if parts.query:
            self.path += "?" + parts.query
        self.conn = None

    def send(self, method, headers, body):
        if self.conn is None:
            self.conn = http.client.HTTPConnection(self.address, self.port, timeout=self.timeout)
        start = time.perf_counter()
        try:
            self.conn.request(method, self.path, body=body, headers={"Host": self.host, **headers})
            response = self.conn.getresponse()
            response.read()
            status = response.status
            if response.getheader("connection", "").lower() == "close":
                self.close()
        except (OSError, http.client.HTTPException) as exc:
            self.close()
            status = type(exc).__name__
        return status, (time.perf_counter() - start) * 1000

    def close(self):
        if self.conn is not None:
            self.conn.close()
        self.conn = None


def run_level(args, concurrency, address, headers, body, stop_at):
    latencies, statuses = [], Counter()
    lock = threading.Lock()
    remaining = [args.requests]
    deadline = time.monotonic() + args.duration if args.duration else None

    def take():
        with lock:
            now = time.monotonic()
            if now >= stop_at:
                return False
            if deadline is not None:
                return now < deadline
            if remaining[0] <= 0:
                return False
            remaining[0] -= 1
            return True

    def work():
        worker = Worker(args.url, address, args.timeout)
        while take():
            request_headers = dict(headers)
            if args.fresh_ms_header:
                request_headers[args.fresh_ms_header] = str(int(time.time() * 1000))
            status, ms = worker.send(args.method, request_headers, body)
            with lock:
                latencies.append(ms)
                statuses[status] += 1
        worker.close()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for _ in range(concurrency):
            pool.submit(work)
    elapsed = time.perf_counter() - started
    latencies.sort()

    def pct(q):
        return round(latencies[min(len(latencies) - 1, int(round(q * (len(latencies) - 1))))], 1) if latencies else None

    ok = sum(n for s, n in statuses.items() if isinstance(s, int) and s < 400)
    return {
        "concurrency": concurrency,
        "requests": len(latencies),
        "ok": ok,
        "errors": {str(s): n for s, n in statuses.items() if not (isinstance(s, int) and s < 400)},
        "seconds": round(elapsed, 2),
        "per_second": round(len(latencies) / elapsed, 1) if elapsed else None,
        "p50_ms": pct(0.50), "p95_ms": pct(0.95), "p99_ms": pct(0.99),
        "max_ms": round(latencies[-1], 1) if latencies else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local load generator for performance checks.")
    parser.add_argument("url")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--data")
    parser.add_argument("--header", action="append")
    parser.add_argument("--header-file")
    parser.add_argument("--fresh-ms-header")
    parser.add_argument("--concurrency", default="1,5,10,25,50")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    parts = urlsplit(args.url)
    if parts.scheme != "http" or parts.username or parts.password:
        parser.error("load.py speaks plain HTTP to this machine, with no credentials in the URL")
    address = loopback_address(parts.hostname)
    if address is None:
        parser.error(f"refusing {parts.hostname}: load.py runs only against this machine, and a target "
                     "anywhere else needs the owner's go-ahead in chat and another tool")
    host = parts.hostname.lower().rstrip(".")
    if host.endswith(".localhost") and not os.path.isfile(os.path.join(QA_SITES, host + ".qa-site")):
        parser.error(f"{host} isn't a QA site on this machine: load.py loads a site only when setup-machine has "
                     f"marked it one ({QA_SITES}/{host}.qa-site), so a run never lands on the working or rehearsal "
                     "site")
    for name, _ in parse_qsl(parts.query, keep_blank_values=True):
        if SECRET_NAME.search(name):
            parser.error(f"the query parameter {name} looks like a secret: send it in --header-file or a "
                         "--data file at mode 600, never in the URL")
    if args.header_file and os.stat(args.header_file).st_mode & 0o077:
        parser.error(f"{args.header_file} is readable by others: chmod 600 it first")
    levels = [int(c) for c in args.concurrency.split(",") if c.strip()]
    if not levels or len(levels) > MAX_LEVELS or any(c < 1 or c > MAX_CONCURRENCY for c in levels):
        parser.error(f"give 1 to {MAX_LEVELS} concurrency levels, each 1 to {MAX_CONCURRENCY}")
    if not 1 <= args.requests <= MAX_REQUESTS:
        parser.error(f"--requests must be 1 to {MAX_REQUESTS}")
    if args.duration is not None and not 0 < args.duration <= MAX_DURATION:
        parser.error(f"--duration must be more than 0 and at most {MAX_DURATION} seconds")
    if not 0 < args.timeout <= MAX_TIMEOUT:
        parser.error(f"--timeout must be more than 0 and at most {MAX_TIMEOUT} seconds")

    headers, body = read_headers(args, parser, host), read_body(args.data, parser)
    if host.endswith(".localhost"):
        check_site(args.url, address, headers, host, parser)
    if body is not None and not any(h.lower() == "content-type" for h in headers):
        headers["Content-Type"] = "application/json"
    stop_at = time.monotonic() + MAX_TOTAL
    results = []
    for c in levels:
        if time.monotonic() >= stop_at:
            break
        results.append(run_level(args, c, address, headers, body, stop_at))
    if args.json:
        print(json.dumps(results, indent=1))
    else:
        print(f"{'conc':>5} {'reqs':>6} {'ok':>6} {'req/s':>8} {'p50':>8} {'p95':>8} {'p99':>8} {'max':>8}  errors")
        for r in results:
            print(f"{r['concurrency']:>5} {r['requests']:>6} {r['ok']:>6} {r['per_second'] or 0:>8} "
                  f"{r['p50_ms'] or 0:>8} {r['p95_ms'] or 0:>8} {r['p99_ms'] or 0:>8} {r['max_ms'] or 0:>8}  "
                  f"{r['errors'] or '-'}")
        if len(results) < len(levels):
            print(f"Stopped after {len(results)} levels: a run lasts at most {MAX_TOTAL} seconds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

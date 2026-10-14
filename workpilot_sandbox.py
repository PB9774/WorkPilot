from __future__ import annotations

import threading
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

_server: ThreadingHTTPServer | None = None
_server_lock = threading.Lock()


def ensure_sandbox_server(
    connect: Callable[[], Any],
    apply_update: Callable[[str, dict[str, Any]], dict[str, Any]],
    host: str,
    port: int,
) -> None:
    global _server
    with _server_lock:
        if _server is not None:
            return

        class SandboxHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if urlparse(self.path).path != "/":
                    self.send_error(404)
                    return
                with connect() as db:
                    rows = db.execute("SELECT invoice_id, vendor_id, invoice_number, status FROM internal_invoices ORDER BY invoice_id LIMIT 200").fetchall()
                table_rows = []
                for row in rows:
                    invoice_id = escape(row["invoice_id"])
                    table_rows.append(
                        f'<tr data-invoice-id="{invoice_id}"><td>{invoice_id}</td><td>{escape(row["vendor_id"] or "")}</td>'
                        f'<td>{escape(row["invoice_number"] or "")}</td><td>{escape(row["status"] or "")}</td><td>'
                        f'<form method="post" action="/update">'
                        f'<input name="task_id" aria-label="Task ID" required>'
                        f'<input name="action" aria-label="Action" required>'
                        f'<input name="target" aria-label="Target invoice" value="{invoice_id}" required>'
                        f'<select name="status" aria-label="New status">'
                        f'<option>received</option><option>pending_approval</option><option>approved</option><option>rejected</option><option>disputed</option></select>'
                        f'<input name="expected_effect" aria-label="Expected effect" required>'
                        f'<input name="reason" aria-label="Reason" required>'
                        f'<button type="submit">Save status</button></form></td></tr>'
                    )
                body = ("<!doctype html><html><head><title>WorkPilot Finance Sandbox</title></head><body>"
                        "<h1>Finance Sandbox</h1><p>Local synthetic finance state</p><table><thead><tr><th>Invoice</th><th>Vendor</th>"
                        "<th>Invoice number</th><th>Status</th><th>Action</th></tr></thead><tbody>" + "".join(table_rows) + "</tbody></table></body></html>")
                self._send_html(body)

            def do_POST(self):
                if urlparse(self.path).path != "/update" or self.headers.get("Host") != f"{host}:{port}":
                    self.send_error(403)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 10_000:
                        raise ValueError("Invalid form size")
                    form = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True)
                    get = lambda key: form[key][0]
                    args = {"action": get("action"), "target": get("target"),
                            "parameters": {"status": get("status")}, "expected_effect": get("expected_effect"), "reason": get("reason")}
                    result = apply_update(get("task_id"), args)
                    if "error" in result:
                        self.send_error(403, result["error"])
                        return
                    body = ("<!doctype html><html><head><title>Sandbox result</title></head><body>"
                            f'<output data-result-invoice="{escape(args["target"])}" data-status="{escape(result["status"])}" '
                            f'data-verified="{str(result["verified"]).lower()}" data-already-applied="{str(result.get("already_applied", False)).lower()}"'
                            f'>Saved {escape(args["target"])} as {escape(result["status"])}</output>'
                            "</body></html>")
                    self._send_html(body)
                except Exception as exc:
                    self.send_error(400, str(exc))

            def _send_html(self, body: str) -> None:
                payload = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                return

        _server = ThreadingHTTPServer((host, port), SandboxHandler)
        threading.Thread(target=_server.serve_forever, daemon=True, name="workpilot-sandbox").start()

"""Very small local CORS proxy for the Lambda Runtime Interface Emulator.

Run this when testing the static UI against the local Lambda runtime.
It forwards requests to the RIE endpoint and injects permissive CORS headers.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import urllib.error
import urllib.request


TARGET = os.environ.get(
    "TARGET_URL", "http://localhost:9000/2015-03-31/functions/function/invocations"
)
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8787"))


def _cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
    }


class ProxyHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200, extra_headers=None):
        self.send_response(status)
        headers = {**_cors_headers(), **(extra_headers or {})}
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()

    def do_OPTIONS(self):  # noqa: N802
        self._set_headers(200)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length) if length else b""

        try:
            req = urllib.request.Request(
                TARGET,
                data=body,
                headers={"Content-Type": self.headers.get("content-type", "application/json")},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                resp_body = resp.read()
                # Copy through content-type if present
                resp_headers = {}
                if ct := resp.headers.get("Content-Type"):
                    resp_headers["Content-Type"] = ct
                self._set_headers(resp.status, resp_headers)
                self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            self._set_headers(e.code, {"Content-Type": "application/json"})
            self.wfile.write(e.read())
        except Exception as exc:
            self._set_headers(502, {"Content-Type": "text/plain"})
            self.wfile.write(f"Proxy error: {exc}".encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A003
        # Terse logging
        return


def run():
    server = HTTPServer((HOST, PORT), ProxyHandler)
    print(f"Local CORS proxy listening on http://{HOST}:{PORT} -> {TARGET}")
    server.serve_forever()


if __name__ == "__main__":
    run()

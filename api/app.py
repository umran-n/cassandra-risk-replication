from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "signals"


def load_payload(name: str):
    path = OUTPUT_DIR / name
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class SignalAPIHandler(BaseHTTPRequestHandler):
    server_version = "CassandraSignalAPI/0.6.0"

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path.rstrip("/") or "/"

        if path == "/health":
            return self._send_json({"status": "ok", "artifact_dir": str(OUTPUT_DIR)})
        if path == "/v1/sources/status":
            payload = load_payload("source_status.json")
            return self._send_json(payload or [], 200 if payload is not None else 404)
        if path == "/v1/events/families":
            payload = load_payload("family_signal_book.json")
            if payload is None:
                return self._send_json({"error": "family_signal_book.json not found"}, 404)
            theme = (query.get("theme") or [""])[0]
            if theme:
                payload = [row for row in payload if row.get("structural_theme") == theme]
            return self._send_json(payload)
        if path == "/v1/candidates/discovered":
            payload = load_payload("family_signal_book.json")
            if payload is None:
                return self._send_json({"error": "family_signal_book.json not found"}, 404)
            payload = [row for row in payload if bool(row.get("discovered"))]
            theme = (query.get("theme") or [""])[0]
            if theme:
                payload = [row for row in payload if row.get("structural_theme") == theme]
            return self._send_json(payload)
        if path == "/v1/signals/latest":
            payload = load_payload("signal_snapshots.json")
            if payload is None:
                return self._send_json({"error": "signal_snapshots.json not found"}, 404)
            theme = (query.get("theme") or [""])[0]
            if theme:
                payload = [row for row in payload if row.get("structural_theme") == theme]
            return self._send_json(payload)
        if path == "/v1/rsi/latest":
            payload = load_payload("rsi_snapshot.json")
            return self._send_json(payload or {"error": "rsi_snapshot.json not found"}, 200 if payload is not None else 404)
        if path == "/v1/graph/link-audit":
            payload = load_payload("link_audit.json")
            return self._send_json(payload or [], 200 if payload is not None else 404)

        self._send_json(
            {
                "error": "not_found",
                "available_endpoints": [
                    "/health",
                    "/v1/sources/status",
                    "/v1/events/families",
                    "/v1/candidates/discovered",
                    "/v1/signals/latest",
                    "/v1/rsi/latest",
                    "/v1/graph/link-audit",
                ],
            },
            404,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the Cassandra unified signal API from generated JSON artifacts.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), SignalAPIHandler)
    print(f"Serving Cassandra unified signal API on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

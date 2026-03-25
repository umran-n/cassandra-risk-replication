from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.api_service import (  # noqa: E402
    build_live_signal_artifacts,
    get_event_family_detail,
    get_signal_snapshot,
    list_event_families,
    list_link_audit,
    list_signal_snapshots,
    list_source_markets,
    load_payload,
    registry_meta,
    signal_output_dir,
)


OUTPUT_DIR = signal_output_dir(ROOT)


def _query_value(query: dict[str, list[str]], key: str, default: str = "") -> str:
    return (query.get(key) or [default])[0]


def _query_int(query: dict[str, list[str]], key: str) -> int | None:
    value = _query_value(query, key)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _query_float(query: dict[str, list[str]], key: str) -> float | None:
    value = _query_value(query, key)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _query_bool(query: dict[str, list[str]], key: str) -> bool | None:
    value = _query_value(query, key)
    if not value:
        return None
    lowered = value.lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    return None


class SignalAPIHandler(BaseHTTPRequestHandler):
    server_version = "CassandraSignalAPI/0.6.1"

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path.rstrip("/") or "/"

        if path == "/health":
            summary = load_payload(ROOT, "rsi_snapshot.json")
            return self._send_json({"status": "ok", "artifact_dir": str(OUTPUT_DIR), "has_rsi_snapshot": bool(summary)})
        if path == "/v1/meta/registry":
            return self._send_json(registry_meta(ROOT))
        if path == "/v1/sources/status":
            payload = load_payload(ROOT, "source_status.json")
            return self._send_json(payload or [], 200 if payload is not None else 404)
        if path == "/v1/sources/markets":
            payload = list_source_markets(
                ROOT,
                source=_query_value(query, "source"),
                theme=_query_value(query, "theme"),
                status=_query_value(query, "status"),
                min_quality=_query_float(query, "min_quality"),
                limit=_query_int(query, "limit"),
            )
            return self._send_json(payload)
        if path == "/v1/events/families":
            payload = list_event_families(
                ROOT,
                theme=_query_value(query, "theme"),
                discovered=_query_bool(query, "discovered"),
                selection_state=_query_value(query, "selection_state"),
            )
            return self._send_json(payload)
        if path.startswith("/v1/events/families/"):
            event_family_id = path.split("/v1/events/families/", 1)[1]
            payload = get_event_family_detail(ROOT, event_family_id)
            return self._send_json(payload or {"error": "event_family_not_found", "event_family_id": event_family_id}, 200 if payload else 404)
        if path == "/v1/candidates/discovered":
            payload = list_event_families(ROOT, theme=_query_value(query, "theme"), discovered=True)
            return self._send_json(payload)
        if path == "/v1/signals/latest":
            payload = list_signal_snapshots(ROOT, theme=_query_value(query, "theme"), source=_query_value(query, "source"))
            return self._send_json(payload)
        if path.startswith("/v1/signals/latest/"):
            event_family_id = path.split("/v1/signals/latest/", 1)[1]
            payload = get_signal_snapshot(ROOT, event_family_id)
            return self._send_json(payload or {"error": "signal_snapshot_not_found", "event_family_id": event_family_id}, 200 if payload else 404)
        if path == "/v1/rsi/latest":
            payload = load_payload(ROOT, "rsi_snapshot.json")
            return self._send_json(payload or {"error": "rsi_snapshot.json not found"}, 200 if payload is not None else 404)
        if path == "/v1/graph/link-audit":
            payload = list_link_audit(ROOT, source=_query_value(query, "source"), status=_query_value(query, "status"))
            return self._send_json(payload)

        self._send_json(
            {
                "error": "not_found",
                "available_endpoints": [
                    "/health",
                    "/v1/meta/registry",
                    "/v1/sources/status",
                    "/v1/sources/markets",
                    "/v1/events/families",
                    "/v1/events/families/{event_family_id}",
                    "/v1/candidates/discovered",
                    "/v1/signals/latest",
                    "/v1/signals/latest/{event_family_id}",
                    "/v1/rsi/latest",
                    "/v1/graph/link-audit",
                    "/v1/admin/refresh",
                ],
            },
            404,
        )

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path.rstrip("/") or "/"

        if path == "/v1/admin/refresh":
            body = self._read_json_body()
            refresh_sources = body.get("refresh_sources")
            if refresh_sources is None:
                refresh_sources = _query_bool(query, "refresh_sources")
            payload = build_live_signal_artifacts(ROOT, refresh=bool(refresh_sources))
            return self._send_json(
                {
                    "status": "refreshed",
                    "refresh_sources": bool(refresh_sources),
                    "selected_signals": len(payload["snapshots"]),
                    "rsi": payload["rsi_snapshot"]["rsi"],
                    "dominant_theme": payload["rsi_snapshot"]["dominant_theme"],
                }
            )

        self._send_json({"error": "not_found", "path": path}, 404)


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

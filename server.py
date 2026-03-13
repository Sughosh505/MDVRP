"""
server.py
---------
Pure Python stdlib HTTP server. No pip installs required.
Runs on Python 3.8+.

Routes:
  GET  /              → serve index.html
  POST /api/solve     → run MDVRP solver, return JSON
  GET  /api/health    → {"status": "ok"}

Start with: python3 server.py
Default port: 8000  (override: PORT=9000 python3 server.py)
"""

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# Import our solver
from solver import Depot, Customer, solve


# ─────────────────────────────────────────────
# Request validation helpers
# ─────────────────────────────────────────────

def validate_solve_request(body: dict) -> str | None:
    """Return error string if invalid, None if ok."""
    if "depots" not in body or not isinstance(body["depots"], list) or len(body["depots"]) == 0:
        return "depots: required, must be a non-empty array"
    if "customers" not in body or not isinstance(body["customers"], list) or len(body["customers"]) == 0:
        return "customers: required, must be a non-empty array"
    if "vehicle_capacity" not in body or not isinstance(body["vehicle_capacity"], (int, float)):
        return "vehicle_capacity: required, must be a number"
    if body["vehicle_capacity"] <= 0:
        return "vehicle_capacity: must be > 0"

    for i, dep in enumerate(body["depots"]):
        for field in ("id", "lon", "lat", "num_vehicles"):
            if field not in dep:
                return f"depots[{i}].{field}: required"
        if dep["num_vehicles"] < 1:
            return f"depots[{i}].num_vehicles: must be >= 1"

    for i, cust in enumerate(body["customers"]):
        for field in ("id", "lon", "lat", "demand"):
            if field not in cust:
                return f"customers[{i}].{field}: required"
        if cust["demand"] <= 0:
            return f"customers[{i}].demand: must be > 0"

    return None


def parse_solve_request(body: dict):
    depots = [
        Depot(
            id=int(d["id"]),
            lon=float(d["lon"]),
            lat=float(d["lat"]),
            num_vehicles=int(d["num_vehicles"]),
        )
        for d in body["depots"]
    ]
    customers = [
        Customer(
            id=int(c["id"]),
            lon=float(c["lon"]),
            lat=float(c["lat"]),
            demand=int(c["demand"]),
        )
        for c in body["customers"]
    ]
    vehicle_capacity = int(body["vehicle_capacity"])
    return depots, customers, vehicle_capacity


def result_to_json(result) -> dict:
    return {
        "status": result.status,
        "total_distance_m": result.total_distance_m,
        "total_distance_km": round(result.total_distance_m / 1000, 2),
        "num_routes": len(result.routes),
        "unserved_customers": result.unserved,
        "routes": [
            {
                "depot_id":        r.depot_id,
                "vehicle_id":      r.vehicle_id,
                "customer_ids":    r.customer_ids,
                "load":            r.load,
                "total_distance_m": r.total_distance_m,
            }
            for r in result.routes
        ],
    }


# ─────────────────────────────────────────────
# HTTP Handler
# ─────────────────────────────────────────────

class MDVRPHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Cleaner log format
        print(f"  {self.address_string()} {format % args}")

    # ── Shared response helpers ────────────────

    def send_json(self, code: int, data: dict):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        return json.loads(raw)

    # ── OPTIONS (CORS preflight) ───────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── GET ────────────────────────────────────

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self.send_html(get_frontend_html())

        elif path == "/api/health":
            self.send_json(200, {"status": "ok", "server": "mdvrp-simple"})

        else:
            self.send_json(404, {"error": f"Not found: {path}"})

    # ── POST ───────────────────────────────────

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/solve":
            self._handle_solve()
        else:
            self.send_json(404, {"error": f"Not found: {path}"})

    def _handle_solve(self):
        try:
            body = self.read_json_body()
            if body is None:
                self.send_json(400, {"error": "Empty request body"})
                return

            error = validate_solve_request(body)
            if error:
                self.send_json(400, {"error": error})
                return

            depots, customers, vehicle_capacity = parse_solve_request(body)

            print(f"  Solving: {len(depots)} depots, {len(customers)} customers, cap={vehicle_capacity}")

            result = solve(depots, customers, vehicle_capacity)
            response = result_to_json(result)

            print(f"  Done: {response['num_routes']} routes, {response['total_distance_km']} km")
            self.send_json(200, response)

        except json.JSONDecodeError as e:
            self.send_json(400, {"error": f"Invalid JSON: {e}"})
        except Exception as e:
            traceback.print_exc()
            self.send_json(500, {"error": f"Solver error: {str(e)}"})


# ─────────────────────────────────────────────
# Frontend HTML (inlined — no separate files needed)
# ─────────────────────────────────────────────

def get_frontend_html() -> str:
    """
    Returns the full HTML/CSS/JS frontend as a string.
    Uses Leaflet.js (free, no API key) + OpenStreetMap tiles.
    Imported from frontend.py to keep this file clean.
    """
    import importlib
    import frontend
    importlib.reload(frontend)
    return frontend.HTML


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def run():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), MDVRPHandler)
    print(f"\n  MDVRP Simple Server")
    print(f"  ───────────────────────────────")
    print(f"  URL:    http://localhost:{port}")
    print(f"  API:    http://localhost:{port}/api/solve")
    print(f"  Health: http://localhost:{port}/api/health")
    print(f"  ───────────────────────────────")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.server_close()


if __name__ == "__main__":
    run()

"""
server.py
---------
FastAPI server for the MDVRP solver.

Routes:
  GET  /              → serve frontend HTML
  POST /api/solve     → run MDVRP solver, return JSON
  GET  /api/health    → {"status": "ok"}
  GET  /docs          → Swagger UI (interactive API docs)
  GET  /redoc         → ReDoc documentation

Start with: python server.py
Default port: 8000  (override: PORT=9000 python server.py)
"""

import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import List
import uvicorn

# Import our solver
from solver import Depot, Customer, solve

# ─────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────

app = FastAPI(
    title="MDVRP Solver API",
    description=(
        "Multi-Depot Vehicle Routing Problem (MDVRP) solver using Google OR-Tools.\n\n"
        "Provide depots, customers, and a vehicle capacity to receive optimised routes."
    ),
    version="1.0.0",
    docs_url="/docs",   # Swagger UI
    redoc_url="/redoc", # ReDoc
)


# ─────────────────────────────────────────────
# Pydantic models (for /docs schema + validation)
# ─────────────────────────────────────────────

class DepotModel(BaseModel):
    id: int = Field(..., description="Unique depot identifier")
    lon: float = Field(..., description="Longitude of the depot")
    lat: float = Field(..., description="Latitude of the depot")
    num_vehicles: int = Field(..., ge=1, description="Number of vehicles available at this depot")

    model_config = {"json_schema_extra": {"example": {"id": 1, "lon": 77.5946, "lat": 12.9716, "num_vehicles": 3}}}


class CustomerModel(BaseModel):
    id: int = Field(..., description="Unique customer identifier")
    lon: float = Field(..., description="Longitude of the customer")
    lat: float = Field(..., description="Latitude of the customer")
    demand: int = Field(..., gt=0, description="Demand of the customer (must be > 0)")

    model_config = {"json_schema_extra": {"example": {"id": 101, "lon": 77.6101, "lat": 12.9352, "demand": 10}}}


class SolveRequest(BaseModel):
    depots: List[DepotModel] = Field(..., min_length=1, description="List of depots (at least one required)")
    customers: List[CustomerModel] = Field(..., min_length=1, description="List of customers (at least one required)")
    vehicle_capacity: int = Field(..., gt=0, description="Maximum load capacity of each vehicle")

    model_config = {
        "json_schema_extra": {
            "example": {
                "depots": [
                    {"id": 1, "lon": 77.5946, "lat": 12.9716, "num_vehicles": 2}
                ],
                "customers": [
                    {"id": 101, "lon": 77.6101, "lat": 12.9352, "demand": 10},
                    {"id": 102, "lon": 77.5800, "lat": 12.9600, "demand": 5},
                ],
                "vehicle_capacity": 50,
            }
        }
    }


class RouteModel(BaseModel):
    depot_id: int
    vehicle_id: int
    customer_ids: List[int]
    load: int
    total_distance_m: float


class SolveResponse(BaseModel):
    status: str = Field(..., description="Solver status, e.g. 'optimal' or 'feasible'")
    total_distance_m: float = Field(..., description="Total route distance in metres")
    total_distance_km: float = Field(..., description="Total route distance in kilometres")
    num_routes: int = Field(..., description="Number of routes generated")
    unserved_customers: List[int] = Field(..., description="Customer IDs that could not be served")
    routes: List[RouteModel]


class HealthResponse(BaseModel):
    status: str
    server: str


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def result_to_response(result) -> SolveResponse:
    return SolveResponse(
        status=result.status,
        total_distance_m=result.total_distance_m,
        total_distance_km=round(result.total_distance_m / 1000, 2),
        num_routes=len(result.routes),
        unserved_customers=result.unserved,
        routes=[
            RouteModel(
                depot_id=r.depot_id,
                vehicle_id=r.vehicle_id,
                customer_ids=r.customer_ids,
                load=r.load,
                total_distance_m=r.total_distance_m,
            )
            for r in result.routes
        ],
    )


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    """Serve the frontend HTML."""
    import importlib
    import frontend
    importlib.reload(frontend)
    return frontend.HTML


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def health():
    """Check that the server is running."""
    return HealthResponse(status="ok", server="mdvrp-fastapi")


@app.post(
    "/api/solve",
    response_model=SolveResponse,
    tags=["Solver"],
    summary="Solve MDVRP",
    description=(
        "Submit depots, customers, and vehicle capacity to get optimised vehicle routes. "
        "Returns routes for each vehicle assigned to each depot."
    ),
)
def api_solve(request: SolveRequest):
    """Run the MDVRP solver and return optimised routes."""
    depots = [
        Depot(id=d.id, lon=d.lon, lat=d.lat, num_vehicles=d.num_vehicles)
        for d in request.depots
    ]
    customers = [
        Customer(id=c.id, lon=c.lon, lat=c.lat, demand=c.demand)
        for c in request.customers
    ]

    print(f"  Solving: {len(depots)} depots, {len(customers)} customers, cap={request.vehicle_capacity}")

    try:
        result = solve(depots, customers, request.vehicle_capacity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Solver error: {str(e)}")

    response = result_to_response(result)
    print(f"  Done: {response.num_routes} routes, {response.total_distance_km} km")
    return response


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"\n  MDVRP FastAPI Server")
    print(f"  -------------------------------")
    print(f"  URL:    http://localhost:{port}")
    print(f"  Docs:   http://localhost:{port}/docs")
    print(f"  ReDoc:  http://localhost:{port}/redoc")
    print(f"  API:    http://localhost:{port}/api/solve")
    print(f"  Health: http://localhost:{port}/api/health")
    print(f"  -------------------------------")
    print(f"  Press Ctrl+C to stop\n")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)

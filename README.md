# MDVRP Solver

A **Multi-Depot Vehicle Routing Problem (MDVRP)** solver built with Google OR-Tools, exposed via a FastAPI REST API and an interactive Leaflet.js map frontend.

---

## Features

- **OR-Tools solver** — uses Google's constraint programming engine with Guided Local Search metaheuristic
- **Multi-depot support** — assign vehicles from multiple depot locations
- **Capacity constraints** — per-vehicle load limits enforced during routing
- **Unserved customer handling** — customers that can't be feasibly served are reported separately
- **Interactive map** — visualise depots, customers and routes on a Leaflet/OpenStreetMap map
- **REST API** — clean JSON API with full Swagger UI documentation

---

## Project Structure

```
MDVRP/
├── server.py        # FastAPI server — API routes, request/response models
├── solver.py        # OR-Tools MDVRP solver engine
├── frontend.py      # Frontend HTML/CSS/JS (Leaflet map, inlined as a Python string)
├── .env             # Environment variables (e.g. PYTHONPATH)
└── README.md
```

---

## Requirements

- Python 3.8+
- pip packages: `fastapi`, `uvicorn`, `ortools`

---

## Setup

### 1. Clone / enter the project directory

```bash
git clone https://github.com/Sughosh505/Multi-Depot-Vehicle-Routing-optimizer.git
cd Multi-Depot-Vehicle-Routing-optimizer
```

### 2. (Recommended) Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
```

### 3. Install dependencies

```bash
pip install fastapi uvicorn ortools
```

---

## Running the Server

```bash
python server.py
```

The server starts on **port 8000** by default. To use a different port:

```bash
PORT=9000 python server.py      # macOS / Linux
set PORT=9000 && python server.py  # Windows
```

### Available URLs

| URL | Description |
|-----|-------------|
| `http://localhost:8000/` | Interactive map frontend |
| `http://localhost:8000/docs` | Swagger UI — interactive API documentation |
| `http://localhost:8000/redoc` | ReDoc API reference |
| `http://localhost:8000/api/solve` | `POST` — run the solver |
| `http://localhost:8000/api/health` | `GET` — health check |

---

## API Reference

### `POST /api/solve`

Solve the MDVRP and return optimised vehicle routes.

**Request body:**

```json
{
  "depots": [
    { "id": 1, "lon": 77.5946, "lat": 12.9716, "num_vehicles": 2 }
  ],
  "customers": [
    { "id": 101, "lon": 77.6101, "lat": 12.9352, "demand": 10 },
    { "id": 102, "lon": 77.5800, "lat": 12.9600, "demand": 5  }
  ],
  "vehicle_capacity": 50
}
```

**Response:**

```json
{
  "status": "ok",
  "total_distance_m": 12345.6,
  "total_distance_km": 12.35,
  "num_routes": 1,
  "unserved_customers": [],
  "routes": [
    {
      "depot_id": 1,
      "vehicle_id": 0,
      "customer_ids": [101, 102],
      "load": 15,
      "total_distance_m": 12345.6
    }
  ]
}
```

> For full interactive documentation with a built-in request tester, open [`/docs`](http://localhost:8000/docs) in your browser.

### `GET /api/health`

Returns `{"status": "ok", "server": "mdvrp-fastapi"}` if the server is running.

---

## How the Solver Works

1. **Distance matrix** — haversine (great-circle) distances are computed between all depots and customers.
2. **OR-Tools setup** — `RoutingIndexManager` and `RoutingModel` are initialised with depot start/end nodes.
3. **Capacity dimension** — `AddDimensionWithVehicleCapacity` enforces the vehicle load limit.
4. **Dropped nodes** — each customer is wrapped in a disjunction so the solver can skip infeasible ones (with a high penalty to discourage dropping).
5. **Search strategy** — `PATH_CHEAPEST_ARC` for the initial solution, then `GUIDED_LOCAL_SEARCH` to improve it within a 3-second time limit.

---

## License

This project was created as part of the VIT 4th Semester curriculum.

"""
solver.py
---------
Self-contained MDVRP solver using Google OR-Tools.

Algorithm: Google OR-Tools Constraint Solver
  1. Compute unified haversine distance matrix for Depots + Customers.
  2. Setup pywrapcp.RoutingIndexManager and pywrapcp.RoutingModel.
  3. Enforce capacities via AddDimensionWithVehicleCapacity.
  4. Allow unserved customers using AddDisjunction with drop penalties.
  5. Return formatted solution.
"""

import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

try:
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp
except ImportError:
    routing_enums_pb2 = None
    pywrapcp = None


# ─────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────

@dataclass
class Depot:
    id: int
    lon: float
    lat: float
    num_vehicles: int


@dataclass
class Customer:
    id: int
    lon: float
    lat: float
    demand: int


@dataclass
class Route:
    depot_id: int
    vehicle_id: int
    customer_ids: List[int] = field(default_factory=list)
    total_distance_m: float = 0.0
    load: int = 0


@dataclass
class SolveResult:
    status: str           # "ok" | "infeasible"
    routes: List[Route]
    total_distance_m: float
    unserved: List[int]   # customer ids that couldn't be assigned
    error: Optional[str] = None


# ─────────────────────────────────────────────
# Distance
# ─────────────────────────────────────────────

EARTH_RADIUS_M = 6_371_000

def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = math.radians(lat2 - lat1)
    dlambda    = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def solve(
    depots: List[Depot],
    customers: List[Customer],
    vehicle_capacity: int,
) -> SolveResult:
    """
    Solve MDVRP using Google OR-Tools constraint solver.
    """
    if not depots:
        return SolveResult("infeasible", [], 0.0, [], "No depots provided")
    if not customers:
        return SolveResult("ok", [], 0.0, [])
    if pywrapcp is None:
        return SolveResult("infeasible", [], 0.0, [], "ortools is not installed. Please pip install ortools.")

    # 1. Prepare data model
    num_depots = len(depots)
    num_customers = len(customers)
    num_nodes = num_depots + num_customers

    # Create mapping of global_vehicle_index -> (depot_index, local_vehicle_index)
    global_vehicles = []
    starts = []
    ends = []
    vehicle_capacities = []
    for d_idx, depot in enumerate(depots):
        for local_v_idx in range(depot.num_vehicles):
            global_vehicles.append((d_idx, local_v_idx))
            starts.append(d_idx)
            ends.append(d_idx)
            vehicle_capacities.append(vehicle_capacity)

    num_vehicles = len(global_vehicles)
    if num_vehicles == 0:
        return SolveResult("infeasible", [], 0.0, [c.id for c in customers], "No vehicles available")

    # Unified list of coords (depots first, then customers)
    nodes = [(d.lon, d.lat) for d in depots] + [(c.lon, c.lat) for c in customers]
    
    # Demands (0 for depots, actual demand for customers)
    demands = [0] * num_depots + [c.demand for c in customers]

    # Precompute Distance Matrix (rounded to integer meters for OR-Tools)
    distance_matrix = []
    for i in range(num_nodes):
        row = []
        for j in range(num_nodes):
            row.append(int(round(haversine(nodes[i][0], nodes[i][1], nodes[j][0], nodes[j][1]))))
        distance_matrix.append(row)

    # 2. Setup OR-Tools
    manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    # Distance callback
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Demand callback & Capacity constraint
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        vehicle_capacities,
        True,  # start cumul to zero
        'Capacity'
    )

    # 3. Allow dropped customers (disjunctions)
    # Give a penalty to dropping a customer so the solver tries to serve them
    # Penalty needs to be higher than the maximum possible route cost savings
    penalty = 10_000_000
    for node in range(num_depots, num_nodes):
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    # 4. Search Parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.FromSeconds(3) # Bound solve time to 3 seconds for interactivity

    # 5. Solve
    solution = routing.SolveWithParameters(search_parameters)

    # 6. Reconstruct output
    if not solution:
        return SolveResult("infeasible", [], 0.0, [c.id for c in customers], "OR-Tools failed to find any solution")

    routes = []
    total_dist_m = 0.0

    for global_v_idx in range(num_vehicles):
        index = routing.Start(global_v_idx)
        d_idx, local_v_idx = global_vehicles[global_v_idx]
        depot = depots[d_idx]
        
        route_dist = 0
        route_load = 0
        customer_ids = []

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            # If node is a customer
            if node_index >= num_depots:
                customer = customers[node_index - num_depots]
                customer_ids.append(customer.id)
                route_load += customer.demand
            
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            # Get exact float distance for accurate reporting instead of the rounded int used by solver
            if not routing.IsEnd(index):
                next_node_index = manager.IndexToNode(index)
                route_dist += haversine(
                    nodes[node_index][0], nodes[node_index][1],
                    nodes[next_node_index][0], nodes[next_node_index][1]
                )
            else:
                 # Need dist back to depot (the End node corresponds to the depot)
                 end_node_index = starts[global_v_idx]
                 route_dist += haversine(
                    nodes[node_index][0], nodes[node_index][1],
                    nodes[end_node_index][0], nodes[end_node_index][1]
                 )

        if customer_ids:
            routes.append(Route(
                depot_id=depot.id,
                vehicle_id=local_v_idx,
                customer_ids=customer_ids,
                total_distance_m=round(route_dist, 1),
                load=route_load
            ))
            total_dist_m += route_dist

    # Check unserved
    unserved = []
    for node in range(num_depots, num_nodes):
        if solution.Value(routing.NextVar(manager.NodeToIndex(node))) == manager.NodeToIndex(node):
            unserved.append(customers[node - num_depots].id)

    status = "infeasible" if len(unserved) > 0 else "ok"
    return SolveResult(status, routes, round(total_dist_m, 1), unserved)

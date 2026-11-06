"""Integer transportation optimizer. Shared capacities span every product."""

import math
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix


def transport_cost(source, dest):
    return round(
        0.35
        + math.hypot(source.latitude - dest.latitude, source.longitude - dest.longitude)
        * 0.12,
        2,
    )


def optimize(inventory, locations, forecasts, weights, solver="milp", supply_factor=1):
    loc = {x.id: x for x in locations}
    stock = {(x.product_id, x.location_id): x for x in inventory}
    used = {
        l.id: sum(x.quantity_on_hand for x in inventory if x.location_id == l.id)
        for l in locations
    }
    room = {
        l.id: max(0, min(l.storage_capacity - used[l.id], l.fulfillment_capacity))
        for l in locations
    }
    supply = {
        (x.product_id, x.location_id): int(
            max(0, x.quantity_on_hand - x.quantity_reserved - x.safety_stock)
            * supply_factor
        )
        for x in inventory
        if loc[x.location_id].location_type in ["Warehouse", "Distribution Center"]
    }
    needs = {}
    for f in forecasts:
        item = stock[(f["product_id"], f["location_id"])]
        needs[(f["product_id"], f["location_id"])] = max(
            0,
            math.ceil(
                f["predicted_demand"]
                + item.safety_stock
                - (item.quantity_on_hand - item.quantity_reserved)
            ),
        )
    edges = []
    for (pid, dest), need in sorted(needs.items()):
        if not need or not room[dest]:
            continue
        for (p, src), available in supply.items():
            if p == pid and available:
                cost = (
                    transport_cost(loc[src], loc[dest])
                    + weights["reallocation_cost"]
                    + weights["holding_cost"]
                )
                penalty = weights["stockout_penalty"] * (
                    weights["online_priority"]
                    if loc[dest].location_type == "Online Fulfillment Center"
                    else 1
                )
                edges.append(
                    (pid, src, dest, cost, penalty, min(available, need, room[dest]))
                )
    quantities = []
    method = "greedy"
    if edges and solver == "milp":
        keys = (
            [("s", *k) for k in supply]
            + [("d", *k) for k in needs]
            + [("c", k) for k in room]
        )
        index = {k: i for i, k in enumerate(keys)}
        matrix = lil_matrix((len(keys), len(edges)))
        for j, (p, s, d, *_) in enumerate(edges):
            for key in [("s", p, s), ("d", p, d), ("c", d)]:
                matrix[index[key], j] = 1
        upper = list(supply.values()) + list(needs.values()) + list(room.values())
        result = milp(
            np.array([e[3] - e[4] for e in edges]),
            integrality=np.ones(len(edges)),
            bounds=Bounds(0, [e[5] for e in edges]),
            constraints=LinearConstraint(matrix.tocsr(), 0, upper),
            options={"time_limit": 20},
        )
        if result.success:
            quantities = np.rint(result.x).astype(int).tolist()
            method = "scipy_milp"
    if not quantities:
        quantities = [0] * len(edges)
        remaining_supply = supply.copy()
        remaining_needs = needs.copy()
        capacity = room.copy()
        for j in sorted(
            range(len(edges)), key=lambda j: (edges[j][3] - edges[j][4], edges[j][1])
        ):
            p, s, d, cost, penalty, _ = edges[j]
            if cost >= penalty:
                continue
            q = min(remaining_supply[p, s], remaining_needs[p, d], capacity[d])
            quantities[j] = q
            remaining_supply[p, s] -= q
            remaining_needs[p, d] -= q
            capacity[d] -= q
    moves = []
    cost = 0
    avoided = 0
    for e, q in zip(edges, quantities):
        if q:
            p, s, d, c, penalty, _ = e
            cost += q * c
            avoided += q * penalty
            moves.append(
                dict(
                    product_id=p,
                    source_location_id=s,
                    destination_location_id=d,
                    sales_channel=(
                        "online"
                        if loc[d].location_type == "Online Fulfillment Center"
                        else "offline"
                    ),
                    allocated_quantity=q,
                    estimated_cost=round(q * c, 2),
                    explanation="Replenish forecast demand and safety stock; source reservations and network capacity protected.",
                )
            )
    shortage = sum(needs.values())
    allocated = sum(quantities)
    baseline_cost = sum(
        q
        * weights["stockout_penalty"]
        * (
            weights["online_priority"]
            if loc[d].location_type == "Online Fulfillment Center"
            else 1
        )
        for (p, d), q in needs.items()
    )
    return {
        "recommendations": moves,
        "method": method,
        "baseline_shortage": shortage,
        "remaining_shortage": shortage - allocated,
        "baseline_cost": round(baseline_cost, 2),
        "total_allocated": allocated,
        "total_cost": round(cost, 2),
        "estimated_savings": round(avoided - cost, 2),
        "objective_value": round(baseline_cost - avoided + cost, 2),
        "stockout_risk": round((shortage - allocated) / max(1, shortage), 4),
        "unmet_safety_stock": "Prioritized with demand; shortage may prevent full replenishment.",
    }

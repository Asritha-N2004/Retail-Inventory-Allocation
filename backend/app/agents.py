import time
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy import select, delete, func
from .database import *
from .forecasting import forecast
from .optimization import optimize

AGENTS = [
    ("supervisor", "Supervisor", "Coordinate, validate and audit workflow"),
    ("demand", "Demand Forecasting", "Forecast demand and uncertainty"),
    ("monitor", "Inventory Monitoring", "Detect shortages and excess stock"),
    ("online", "Online Channel", "Calculate online fulfillment requirements"),
    ("offline", "Offline Store", "Calculate store replenishment"),
    ("warehouse", "Warehouse", "Protect reservations and identify supply"),
    ("risk", "Risk Management", "Detect operational bottlenecks"),
    ("allocation", "Inventory Allocation", "Minimize constrained operational cost"),
    ("logistics", "Logistics", "Estimate transfer costs and delivery times"),
    ("pricing", "Pricing & Promotion", "Suggest promotions for slow stock"),
]


def forecast_network(s, horizon=7, model="exponential_smoothing"):
    groups = defaultdict(list)
    last = s.scalar(select(func.max(Sale.sale_date)))
    since = (
        (date.fromisoformat(last) - timedelta(days=89)).isoformat() if last else "9999"
    )
    for pid, lid, qty in s.execute(
        select(Sale.product_id, Sale.location_id, Sale.quantity_sold)
        .where(Sale.sale_date >= since)
        .order_by(Sale.sale_date)
    ):
        groups[pid, lid].append(qty)
    dests = s.scalars(
        select(Location).where(
            Location.location_type.in_(["Physical Store", "Online Fulfillment Center"])
        )
    ).all()
    rows = []
    for item in s.scalars(select(Inventory)):
        if item.location_id not in {l.id for l in dests}:
            continue
        rows.append(
            dict(
                product_id=item.product_id,
                location_id=item.location_id,
                channel=(
                    "online"
                    if next(l for l in dests if l.id == item.location_id).location_type
                    == "Online Fulfillment Center"
                    else "offline"
                ),
                **forecast(groups[item.product_id, item.location_id], horizon, model),
            )
        )
    return rows


def execute(
    s,
    run,
    horizon=7,
    model="exponential_smoothing",
    agent_id=None,
    publish=lambda x: None,
):
    state = {}
    inventory = s.scalars(select(Inventory)).all()
    locations = s.scalars(select(Location)).all()
    weights = s.get(Setting, "optimization").value
    order = [AGENTS[0]] + AGENTS[1:]
    try:
        for aid, name, role in order:
            start = time.perf_counter()
            execution = AgentExecution(
                agent_name=name,
                execution_id=run.id,
                status="running",
                input_summary={"keys": list(state), "horizon": horizon},
                created_at=now(),
            )
            s.add(execution)
            s.flush()
            publish(
                {"type": "agent", "agent": aid, "status": "running", "run_id": run.id}
            )
            if aid == "supervisor":
                output = {
                    "workflow": "created",
                    "policy": "Explicit approval required",
                    "dependencies": [a[0] for a in AGENTS[1:]],
                }
            elif aid == "demand":
                rows = forecast_network(s, horizon, model)
                state["forecasts"] = rows
                s.execute(delete(Forecast))
                s.add_all([Forecast(**r) for r in rows])
                output = {
                    "forecasts": len(rows),
                    "predicted_demand": round(sum(r["predicted_demand"] for r in rows)),
                    "model": model,
                }
            elif aid == "monitor":
                output = {
                    "low_stock": sum(
                        x.quantity_on_hand - x.quantity_reserved < x.reorder_level
                        for x in inventory
                    ),
                    "overstock": sum(
                        x.quantity_on_hand > 5 * x.reorder_level for x in inventory
                    ),
                    "units": sum(x.quantity_on_hand for x in inventory),
                }
            elif aid in ["online", "offline"]:
                output = {
                    "channel": aid,
                    "predicted_demand": round(
                        sum(
                            r["predicted_demand"]
                            for r in state["forecasts"]
                            if r["channel"] == aid
                        )
                    ),
                }
            elif aid == "warehouse":
                output = {
                    "available_supply": sum(
                        max(
                            0, x.quantity_on_hand - x.quantity_reserved - x.safety_stock
                        )
                        for x in inventory
                        if x.location_id
                        in {
                            l.id
                            for l in locations
                            if l.location_type in ["Warehouse", "Distribution Center"]
                        }
                    )
                }
            elif aid == "risk":
                output = {
                    "at_risk_positions": sum(
                        x.quantity_on_hand - x.quantity_reserved < x.safety_stock
                        for x in inventory
                    ),
                    "supplier_delays": [
                        p.id
                        for p in s.scalars(
                            select(PurchaseOrder).where(
                                PurchaseOrder.status == "delayed"
                            )
                        )
                    ],
                }
            elif aid == "allocation":
                result = optimize(inventory, locations, state["forecasts"], weights)
                state["optimization"] = result
                s.add_all(
                    [
                        Allocation(allocation_run_id=run.id, **r)
                        for r in result["recommendations"]
                    ]
                )
                output = {k: v for k, v in result.items() if k != "recommendations"}
            elif aid == "logistics":
                output = {
                    "shipments": len(state["optimization"]["recommendations"]),
                    "estimated_cost": state["optimization"]["total_cost"],
                    "estimated_hours_range": [12, 48],
                }
            else:
                output = {
                    "suggestions": [
                        {
                            "product_id": x.product_id,
                            "location_id": x.location_id,
                            "suggestion": "Review 10% promotion; prices unchanged",
                        }
                        for x in inventory
                        if x.quantity_on_hand > 8 * x.reorder_level
                    ][:20]
                }
            state[aid] = output
            execution.status = "completed"
            execution.output_summary = output
            execution.confidence = (
                1
                if aid != "demand"
                else sum(r["confidence_score"] for r in state["forecasts"])
                / max(1, len(state["forecasts"]))
            )
            execution.execution_duration = time.perf_counter() - start
            s.add(
                Message(
                    execution_id=run.id,
                    sender=aid,
                    receiver=(
                        "supervisor"
                        if aid in ["logistics", "pricing"]
                        else "allocation"
                    ),
                    payload=output,
                )
            )
            publish(
                {"type": "agent", "agent": aid, "status": "completed", "run_id": run.id}
            )
        result = state["optimization"]
        run.status = "waiting_for_approval"
        for key in [
            "total_allocated",
            "total_cost",
            "objective_value",
            "stockout_risk",
        ]:
            setattr(run, key, result[key])
        changes = defaultdict(int)
        for movement in result["recommendations"]:
            changes[movement["product_id"], movement["source_location_id"]] -= movement[
                "allocated_quantity"
            ]
            changes[
                movement["product_id"], movement["destination_location_id"]
            ] += movement["allocated_quantity"]
        projection = [
            {
                "product_id": i.product_id,
                "location_id": i.location_id,
                "version": i.version,
                "before": i.quantity_on_hand,
                "change": changes[i.product_id, i.location_id],
                "after": i.quantity_on_hand + changes[i.product_id, i.location_id],
            }
            for i in inventory
            if (i.product_id, i.location_id) in changes
        ]
        run.details = {
            **{k: v for k, v in result.items() if k != "recommendations"},
            "projection": projection,
        }
        run.completed_at = now()
        s.add(
            Message(
                execution_id=run.id,
                sender="supervisor",
                receiver="administrator",
                payload={"validation": "passed", "approval_required": True},
            )
        )
        s.add(
            Notification(
                message=f"Allocation run #{run.id} ready for review: {run.total_allocated:,} units."
            )
        )
        publish({"type": "optimization", "status": run.status, "run_id": run.id})
    except Exception as exc:
        execution.status = "failed"
        execution.error_message = str(exc)
        run.status = "failed"
        run.details = {"error": str(exc)}
        publish({"type": "error", "run_id": run.id, "detail": str(exc)})
        raise

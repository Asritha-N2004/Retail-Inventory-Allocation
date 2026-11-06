from collections import defaultdict
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, update, func
from .database import *


def inventory_transaction(s, run_id, user, rollback=False):
    run = s.scalar(select(Run).where(Run.id == run_id).with_for_update())
    if not run:
        raise HTTPException(404, "Run not found")
    expected = "approved" if rollback else "waiting_for_approval"
    target = "rolled_back" if rollback else "approved"
    claimed = s.execute(
        update(Run)
        .where(Run.id == run_id, Run.status == expected)
        .values(status=target)
    )
    if claimed.rowcount != 1:
        raise HTTPException(
            409, f"Run must be {expected}; duplicate or conflicting operation"
        )
    # Lock all locations in stable order. Every inventory writer follows this protocol.
    locations = s.scalars(
        select(Location).order_by(Location.id).with_for_update()
    ).all()
    rows = s.scalars(select(Inventory).order_by(Inventory.id).with_for_update()).all()
    stock = {(r.product_id, r.location_id): r for r in rows}
    if not rollback:
        for projected in run.details.get("projection", []):
            item = stock.get((projected["product_id"], projected["location_id"]))
            if item is None or item.version != projected["version"]:
                raise HTTPException(
                    409,
                    "Inventory changed since this proposal; generate a new allocation run",
                )
    moves = s.scalars(
        select(Allocation).where(Allocation.allocation_run_id == run_id)
    ).all()
    changes = defaultdict(int)
    for a in moves:
        sign = -1 if rollback else 1
        changes[a.product_id, a.source_location_id] -= sign * a.allocated_quantity
        changes[a.product_id, a.destination_location_id] += sign * a.allocated_quantity
    for key, delta in changes.items():
        item = stock.get(key)
        if not item:
            raise HTTPException(409, "Inventory position no longer exists")
        if item.quantity_on_hand + delta < item.quantity_reserved + (
            item.safety_stock if delta < 0 and not rollback else 0
        ):
            raise HTTPException(
                409,
                "Stale recommendation: reserved stock or safety stock would be consumed. Run optimization again.",
            )
    for l in locations:
        total = sum(
            r.quantity_on_hand + changes.get((r.product_id, r.location_id), 0)
            for r in rows
            if r.location_id == l.id
        )
        incoming = sum(max(0, d) for (p, dest), d in changes.items() if dest == l.id)
        if total > l.storage_capacity or (
            not rollback and incoming > l.fulfillment_capacity
        ):
            raise HTTPException(409, "Capacity changed; allocation cannot be applied")
    for key, delta in changes.items():
        item = stock[key]
        previous = {"quantity_on_hand": item.quantity_on_hand, "version": item.version}
        # Compare-and-swap also protects SQLite where SELECT FOR UPDATE is ignored.
        changed = s.execute(
            update(Inventory)
            .where(Inventory.id == item.id, Inventory.version == item.version)
            .values(
                quantity_on_hand=item.quantity_on_hand + delta,
                version=item.version + 1,
                last_updated=now(),
            )
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "Concurrent inventory update; retry")
        s.add(
            Audit(
                user_id=user.id,
                action=target,
                entity_type="inventory",
                entity_id=item.id,
                previous_value=previous,
                new_value={
                    "quantity_on_hand": item.quantity_on_hand + delta,
                    "run_id": run_id,
                },
            )
        )
    for a in moves:
        a.allocation_status = target
        if not rollback:
            s.add(
                Transfer(
                    allocation_id=a.id,
                    source_location_id=a.source_location_id,
                    destination_location_id=a.destination_location_id,
                    product_id=a.product_id,
                    quantity=a.allocated_quantity,
                    estimated_cost=a.estimated_cost,
                    estimated_hours=24,
                    status="planned",
                )
            )
        else:
            t = s.scalar(select(Transfer).where(Transfer.allocation_id == a.id))
            if t and t.status == "delivered":
                raise HTTPException(
                    409, "Delivered shipment cannot be compensated automatically"
                )
            if t:
                t.status = "cancelled"
    s.add(
        Audit(
            user_id=user.id,
            action=target,
            entity_type="optimization_run",
            entity_id=run_id,
            previous_value={"status": expected},
            new_value={"status": target},
        )
    )
    s.add(Notification(message=f"Run #{run_id} {target}; inventory ledger updated."))
    return {"id": run_id, "status": target, "units": run.total_allocated}

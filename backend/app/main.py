import os, asyncio, logging, json, time, csv, io
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Literal
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func, update, delete
from sqlalchemy.exc import OperationalError, IntegrityError
from .database import *
from .security import (
    current_user,
    manager,
    administrator,
    token,
    passwords,
    throttle,
    secret,
)
from .seed import seed
from .agents import AGENTS, execute, forecast_network
from .optimization import optimize
from .transactions import inventory_transaction
from .analytics import monthly_sales_query
import jwt

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("retail")
events = []
event_seq = 0
live_agents = {}


def publish(payload):
    global event_seq
    event_seq += 1
    events.append({"sequence": event_seq, "timestamp": now(), **payload})
    if payload.get("type") == "agent":
        live_agents[payload["agent"]] = payload["status"]
    if payload.get("type") == "error":
        for key in live_agents:
            live_agents[key] = "failed"
    if len(events) > 500:
        del events[:-500]


@asynccontextmanager
async def lifespan(app):
    # Cloud schema/seed is initialized once by the release command, not per invocation.
    if os.getenv("VERCEL"):
        yield
        return
    migrate()
    if os.getenv("AUTO_SEED", "true") == "true":
        seed()
    # Any interrupted process-local work must be visible rather than remain running forever.
    with Session.begin() as s:
        s.execute(
            update(Run)
            .where(Run.status == "running")
            .values(
                status="failed",
                details={"error": "Server restarted before workflow completed"},
            )
        )
    yield


app = FastAPI(title="Nexus Retail Intelligence", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080",
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info(
        json.dumps(
            {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            }
        )
    )
    return response


@app.exception_handler(OperationalError)
async def db_conflict(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=409,
        content={"detail": "Database busy or unavailable; retry the transaction"},
    )


@app.exception_handler(IntegrityError)
async def integrity(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=409, content={"detail": "Database constraint conflict"}
    )


def row(obj):
    if obj is None:
        raise HTTPException(404, "Record not found")
    return {
        c.name: (
            str(getattr(obj, c.name))
            if isinstance(getattr(obj, c.name), Decimal)
            else getattr(obj, c.name)
        )
        for c in obj.__table__.columns
    }


def audit(s, user, action, kind, id, old, new):
    s.add(
        Audit(
            user_id=user.id,
            action=action,
            entity_type=kind,
            entity_id=id,
            previous_value=old,
            new_value=new,
        )
    )


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


@app.post("/api/auth/login")
def login(body: Login, request: Request):
    throttle(request.client.host)
    with Session() as s:
        u = s.scalar(select(User).where(User.username == body.username))
        if not u or not passwords.verify(body.password, u.password_hash):
            raise HTTPException(401, "Incorrect username or password")
        return {
            "access_token": token(u),
            "token_type": "bearer",
            "user": {"id": u.id, "username": u.username, "role": u.role},
        }


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}


@app.get("/health")
def health():
    with Session() as s:
        s.execute(select(1))
    return {"status": "ok", "database": "connected", "version": "1.0.0"}


class ProductBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(min_length=1, max_length=60)
    product_name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    description: str = ""
    unit_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    selling_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    weight: float = Field(default=1, gt=0)
    dimensions: str = "20x20x20 cm"
    active: bool = True


@app.get("/api/products")
def products(
    search: str = "",
    category: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    sort: Literal["sku", "product_name", "category"] = "sku",
    user=Depends(current_user),
):
    with Session() as s:
        q = select(Product).where(Product.active == True)
        if search:
            q = q.where(
                (Product.product_name.ilike(f"%{search}%"))
                | (Product.sku.ilike(f"%{search}%"))
            )
        if category:
            q = q.where(Product.category == category)
        total = s.scalar(select(func.count()).select_from(q.subquery()))
        return {
            "items": [
                row(p)
                for p in s.scalars(
                    q.order_by(getattr(Product, sort))
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ],
            "total": total,
        }


@app.post("/api/products", status_code=201)
def create_product(body: ProductBody, user=Depends(manager)):
    with Session.begin() as s:
        p = Product(**body.model_dump())
        s.add(p)
        s.flush()
        audit(s, user, "create", "product", p.id, None, row(p))
        return row(p)


@app.get("/api/products/{id}")
def product(id: int, user=Depends(current_user)):
    with Session() as s:
        return row(s.get(Product, id))


@app.put("/api/products/{id}")
def edit_product(id: int, body: ProductBody, user=Depends(manager)):
    with Session.begin() as s:
        p = s.get(Product, id)
        old = row(p)
        for k, v in body.model_dump().items():
            setattr(p, k, v)
        p.updated_at = now()
        audit(s, user, "update", "product", id, old, row(p))
        return row(p)


@app.delete("/api/products/{id}")
def delete_product(id: int, user=Depends(manager)):
    with Session.begin() as s:
        p = s.get(Product, id)
        old = row(p)
        p.active = False
        audit(s, user, "deactivate", "product", id, old, row(p))
        return {"status": "deactivated"}


def inventory_rows(s):
    result = []
    for i, p, l in s.execute(
        select(Inventory, Product, Location)
        .join(Product, Inventory.product_id == Product.id)
        .join(Location, Inventory.location_id == Location.id)
        .where(Product.active == True)
    ):
        available = i.quantity_on_hand - i.quantity_reserved
        result.append(
            {
                **row(i),
                "sku": p.sku,
                "product_name": p.product_name,
                "category": p.category,
                "location_name": l.location_name,
                "location_type": l.location_type,
                "region": l.region,
                "quantity_available": available,
                "channel": (
                    "online"
                    if l.location_type == "Online Fulfillment Center"
                    else (
                        "offline"
                        if l.location_type == "Physical Store"
                        else "warehouse"
                    )
                ),
                "status": (
                    "critical"
                    if available < i.safety_stock
                    else (
                        "low"
                        if available < i.reorder_level
                        else "excess" if available > i.reorder_level * 5 else "healthy"
                    )
                ),
            }
        )
    return result


@app.get("/api/inventory")
def inventory(
    search: str = "",
    status: str = "",
    channel: str = "",
    location_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=2500),
    sort: Literal["sku", "quantity_available", "location_name"] = "sku",
    descending: bool = False,
    user=Depends(current_user),
):
    with Session() as s:
        data = [
            r
            for r in inventory_rows(s)
            if (not search or search.lower() in (r["sku"] + r["product_name"]).lower())
            and (not status or r["status"] == status)
            and (not channel or r["channel"] == channel)
            and (not location_id or r["location_id"] == location_id)
        ]
        data.sort(key=lambda r: r[sort], reverse=descending)
        return {
            "items": data[(page - 1) * page_size : page * page_size],
            "total": len(data),
        }


@app.get("/api/inventory/low-stock")
def low(user=Depends(current_user)):
    with Session() as s:
        return [r for r in inventory_rows(s) if r["status"] in ["low", "critical"]]


@app.get("/api/inventory/overstock")
def excess(user=Depends(current_user)):
    with Session() as s:
        return [r for r in inventory_rows(s) if r["status"] == "excess"]


@app.get("/api/inventory/{product_id}")
def product_inventory(product_id: int, user=Depends(current_user)):
    with Session() as s:
        return [r for r in inventory_rows(s) if r["product_id"] == product_id]


class StockUpdate(BaseModel):
    quantity_on_hand: int = Field(ge=0)
    quantity_reserved: int = Field(ge=0)
    safety_stock: int = Field(ge=0)
    reorder_level: int = Field(ge=0)
    version: int = Field(ge=0)


@app.put("/api/inventory/{id}")
def update_stock(id: int, body: StockUpdate, user=Depends(manager)):
    if body.quantity_reserved > body.quantity_on_hand:
        raise HTTPException(422, "Reservations exceed stock")
    with Session.begin() as s:
        item = s.get(Inventory, id)
        old = row(item)
        loc = s.scalar(
            select(Location).where(Location.id == item.location_id).with_for_update()
        )
        total = s.scalar(
            select(func.sum(Inventory.quantity_on_hand)).where(
                Inventory.location_id == loc.id
            )
        )
        if total - item.quantity_on_hand + body.quantity_on_hand > loc.storage_capacity:
            raise HTTPException(409, "Storage capacity exceeded")
        changed = s.execute(
            update(Inventory)
            .where(Inventory.id == id, Inventory.version == body.version)
            .values(
                **body.model_dump(exclude={"version"}),
                version=body.version + 1,
                last_updated=now(),
            )
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "Inventory changed; refresh before saving")
        audit(s, user, "adjust", "inventory", id, old, body.model_dump())
        publish({"type": "inventory", "id": id})
        return {"status": "updated"}


@app.get("/api/locations")
def locations(user=Depends(current_user)):
    with Session() as s:
        return [
            {
                **row(l),
                "units": s.scalar(
                    select(func.sum(Inventory.quantity_on_hand)).where(
                        Inventory.location_id == l.id
                    )
                )
                or 0,
            }
            for l in s.scalars(select(Location))
        ]


def summary(s):
    items = inventory_rows(s)
    runs = s.scalars(select(Run).where(Run.status == "approved")).all()
    total = sum(x["quantity_on_hand"] for x in items)
    sales = s.scalar(select(func.sum(Sale.quantity_sold))) or 0
    metrics = s.scalars(select(Forecast)).all()
    return {
        "total_products": s.scalar(
            select(func.count(Product.id)).where(Product.active == True)
        ),
        "total_inventory": total,
        "total_warehouses": s.scalar(
            select(func.count(Location.id)).where(
                Location.location_type.in_(["Warehouse", "Distribution Center"])
            )
        ),
        "total_stores": s.scalar(
            select(func.count(Location.id)).where(
                Location.location_type == "Physical Store"
            )
        ),
        "online_inventory": sum(
            x["quantity_on_hand"] for x in items if x["channel"] == "online"
        ),
        "offline_inventory": sum(
            x["quantity_on_hand"] for x in items if x["channel"] == "offline"
        ),
        "low_stock": sum(x["status"] in ["low", "critical"] for x in items),
        "overstock": sum(x["status"] == "excess" for x in items),
        "stockout_risk": sum(x["status"] == "critical" for x in items)
        / max(1, len(items)),
        "inventory_turnover": round(sales / max(1, total), 2),
        "forecast_accuracy": (
            round(
                sum(x.confidence_score for x in metrics) / max(1, len(metrics)) * 100, 1
            )
            if metrics
            else None
        ),
        "estimated_savings": round(
            sum(float(r.details.get("estimated_savings", 0)) for r in runs), 2
        ),
        "pending_approvals": s.scalar(
            select(func.count(Run.id)).where(Run.status == "waiting_for_approval")
        ),
        "sales_units": sales,
    }


@app.get("/api/dashboard/summary")
def dashboard(user=Depends(current_user)):
    with Session() as s:
        return summary(s)


@app.get("/api/dashboard/inventory-health")
def inventory_health(user=Depends(current_user)):
    with Session() as s:
        rows = inventory_rows(s)
        return [
            {"name": status, "value": sum(x["status"] == status for x in rows)}
            for status in ["healthy", "low", "critical", "excess"]
        ]


@app.get("/api/dashboard/sales-performance")
def sales_performance(user=Depends(current_user)):
    with Session() as s:
        return [
            {
                "month": month,
                "channel": channel,
                "units": int(units),
                "revenue": str(revenue),
            }
            for month, channel, units, revenue in s.execute(monthly_sales_query())
        ]


@app.get("/api/dashboard/channel-performance")
def channel_performance(user=Depends(current_user)):
    with Session() as s:
        rows = inventory_rows(s)
        return [
            {
                "name": c,
                "units": sum(x["quantity_on_hand"] for x in rows if x["channel"] == c),
                "reserved": sum(
                    x["quantity_reserved"] for x in rows if x["channel"] == c
                ),
            }
            for c in ["warehouse", "offline", "online"]
        ]


class ForecastBody(BaseModel):
    horizon: int = Field(default=7, ge=1, le=90)
    model: Literal[
        "moving_average", "exponential_smoothing", "linear_regression", "random_forest"
    ] = "exponential_smoothing"


@app.post("/api/forecast/run")
def run_forecast(body: ForecastBody, user=Depends(manager)):
    with Session.begin() as s:
        data = forecast_network(s, body.horizon, body.model)
        s.execute(delete(Forecast))
        s.add_all([Forecast(**f) for f in data])
        audit(s, user, "forecast", "forecast", 0, None, body.model_dump())
        return {"count": len(data), "items": data[:100]}


@app.get("/api/forecast")
def forecasts(
    product_id: int | None = None,
    location_id: int | None = None,
    channel: str = "",
    user=Depends(current_user),
):
    with Session() as s:
        q = select(Forecast)
        if product_id:
            q = q.where(Forecast.product_id == product_id)
        if location_id:
            q = q.where(Forecast.location_id == location_id)
        if channel:
            q = q.where(Forecast.channel == channel)
        return [row(f) for f in s.scalars(q)]


@app.get("/api/forecast/{product_id}")
def forecast_product(product_id: int, user=Depends(current_user)):
    return forecasts(product_id=product_id, user=user)


@app.get("/api/sales/history")
def history(product_id: int = 1, location_id: int = 7, user=Depends(current_user)):
    with Session() as s:
        return [
            row(x)
            for x in s.scalars(
                select(Sale)
                .where(Sale.product_id == product_id, Sale.location_id == location_id)
                .order_by(Sale.sale_date.desc())
                .limit(90)
            )
        ][::-1]


from .coordination import WorkflowGuard

workflow_lock = WorkflowGuard()


def workflow(body, user):
    if not workflow_lock.acquire(blocking=False):
        raise HTTPException(409, "An agent workflow is already running")
    try:
        with Session() as s:
            prefs = s.get(Setting, f"user:{user.id}")
            if prefs:
                if "horizon" not in body.model_fields_set:
                    body.horizon = prefs.value["horizon"]
                if "model" not in body.model_fields_set:
                    body.model = prefs.value["model"]
        with Session.begin() as s:
            run = Run(run_name=f"Network allocation · {now()[:16]}")
            s.add(run)
            s.flush()
            rid = run.id
            audit(s, user, "start", "optimization_run", rid, None, body.model_dump())
        try:
            with Session.begin() as s:
                run = s.get(Run, rid)
                execute(s, run, body.horizon, body.model, publish=publish)
                return row(run)
        except Exception as exc:
            logger.exception("Agent workflow failed")
            with Session.begin() as s:
                r = s.get(Run, rid)
                r.status = "failed"
                r.details = {"error": str(exc)}
                s.add(
                    AgentExecution(
                        agent_name="Supervisor",
                        execution_id=rid,
                        status="failed",
                        error_message=str(exc),
                        input_summary=body.model_dump(),
                        output_summary={},
                    )
                )
            raise HTTPException(500, f"Workflow #{rid} failed; see execution history")
    finally:
        workflow_lock.release()


@app.post("/api/optimization/run", status_code=201)
def run_optimization(body: ForecastBody, user=Depends(manager)):
    return workflow(body, user)


class AgentBody(ForecastBody):
    agent_id: str | None = None


@app.post("/api/agents/run", status_code=201)
def run_agents(body: AgentBody, user=Depends(manager)):
    if body.agent_id and body.agent_id not in [a[0] for a in AGENTS]:
        raise HTTPException(422, "Unknown agent")
    # Execute prerequisite chain to avoid isolated agents receiving stale recommendations.
    return workflow(body, user)


@app.get("/api/optimization/runs")
def runs(user=Depends(current_user)):
    with Session() as s:
        return [row(x) for x in s.scalars(select(Run).order_by(Run.id.desc()))]


@app.get("/api/optimization/runs/{run_id}")
def run_detail(run_id: int, user=Depends(current_user)):
    with Session() as s:
        return row(s.get(Run, run_id))


@app.get("/api/optimization/runs/{run_id}/recommendations")
def recommendations(run_id: int, user=Depends(current_user)):
    with Session() as s:
        run = s.get(Run, run_id)
        row(run)
        loc = {l.id: l.location_name for l in s.scalars(select(Location))}
        prod = {p.id: p for p in s.scalars(select(Product))}
        projections = {
            (p["product_id"], p["location_id"]): p
            for p in run.details.get("projection", [])
        }
        return [
            {
                **row(a),
                "source": loc[a.source_location_id],
                "destination": loc[a.destination_location_id],
                "sku": prod[a.product_id].sku,
                "product_name": prod[a.product_id].product_name,
                "destination_before": projections.get(
                    (a.product_id, a.destination_location_id), {}
                ).get("before"),
                "destination_after": projections.get(
                    (a.product_id, a.destination_location_id), {}
                ).get("after"),
            }
            for a in s.scalars(
                select(Allocation).where(Allocation.allocation_run_id == run_id)
            )
        ]


@app.post("/api/optimization/runs/{run_id}/approve")
def approve(run_id: int, user=Depends(manager)):
    with Session.begin() as s:
        result = inventory_transaction(s, run_id, user)
    publish({"type": "inventory", "run_id": run_id, "status": "approved"})
    return result


@app.post("/api/optimization/runs/{run_id}/rollback")
def rollback(run_id: int, user=Depends(manager)):
    with Session.begin() as s:
        result = inventory_transaction(s, run_id, user, True)
    publish({"type": "inventory", "run_id": run_id, "status": "rolled_back"})
    return result


@app.post("/api/optimization/runs/{run_id}/reject")
def reject(run_id: int, user=Depends(manager)):
    with Session.begin() as s:
        changed = s.execute(
            update(Run)
            .where(Run.id == run_id, Run.status == "waiting_for_approval")
            .values(status="rejected")
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "Run is not waiting for approval")
        s.execute(
            update(Allocation)
            .where(Allocation.allocation_run_id == run_id)
            .values(allocation_status="rejected")
        )
        audit(
            s, user, "reject", "optimization_run", run_id, None, {"status": "rejected"}
        )
    publish({"type": "optimization", "run_id": run_id, "status": "rejected"})
    return {"status": "rejected"}


@app.get("/api/agents")
@app.get("/api/agents/status")
def agents(user=Depends(current_user)):
    with Session() as s:
        result = []
        for aid, name, role in AGENTS:
            latest = s.scalar(
                select(AgentExecution)
                .where(AgentExecution.agent_name == name)
                .order_by(AgentExecution.id.desc())
            )
            result.append(
                {
                    "id": aid,
                    "name": name,
                    "role": role,
                    "status": live_agents.get(aid, latest.status if latest else "idle"),
                    "tasks_completed": s.scalar(
                        select(func.count(AgentExecution.id)).where(
                            AgentExecution.agent_name == name,
                            AgentExecution.status == "completed",
                        )
                    ),
                    "latest": row(latest) if latest else None,
                }
            )
        return result


@app.get("/api/agents/logs")
def agent_logs(user=Depends(current_user)):
    with Session() as s:
        return [
            row(x)
            for x in s.scalars(
                select(AgentExecution).order_by(AgentExecution.id.desc()).limit(100)
            )
        ]


@app.get("/api/agents/messages")
def agent_messages(user=Depends(current_user)):
    with Session() as s:
        return [
            row(x)
            for x in s.scalars(select(Message).order_by(Message.id.desc()).limit(100))
        ]


@app.get("/api/agents/executions/{execution_id}")
def execution_detail(execution_id: int, user=Depends(current_user)):
    with Session() as s:
        return {
            "run": row(s.get(Run, execution_id)),
            "agents": [
                row(x)
                for x in s.scalars(
                    select(AgentExecution).where(
                        AgentExecution.execution_id == execution_id
                    )
                )
            ],
            "messages": [
                row(x)
                for x in s.scalars(
                    select(Message).where(Message.execution_id == execution_id)
                )
            ],
        }


class TransferBody(BaseModel):
    source_location_id: int
    destination_location_id: int
    product_id: int
    quantity: int = Field(gt=0)


@app.get("/api/transfers")
def transfers(user=Depends(current_user)):
    with Session() as s:
        return [
            row(t) for t in s.scalars(select(Transfer).order_by(Transfer.id.desc()))
        ]


@app.post("/api/transfers", status_code=201)
def request_transfer(body: TransferBody, user=Depends(manager)):
    if body.source_location_id == body.destination_location_id:
        raise HTTPException(422, "Source and destination must differ")
    with Session.begin() as s:
        for lid in [body.source_location_id, body.destination_location_id]:
            row(s.get(Location, lid))
        row(s.get(Product, body.product_id))
        run = Run(
            run_name="Manual transfer request",
            status="waiting_for_approval",
            total_allocated=body.quantity,
        )
        s.add(run)
        s.flush()
        s.add(
            Allocation(
                allocation_run_id=run.id,
                **body.model_dump(exclude={"quantity"}),
                allocated_quantity=body.quantity,
                sales_channel="offline",
                estimated_cost=Decimal(body.quantity) * Decimal(".75"),
                explanation="Manual request; inventory moves only on explicit approval",
            )
        )
        audit(
            s,
            user,
            "request_transfer",
            "optimization_run",
            run.id,
            None,
            body.model_dump(),
        )
        return row(run)


class TransferStatus(BaseModel):
    status: Literal["in_transit", "delivered"]


@app.put("/api/transfers/{id}/status")
def transfer_status(id: int, body: TransferStatus, user=Depends(manager)):
    with Session.begin() as s:
        t = s.scalar(select(Transfer).where(Transfer.id == id).with_for_update())
        old = row(t)
        allowed = {"planned": "in_transit", "in_transit": "delivered"}
        if allowed.get(t.status) != body.status:
            raise HTTPException(409, "Invalid shipment state transition")
        t.status = body.status
        audit(s, user, "shipment_status", "transfer", id, old, row(t))
    publish({"type": "transfer", "id": id, "status": body.status})
    return {"status": body.status}


@app.get("/api/analytics/inventory")
def analytics_inventory(user=Depends(current_user)):
    with Session() as s:
        return {
            "summary": summary(s),
            "channels": channel_performance(user),
            "health": inventory_health(user),
        }


@app.get("/api/analytics/forecast-accuracy")
def accuracy(user=Depends(current_user)):
    with Session() as s:
        fs = s.scalars(select(Forecast)).all()
        return {
            "count": len(fs),
            "mean_wape": sum(f.metrics["wape"] for f in fs) / max(1, len(fs)),
            "mean_mae": sum(f.metrics["mae"] for f in fs) / max(1, len(fs)),
            "method": "Trailing seven-day holdout, aggregate demand error",
        }


@app.get("/api/analytics/allocation-performance")
def allocation_performance(user=Depends(current_user)):
    return runs(user)


@app.get("/api/analytics/cost-savings")
def cost_savings(user=Depends(current_user)):
    with Session() as s:
        approved = s.scalars(select(Run).where(Run.status == "approved")).all()
        return {
            "estimated_avoided_cost": round(
                sum(float(r.details.get("estimated_savings", 0)) for r in approved), 2
            ),
            "transfer_cost": str(sum((r.total_cost for r in approved), Decimal(0))),
            "basis": "Modeled avoided shortage penalty less transport, holding and reallocation costs; not realized revenue",
        }


SCENARIOS = {
    "online_surge": ("online", 2, 1),
    "store_surge": ("offline", 1.8, 1),
    "warehouse_shortage": ("all", 1, 0.35),
    "supplier_delay": ("all", 1, 0.65),
    "seasonal_surge": ("all", 1.6, 1),
    "regional_imbalance": ("regional", 2, 1),
    "promotion_spike": ("all", 2.2, 1),
}


class SimulationBody(ForecastBody):
    scenario: Literal[
        "online_surge",
        "store_surge",
        "warehouse_shortage",
        "supplier_delay",
        "seasonal_surge",
        "regional_imbalance",
        "promotion_spike",
    ] = "online_surge"
    multiplier: float = Field(default=2, ge=1, le=5)


@app.post("/api/simulation/run", status_code=201)
def simulate(body: SimulationBody, user=Depends(manager)):
    with Session.begin() as s:
        rows = forecast_network(s, body.horizon, body.model)
        channel, mult, supply = SCENARIOS[body.scenario]
        for f in rows:
            if (
                channel == "all"
                or f["channel"] == channel
                or (channel == "regional" and f["location_id"] % 5 == 2)
            ):
                f["predicted_demand"] *= (
                    body.multiplier if channel in ["online", "offline"] else mult
                )
        inventory = s.scalars(select(Inventory)).all()
        locations = s.scalars(select(Location)).all()
        result = optimize(
            inventory,
            locations,
            rows,
            s.get(Setting, "optimization").value,
            supply_factor=supply,
        )
        result["initial_inventory"] = sum(i.quantity_on_hand for i in inventory)
        result["simulated_demand"] = round(sum(f["predicted_demand"] for f in rows))
        result["inventory_changed"] = False
        sim = Simulation(
            scenario=body.scenario, parameters=body.model_dump(), results=result
        )
        s.add(sim)
        s.flush()
        audit(s, user, "simulate", "simulation", sim.id, None, body.model_dump())
        return row(sim)


@app.get("/api/simulation/runs")
def simulations(user=Depends(current_user)):
    with Session() as s:
        return [
            row(x) for x in s.scalars(select(Simulation).order_by(Simulation.id.desc()))
        ]


@app.get("/api/simulation/results/{id}")
def simulation_result(id: int, user=Depends(current_user)):
    with Session() as s:
        return row(s.get(Simulation, id))


@app.get("/api/notifications")
def notifications(user=Depends(current_user)):
    with Session() as s:
        return [
            row(x)
            for x in s.scalars(
                select(Notification).order_by(Notification.id.desc()).limit(100)
            )
        ]


@app.put("/api/notifications/{id}/read")
def read_notification(id: int, user=Depends(current_user)):
    with Session.begin() as s:
        n = s.get(Notification, id)
        row(n)
        n.read = True
        return {"read": True}


@app.get("/api/audit")
def audit_logs(user=Depends(current_user)):
    with Session() as s:
        return [
            row(x)
            for x in s.scalars(select(Audit).order_by(Audit.id.desc()).limit(200))
        ]


@app.get("/api/settings")
def settings(user=Depends(current_user)):
    with Session() as s:
        return {
            "optimization": s.get(Setting, "optimization").value,
            "roles": [r.name for r in s.scalars(select(Role))],
            "user": me(user),
            "health": health(),
        }


class Weights(BaseModel):
    stockout_penalty: float = Field(gt=0, le=1000)
    holding_cost: float = Field(ge=0, le=100)
    reallocation_cost: float = Field(ge=0, le=100)
    online_priority: float = Field(gt=0, le=5)


@app.get("/api/users")
def users(user=Depends(administrator)):
    with Session() as s:
        return [
            {"id": u.id, "username": u.username, "role": u.role}
            for u in s.scalars(select(User).order_by(User.id))
        ]


class UserRoleBody(BaseModel):
    role: Literal[
        "Administrator",
        "Inventory Manager",
        "Warehouse Manager",
        "Store Manager",
        "Analyst",
    ]


@app.put("/api/users/{id}/role")
def update_role(id: int, body: UserRoleBody, user=Depends(administrator)):
    with Session.begin() as s:
        # Serialize role changes so at least one administrator always remains.
        all_users = s.scalars(select(User).order_by(User.id).with_for_update()).all()
        target = next((u for u in all_users if u.id == id), None)
        if not target:
            raise HTTPException(404, "User not found")
        if (
            target.role == "Administrator"
            and body.role != "Administrator"
            and sum(u.role == "Administrator" for u in all_users) <= 1
        ):
            raise HTTPException(409, "At least one administrator must remain")
        old = target.role
        target.role = body.role
        audit(s, user, "change_role", "user", id, {"role": old}, {"role": body.role})
        return {"id": target.id, "username": target.username, "role": target.role}


class PreferencesBody(ForecastBody):
    notifications_enabled: bool = True


@app.get("/api/preferences")
def preferences(user=Depends(current_user)):
    with Session() as s:
        setting = s.get(Setting, f"user:{user.id}")
        return setting.value if setting else PreferencesBody().model_dump()


@app.put("/api/preferences")
def save_preferences(body: PreferencesBody, user=Depends(current_user)):
    with Session.begin() as s:
        key = f"user:{user.id}"
        setting = s.get(Setting, key)
        if setting:
            setting.value = body.model_dump()
        else:
            s.add(Setting(key=key, value=body.model_dump()))
        audit(s, user, "preferences", "user", user.id, None, body.model_dump())
        return body.model_dump()


class CompareBody(ForecastBody):
    product_id: int = Field(gt=0)
    location_id: int = Field(gt=0)


@app.post("/api/forecast/compare")
def compare_forecasts(body: CompareBody, user=Depends(current_user)):
    from .forecasting import MODELS, forecast

    with Session() as s:
        row(s.get(Product, body.product_id))
        row(s.get(Location, body.location_id))
        values = list(
            s.scalars(
                select(Sale.quantity_sold)
                .where(
                    Sale.product_id == body.product_id,
                    Sale.location_id == body.location_id,
                )
                .order_by(Sale.sale_date.desc())
                .limit(90)
            )
        )[::-1]
        return [forecast(values, body.horizon, model) for model in MODELS]


@app.put("/api/settings")
def update_settings(body: Weights, user=Depends(manager)):
    with Session.begin() as s:
        setting = s.get(Setting, "optimization")
        old = setting.value
        setting.value = body.model_dump()
        audit(s, user, "configure", "settings", 0, old, setting.value)
        return setting.value


@app.get("/api/reports/inventory.csv")
def export_inventory(user=Depends(current_user)):
    with Session() as s:
        data = inventory_rows(s)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(data[0]) if data else ["sku"])
    writer.writeheader()
    writer.writerows(data)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory.csv"},
    )


@app.get("/api/reports/allocations/{run_id}.csv")
def export_allocations(run_id: int, user=Depends(current_user)):
    data = recommendations(run_id, user)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(data[0]) if data else ["sku"])
    writer.writeheader()
    writer.writerows(data)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=allocation-{run_id}.csv"
        },
    )


@app.get("/api/events")
def get_events(after: int = 0, user=Depends(current_user)):
    return [e for e in events if e["sequence"] > after]


@app.websocket("/ws/events")
async def websocket(ws: WebSocket):
    # Token travels in the first frame, never in a URL or request log.
    await ws.accept()
    try:
        auth = await asyncio.wait_for(ws.receive_json(), timeout=10)
        claims = jwt.decode(auth.get("token", ""), secret, algorithms=["HS256"])
        with Session() as s:
            if not s.get(User, int(claims["sub"])):
                raise ValueError("Unknown user")
        cursor = event_seq
        while True:
            if datetime.now().timestamp() > claims["exp"]:
                await ws.close(code=1008)
                return
            for event in list(events):
                if event["sequence"] > cursor:
                    await ws.send_json(event)
                    cursor = event["sequence"]
            await asyncio.sleep(0.5)
    except (
        WebSocketDisconnect,
        asyncio.TimeoutError,
        jwt.PyJWTError,
        ValueError,
        KeyError,
    ):
        try:
            await ws.close(code=1008)
        except RuntimeError:
            pass

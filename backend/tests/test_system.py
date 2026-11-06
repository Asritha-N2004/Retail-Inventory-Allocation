from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, func
from app.database import *
from app.forecasting import forecast
from app.optimization import optimize


def test_auth_and_roles(client, auth):
    assert client.get("/api/inventory").status_code in [401, 403]
    r = client.post(
        "/api/auth/login", json={"username": "analyst", "password": "RetailDemo!2026"}
    )
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert client.post("/api/optimization/run", headers=h, json={}).status_code == 403
    assert client.get("/api/dashboard/summary", headers=h).status_code == 200
    assert (
        client.post(
            "/api/auth/login", json={"username": "admin", "password": "bad"}
        ).status_code
        == 401
    )


def test_seed_dashboard_and_endpoints(client, auth):
    r = client.get("/api/dashboard/summary", headers=auth).json()
    assert r["total_products"] == 100 and r["total_stores"] == 15
    with Session() as s:
        assert s.scalar(select(func.count(Location.id))) == 22
        assert s.scalar(select(func.count(Sale.id))) == 584000
    for path in [
        "/api/dashboard/inventory-health",
        "/api/dashboard/sales-performance",
        "/api/dashboard/channel-performance",
        "/api/analytics/inventory",
        "/api/analytics/forecast-accuracy",
        "/api/analytics/allocation-performance",
        "/api/analytics/cost-savings",
        "/api/notifications",
        "/api/settings",
        "/api/reports/inventory.csv",
        "/api/locations",
        "/api/agents/messages",
    ]:
        assert client.get(path, headers=auth).status_code == 200, path


def test_product_lifecycle(client, auth):
    p = {
        "sku": "TEST-001",
        "product_name": "Test Product",
        "category": "Electronics",
        "unit_cost": "10.10",
        "selling_price": "15.25",
    }
    r = client.post("/api/products", headers=auth, json=p)
    assert r.status_code == 201, r.text
    id = r.json()["id"]
    p["product_name"] = "Updated"
    assert client.put(f"/api/products/{id}", headers=auth, json=p).status_code == 200
    assert (
        client.get(f"/api/products/{id}", headers=auth).json()["selling_price"]
        == "15.25"
    )
    assert client.delete(f"/api/products/{id}", headers=auth).status_code == 200


@pytest.mark.parametrize(
    "model",
    ["moving_average", "exponential_smoothing", "linear_regression", "random_forest"],
)
def test_forecasts(model):
    f = forecast([3, 4, 5, 4, 3, 5, 4] * 10, 7, model)
    assert (
        f["predicted_demand"] > 0
        and f["lower_bound"] <= f["predicted_demand"] <= f["upper_bound"]
    )
    assert 0 <= f["confidence_score"] <= 1
    assert forecast([], 7, model)["model_name"] == "fallback"


def snapshot():
    with Session() as s:
        return {
            i.id: (i.quantity_on_hand, i.quantity_reserved, i.safety_stock)
            for i in s.scalars(select(Inventory))
        }


def test_complete_workflow_and_compensation(client, auth):
    before = snapshot()
    response = client.post("/api/optimization/run", headers=auth, json={})
    assert response.status_code == 201, response.text
    run = response.json()
    rid = run["id"]
    assert run["status"] == "waiting_for_approval"
    assert snapshot() == before
    assert run["total_allocated"] > 0
    recs = client.get(
        f"/api/optimization/runs/{rid}/recommendations", headers=auth
    ).json()
    assert sum(r["allocated_quantity"] for r in recs) == run["total_allocated"]
    execution = client.get(f"/api/agents/executions/{rid}", headers=auth).json()
    assert len(execution["agents"]) == 10
    assert all(a["status"] == "completed" for a in execution["agents"])
    assert len(execution["messages"]) >= 10
    assert (
        client.post(f"/api/optimization/runs/{rid}/approve", headers=auth).status_code
        == 200
    )
    after = snapshot()
    assert sum(x[0] for x in before.values()) == sum(x[0] for x in after.values())
    assert all(
        q >= reserved + safety
        for id, (q, reserved, safety) in after.items()
        if before[id] != after[id]
    )
    assert (
        client.post(f"/api/optimization/runs/{rid}/approve", headers=auth).status_code
        == 409
    )
    compensated = client.post(f"/api/optimization/runs/{rid}/rollback", headers=auth)
    assert compensated.status_code == 200, compensated.text
    assert snapshot() == before
    assert (
        client.post(f"/api/optimization/runs/{rid}/rollback", headers=auth).status_code
        == 409
    )


def test_simulation_isolation(client, auth):
    before = snapshot()
    for scenario in [
        "online_surge",
        "store_surge",
        "warehouse_shortage",
        "supplier_delay",
        "seasonal_surge",
        "regional_imbalance",
        "promotion_spike",
    ]:
        r = client.post(
            "/api/simulation/run", headers=auth, json={"scenario": scenario}
        )
        assert r.status_code == 201, r.text
        data = r.json()["results"]
        assert data["remaining_shortage"] <= data["baseline_shortage"]
        assert data["inventory_changed"] == False
    assert snapshot() == before


def test_inventory_validation_and_version(client, auth):
    item = client.get("/api/inventory?page_size=1", headers=auth).json()["items"][0]
    body = {
        k: item[k]
        for k in [
            "quantity_on_hand",
            "quantity_reserved",
            "safety_stock",
            "reorder_level",
            "version",
        ]
    }
    assert (
        client.put(f"/api/inventory/{item['id']}", headers=auth, json=body).status_code
        == 200
    )
    assert (
        client.put(f"/api/inventory/{item['id']}", headers=auth, json=body).status_code
        == 409
    )
    body["quantity_on_hand"] = -1
    assert (
        client.put(f"/api/inventory/{item['id']}", headers=auth, json=body).status_code
        == 422
    )


def test_zero_supply_and_fallback():
    locations = [
        Location(
            id=1,
            location_type="Warehouse",
            storage_capacity=100,
            fulfillment_capacity=100,
            latitude=0,
            longitude=0,
        ),
        Location(
            id=2,
            location_type="Physical Store",
            storage_capacity=20,
            fulfillment_capacity=20,
            latitude=1,
            longitude=1,
        ),
    ]
    items = [
        Inventory(
            product_id=1,
            location_id=1,
            quantity_on_hand=0,
            quantity_reserved=0,
            safety_stock=0,
        ),
        Inventory(
            product_id=1,
            location_id=2,
            quantity_on_hand=0,
            quantity_reserved=0,
            safety_stock=2,
        ),
    ]
    w = {
        "stockout_penalty": 25,
        "reallocation_cost": 0.2,
        "holding_cost": 0.15,
        "online_priority": 1.2,
    }
    f = [{"product_id": 1, "location_id": 2, "predicted_demand": 50}]
    assert optimize(items, locations, f, w)["total_allocated"] == 0
    items[0].quantity_on_hand = 100
    result = optimize(items, locations, f, w, solver="greedy")
    assert result["total_allocated"] == 20 and result["method"] == "greedy"


def test_concurrent_approval(client, auth):
    rid = client.post("/api/optimization/run", headers=auth, json={}).json()["id"]
    before = snapshot()
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: client.post(
                    f"/api/optimization/runs/{rid}/approve", headers=auth
                ).status_code,
                range(2),
            )
        )
    assert sorted(responses) == [200, 409]
    assert sum(x[0] for x in snapshot().values()) == sum(x[0] for x in before.values())
    assert (
        client.post(f"/api/optimization/runs/{rid}/rollback", headers=auth).status_code
        == 200
    )


def test_reject(client, auth):
    rid = client.post("/api/optimization/run", headers=auth, json={}).json()["id"]
    before = snapshot()
    assert (
        client.post(f"/api/optimization/runs/{rid}/reject", headers=auth).status_code
        == 200
    )
    assert (
        client.post(f"/api/optimization/runs/{rid}/approve", headers=auth).status_code
        == 409
    )
    assert snapshot() == before


def test_websocket_auth(client, auth):
    with client.websocket_connect("/ws/events") as ws:
        ws.send_json({"token": "invalid"})
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_shared_capacity_across_products():
    locations = [
        Location(
            id=1,
            location_type="Warehouse",
            storage_capacity=1000,
            fulfillment_capacity=1000,
            latitude=0,
            longitude=0,
        ),
        Location(
            id=2,
            location_type="Physical Store",
            storage_capacity=15,
            fulfillment_capacity=12,
            latitude=1,
            longitude=1,
        ),
    ]
    items = [
        Inventory(
            product_id=p,
            location_id=l,
            quantity_on_hand=100 if l == 1 else 0,
            quantity_reserved=10 if l == 1 else 0,
            safety_stock=5,
        )
        for p in [1, 2]
        for l in [1, 2]
    ]
    fs = [{"product_id": p, "location_id": 2, "predicted_demand": 40} for p in [1, 2]]
    weights = {
        "stockout_penalty": 25,
        "reallocation_cost": 0.2,
        "holding_cost": 0.15,
        "online_priority": 1.2,
    }
    for method in ["milp", "greedy"]:
        result = optimize(items, locations, fs, weights, solver=method)
        assert result["total_allocated"] == 12
        assert result["remaining_shortage"] == 78
        assert result["objective_value"] >= 0


def test_stale_proposal_is_atomic(client, auth):
    rid = client.post("/api/optimization/run", headers=auth, json={}).json()["id"]
    recs = client.get(
        f"/api/optimization/runs/{rid}/recommendations", headers=auth
    ).json()
    a = recs[0]
    with Session.begin() as s:
        source = s.scalar(
            select(Inventory).where(
                Inventory.product_id == a["product_id"],
                Inventory.location_id == a["source_location_id"],
            )
        )
        old = source.quantity_on_hand
        source.quantity_on_hand = source.quantity_reserved + source.safety_stock
        source.version += 1
        iid = source.id
    before = snapshot()
    assert (
        client.post(f"/api/optimization/runs/{rid}/approve", headers=auth).status_code
        == 409
    )
    assert snapshot() == before
    assert (
        client.get(f"/api/optimization/runs/{rid}", headers=auth).json()["status"]
        == "waiting_for_approval"
    )
    with Session.begin() as s:
        s.get(Inventory, iid).quantity_on_hand = old
    assert (
        client.post(f"/api/optimization/runs/{rid}/reject", headers=auth).status_code
        == 200
    )


def test_failure_is_auditable(client, auth, monkeypatch):
    import app.agents as agents

    def fail(*args, **kwargs):
        raise RuntimeError("Injected forecasting failure")

    monkeypatch.setattr(agents, "forecast_network", fail)
    before = snapshot()
    assert (
        client.post("/api/optimization/run", headers=auth, json={}).status_code == 500
    )
    r = client.get("/api/optimization/runs", headers=auth).json()[0]
    assert (
        r["status"] == "failed"
        and "Injected forecasting failure" in r["details"]["error"]
    )
    assert snapshot() == before


def test_preferences_roles_and_comparison(client, auth):
    body = {"horizon": 14, "model": "moving_average", "notifications_enabled": False}
    assert client.put("/api/preferences", headers=auth, json=body).status_code == 200
    assert client.get("/api/preferences", headers=auth).json() == body
    users = client.get("/api/users", headers=auth).json()
    analyst = next(u for u in users if u["username"] == "analyst")
    assert (
        client.put(
            f"/api/users/{analyst['id']}/role",
            headers=auth,
            json={"role": "Store Manager"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/users/{analyst['id']}/role", headers=auth, json={"role": "Analyst"}
        ).status_code
        == 200
    )
    admin = next(u for u in users if u["username"] == "admin")
    assert (
        client.put(
            f"/api/users/{admin['id']}/role", headers=auth, json={"role": "Analyst"}
        ).status_code
        == 409
    )
    comparison = client.post(
        "/api/forecast/compare", headers=auth, json={"product_id": 1, "location_id": 7}
    ).json()
    assert len(comparison) == 4
    assert all(f["predicted_demand"] >= 0 for f in comparison)

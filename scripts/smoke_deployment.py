"""Read-only authenticated API smoke test. Never logs tokens or credentials."""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

BASE = (
    sys.argv[1] if len(sys.argv) > 1 else "https://nexus-retail-allocation.vercel.app"
).rstrip("/")


def main():
    login = Request(
        BASE + "/api/auth/login",
        data=json.dumps(
            {
                "username": "admin",
                "password": os.getenv("SMOKE_PASSWORD", "RetailDemo!2026"),
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(login, timeout=90) as response:
        token = json.load(response)["access_token"]
    paths = [
        "/api/auth/me",
        "/api/preferences",
        "/api/settings",
        "/api/notifications",
        "/api/dashboard/summary",
        "/api/dashboard/inventory-health",
        "/api/dashboard/sales-performance",
        "/api/dashboard/channel-performance",
        "/api/locations",
        "/api/agents",
        "/api/inventory?page_size=5",
        "/api/products?page_size=5",
        "/api/analytics/inventory",
        "/api/analytics/forecast-accuracy",
        "/api/analytics/allocation-performance",
        "/api/analytics/cost-savings",
        "/api/forecast?product_id=1",
        "/api/optimization/runs",
        "/api/simulation/runs",
    ]

    def read(path):
        request = Request(BASE + path, headers={"Authorization": "Bearer " + token})
        with urlopen(request, timeout=90) as response:
            return path, response.status, json.load(response)

    results = list(ThreadPoolExecutor(max_workers=4).map(read, paths))
    data = {path: body for path, status, body in results}
    for path, status, body in results:
        print(f"{status} {path}")
    summary = data["/api/dashboard/summary"]
    sales = data["/api/dashboard/sales-performance"]
    assert sales and {item["channel"] for item in sales} == {"online", "offline"}
    assert sum(item["units"] for item in sales) == summary["sales_units"]
    print(
        f"Verified {len(results)} endpoints, {len(sales)} monthly/channel totals, and sales conservation."
    )


if __name__ == "__main__":
    main()

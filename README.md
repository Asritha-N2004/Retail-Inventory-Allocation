# Nexus — autonomous retail inventory allocation

A local-first, end-to-end demonstration of coordinated online and physical retail inventory allocation. React/TypeScript and FastAPI connect to a normalized SQLAlchemy database. Ten deterministic agents produce structured, auditable recommendations using historical demand and a constrained integer transportation model. No paid AI service is needed.

## Local setup

Requires Python 3.12+ and Node 22.12+ with npm. Run commands from this folder unless noted.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
python -m app.migrate
python seed.py
uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. API documentation: http://localhost:8000/docs. Health: http://localhost:8000/health.

Seeded accounts: `admin`, `manager`, `analyst`. Initial password: `RetailDemo!2026` (override `DEMO_PASSWORD` before first seed). Analyst has read-only access. Administrator and Inventory Manager can propose and approve changes. Tokens are signed JWTs, expire after eight hours, and are stored only for the browser session. Passwords use Argon2. Set a stable `JWT_SECRET` of at least 32 random characters for a persistent deployment; otherwise tokens expire on server restart.

On this workspace's host, npm was absent. A workspace-local npm was bootstrapped under `.tools/package`; use `node ../.tools/package/bin/npm-cli.js <command>` from frontend if npm is still absent. If venv ensurepip fails, system pip can install into it with `python -m pip --python .venv/Scripts/python.exe install -r backend/requirements.txt`.

## Working flow

1. Sign in and inspect live database inventory and sales charts.
2. Open Allocation and select **Run Intelligent Allocation**. Forecasting, monitoring, channel, warehouse, risk, allocation, logistics and pricing agents execute with supervisor coordination.
3. Inspect recommended source/destination movements and costs. Inventory is unchanged at this stage.
4. Select **Review approval**, then **Approve and update inventory**. The API atomically validates and applies the changes, records before/after values and creates planned transfers.
5. Track planned → in transit → delivered shipments. The inventory table is an allocation ledger: quantities are assigned to destinations on approval, not on physical delivery. Shipment status never moves stock a second time.
6. Use **Compensate allocation** to reverse an approved allocation if stock is still available and no shipment has been delivered. If stock/capacity has changed, compensation fails without partial writes.
7. Use Simulation to compare no-reallocation shortages with optimized shortages under seven disruption scenarios. Simulation does not mutate operational inventory or forecasts.

## Architecture and data

See [architecture](docs/architecture.md), [agent workflow](docs/agent_workflow.md), [schema](docs/database_schema.md), and [optimization methodology](docs/optimization_methodology.md).

Seed 42 creates 100 products, 5 warehouses, 1 distribution center, 15 stores and 1 online fulfillment center. There are 584,000 daily product/location sales observations covering 2025-11-06 through 2026-11-05. This is a fixed reproducible demonstration dataset, not live sales. Refreshing pages does not randomize metrics. Seed is idempotent and does not overwrite an existing database.

API groups cover dashboard, products, inventory, forecasts, agents and messages, optimization runs and approval/rejection/rollback, transfers, analytics, simulations, notifications, audit, settings and CSV reports. FastAPI provides request schemas and interactive OpenAPI documentation. Inventory and products support pagination, filtering and allowlisted sort keys. Financial database fields are fixed-precision decimal values, serialized as strings. Inventory quantities are integers.

WebSocket `/ws/events` authenticates using the first message, avoiding token-bearing URLs. Process-local live events trigger fresh API reads; the UI also polls at 30 seconds. Database execution history remains durable. SQLite development uses a process-local workflow lock; PostgreSQL deployments also acquire a transaction advisory lock across instances. The transient event bus remains in memory, so cross-instance updates rely on polling persisted API state. Redis is intentionally omitted.

## Configuration

`DATABASE_URL` defaults to `sqlite:///./retail.db` relative to backend's working directory. PostgreSQL: `postgresql+psycopg://user:password@host:5432/retail`. `AUTO_SEED=false` disables startup seeding. `CORS_ORIGINS` accepts comma-separated exact origins. Environment files are examples; the backend reads process environment variables, not `.env` automatically. Docker Compose reads root `.env`.

Optimization weights are configurable through Settings: shortage penalty, per-unit holding cost, movement cost and online priority. Settings also persists each user's preferred forecast model/horizon and notification highlighting, and lets administrators change existing user roles with an audit record and a last-administrator safeguard. Forecasting supports a side-by-side four-model comparison. Safety stock/reorder levels are edited per stock position through Inventory. No real prices are changed. Suggestions from the pricing agent are advisory.

## Tests and build

```powershell
cd backend
../.venv/Scripts/python -m pytest -q
cd ../frontend
npm test
npm run build
```

Backend integration tests use a temporary isolated SQLite database and exercise seeding, authentication, RBAC, CRUD, forecasting, orchestration, approval, duplicate/concurrent approval, conservation, rollback, simulations and analytics. The initial seed can take time and uses substantial memory. Frontend tests cover operational components and interactive selection. See IMPLEMENTATION_STATUS.md for verification results and remaining limitations.

## Docker

For Vercel hosting, see [Vercel deployment](docs/vercel-deployment.md). The root deployment configuration hosts the frontend and FastAPI together using persistent Neon PostgreSQL, with release-time initialization.

Copy `.env.example` to `.env`, replace the password and JWT secret, then:

```sh
docker compose up --build
```

Frontend: http://localhost:8080. API: http://localhost:8000/docs. PostgreSQL is private to the Docker network and persists in a named volume. The backend starts as a non-root user; startup applies the initial schema and seeds once. Frontend nginx proxies REST and WebSocket requests. Docker is not installed on the development host used to generate this project; the Compose environment requires verification on a Docker-enabled host.

## Operational limits and troubleshooting

- This is a demonstration platform, not an ERP integration. Sales, transport routes and fulfillment capacities are simulated inputs; analytics label modeled savings explicitly.
- No user provisioning/password reset UI, granular store/warehouse scopes, distributed jobs, durable event replay, production alerting, or external logistics/supplier integration is included. Role permissions are enforced in the API; finer operational scopes require extensions.
- The schema includes suppliers, purchase orders and promotions as extension points. Supplier delays in simulation reduce available supply. Planned inventory allocations are distinct from physical stock-in-transit accounting.
- Forecast bounds use a normal approximation and are not calibrated prediction intervals. Accuracy is a trailing holdout estimate, not a guarantee. Turnover uses annual sales/current stock as a proxy for average inventory.
- Partial source shortages may leave destination safety stock unmet; the optimizer reports remaining shortage rather than inventing inventory.
- A stale inventory/approval response returns HTTP 409. Refresh data and generate a new proposal. No partial changes should remain.
- First launch generates substantial history. Wait for the startup completion log before signing in. A port conflict requires stopping the old server or changing port plus proxy configuration.
- The initial migration is versioned and idempotent; it does not alter existing columns. Add explicit new migrations for future schema changes. Back up the database before upgrades.
- For a deployment: configure TLS, stable secrets, non-demo accounts, backups, shared event/job coordination and appropriate rate limits. The included login throttle is process-local.

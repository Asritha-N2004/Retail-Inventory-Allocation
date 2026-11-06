# Implementation checklist
- [x] Normalized database, versioned initial migration and reproducible seed
- [x] JWT/Argon2 authentication, role checks and audited role management
- [x] Four forecasting methods, holdout metrics and model comparison
- [x] Ten-agent dependency workflow, structured messages and execution history
- [x] Integer SciPy/HiGHS transportation optimization and greedy fallback
- [x] Atomic approval/rejection, version checks, compensation and inventory audit
- [x] Seven isolated simulation scenarios, database-derived analytics and exports
- [x] Authenticated WebSocket events and 30-second polling fallback
- [x] Ten connected responsive pages, account preferences and error feedback
- [x] Backend regression tests: 20 passed
- [x] Frontend component/workflow tests: 11 passed
- [x] Browser: sign-in, dashboard, allocation proposal/approval/compensation, inventory filtering
- [x] Browser: desktop and 390px mobile layout inspected
- [x] Browser: role-management controls, preferences and four-model forecast comparison
- [x] Production frontend build passed with split vendor/chart bundles
- [x] Frontend dependency audit: zero known vulnerabilities at installation verification
- [x] Explicit migration and idempotent seed commands verified
- [x] Docker/Compose/PostgreSQL configuration and technical documentation
- [ ] Docker/PostgreSQL runtime verification — Docker is not installed on this host
- [x] Vercel deployment configuration, dedicated Neon database, stable JWT secret, and PostgreSQL workflow coordination
- [x] Vercel live smoke verification — login, dashboard, optimization, PostgreSQL approval and compensation passed

## Verified local data

100 products; 5 warehouses; 1 distribution center; 15 stores; 1 online fulfillment center; 2,200 stock positions; 584,000 daily sales observations. Reproducible seed: 42. Initial network inventory: 214,008 units. Browser-tested proposal: 9,666 units; approval and compensation both completed. Inventory returned to 214,008 units after compensation.

## Scope and limits

This is a functional hosted demonstration, not a production ERP integration. All requested API groups have working implementations. The initial migration creates and versions the schema; future alterations need additional migrations. PostgreSQL advisory transaction locks serialize workflows across hosted instances; local SQLite uses a process lock. Live events remain process-local, with polling of persisted API state across instances. Redis and distributed jobs are not implemented. Existing-account role management is included; user provisioning, password recovery and per-store permission scoping are not. Supplier/order/promotion models are included; external integrations and their administration UI are extension points. Inventory represents assigned ledger stock, with physical shipment states tracked separately. Cost savings and forecast intervals are model estimates, labeled as such.

Docker acceptance remains unverified. PostgreSQL approval and compensation were verified on Vercel/Neon. Frontend TypeScript uses reusable record types for dynamic API tables; a generated OpenAPI client would improve stricter end-to-end schema typing. There is no paid LLM dependency.

## Hosted deployment

Production: https://nexus-retail-allocation.vercel.app

Hotfix: PostgreSQL sales aggregation now computes month once in a subquery before grouping. Added PostgreSQL dialect compilation and sales-conservation regression checks. The error banner now reflects active failed queries, identifies the endpoint, and clears after recovery rather than retaining stale errors.

Hotfix deployment `dpl_7x89J8xKhxotsrTYnsLFoS6NwiBg` reached READY. Authenticated production smoke checks returned HTTP 200 for 19 endpoints; all 26 monthly/channel aggregates matched the database sales total. Browser verification showed both demand series rendered and zero error banners. Verification: 20 backend tests, 11 frontend tests, production build passed.

Vercel project: `resum-projects/nexus-retail-allocation`. Dedicated Neon Free database: `nexus-retail-allocation-db`. Deployment `dpl_HfZCiBhCtGkkU92i6EYKzcJ1HpEU` reached READY. Cloud migration and all 584,000 sales rows seeded successfully during release. `/health` returned HTTP 200 directly. Hosted run #1 proposed 9,666 units, was approved, then compensated; dashboard totals returned to 214,008 units. Backend regression suite: 18 passed after deployment changes.

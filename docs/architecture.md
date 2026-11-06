# Architecture

React pages → authenticated REST/WebSocket → FastAPI → SQLAlchemy transaction boundary → SQLite locally / PostgreSQL in Compose.

`backend/app/database.py` defines normalized entities. `forecasting.py` provides pure prediction methods. `optimization.py` solves a sparse integer transportation program and exposes a deterministic greedy fallback. `agents.py` coordinates shared state and persisted messages. `transactions.py` owns inventory mutations, approval and compensation. `main.py` provides validated HTTP contracts, permissions, read models and event delivery. `frontend/src/pages` contains API-connected views, `services` the authenticated HTTP client, `hooks` query caching and `components` shared presentation.

Proposals persist independently of inventory. Approval claims the expected run state, locks locations in stable order, validates aggregated stock/capacity and uses row versions on every write. PostgreSQL uses row locks; SQLite serializes writes and conditional updates reject duplicate approvals. Simulation uses detached input calculations and persists only its result.

Workflows are synchronous request-scoped operations with a process lock. This avoids fake progress and dependency races in the single-worker demo but is not a distributed scheduler. Live events are bounded and transient; audit/execution/message records are durable. Unfinished runs are marked failed at startup.

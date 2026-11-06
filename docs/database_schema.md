# Database

Products (unique SKU) and Locations (unique name) define the network. Inventory has a unique product/location pair, nonnegative reservations and stock checks, and a version counter. Available quantity is derived as on-hand minus reserved to avoid a second inconsistent stored balance.

Sales History and Demand Forecasts reference product/location. Optimization Runs own Allocations, Agent Executions and Agent Messages. Transfers reference unique allocation IDs. Audits reference the acting user and capture before/after JSON. Users reference named Roles. Notifications, Settings and Simulation Runs persist operational UI state. Suppliers own Purchase Orders; Promotions reference Products.

Foreign-key/index definitions live in `app/database.py`. Money uses Numeric(12,2) or Numeric(14,2). Initial migration uses metadata and records schema_versions version 1. No destructive reset occurs on startup. SQLite uses one process for this demonstration; PostgreSQL is the configured deployment database.

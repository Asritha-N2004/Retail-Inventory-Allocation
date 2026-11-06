# Schema migrations

Run `python -m app.migrate` from backend before starting the service. The initial migration creates the normalized SQLAlchemy schema and records version 1 in `schema_versions`. Startup also applies this idempotent initial migration. It does not reset existing data. This repository contains the initial schema only; future schema changes must add ordered version migrations rather than relying on create_all to alter tables.

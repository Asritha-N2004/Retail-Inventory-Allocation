"""Release-time database initialization using Vercel-provided environment only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.database import migrate, engine
from backend.app.seed import seed
from backend.app.coordination import WorkflowGuard


def main():
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Cloud release requires PostgreSQL")
    guard = WorkflowGuard()
    if not guard.acquire():
        raise RuntimeError("Another workflow or release is running; retry deployment")
    try:
        migrate()
        seed()
        print("Cloud database schema and reproducible retail dataset are ready.")
    finally:
        guard.release()


if __name__ == "__main__":
    main()

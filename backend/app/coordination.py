"""Serialize optimization across local threads and PostgreSQL-backed instances."""

import threading
from sqlalchemy import text
from .database import engine


class WorkflowGuard:
    def __init__(self):
        self.local_lock = threading.Lock()
        self.state = threading.local()

    def acquire(self, blocking=False):
        if not self.local_lock.acquire(blocking=blocking):
            return False
        self.state.connection = None
        try:
            if engine.dialect.name == "postgresql":
                connection = engine.connect()
                self.state.connection = connection
                # Keep this transaction open so Neon transaction pooling pins the
                # advisory lock to one backend until the workflow has finished.
                if not connection.scalar(
                    text("SELECT pg_try_advisory_xact_lock(731942085)")
                ):
                    self.release()
                    return False
            return True
        except Exception:
            self.release()
            raise

    def release(self):
        try:
            connection = getattr(self.state, "connection", None)
            if connection is not None:
                connection.rollback()
                connection.close()
                self.state.connection = None
        finally:
            self.local_lock.release()

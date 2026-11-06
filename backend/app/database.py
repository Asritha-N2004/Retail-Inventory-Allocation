import os
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Boolean,
    ForeignKey,
    Numeric,
    JSON,
    UniqueConstraint,
    CheckConstraint,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker


def now():
    return datetime.now(timezone.utc).isoformat()


URL = os.getenv("DATABASE_URL", "sqlite:///./retail.db")
if URL.startswith(("postgres://", "postgresql://")):
    URL = "postgresql+psycopg://" + URL.split("://", 1)[1]
if os.getenv("VERCEL") and URL.startswith("sqlite"):
    raise RuntimeError("Vercel requires a persistent DATABASE_URL; SQLite is local-only")
engine = create_engine(
    URL,
    connect_args=(
        {"check_same_thread": False, "timeout": 30} if URL.startswith("sqlite") else {}
    ),
    pool_pre_ping=True,
)
if URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")


Session = sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    sku = Column(String, unique=True, nullable=False)
    product_name = Column(String, nullable=False)
    category = Column(String, index=True)
    description = Column(String, default="")
    unit_cost = Column(Numeric(12, 2), default=0)
    selling_price = Column(Numeric(12, 2), default=0)
    weight = Column(Float, default=1)
    dimensions = Column(String, default="20x20x20 cm")
    active = Column(Boolean, default=True)
    created_at = Column(String, default=now)
    updated_at = Column(String, default=now)


class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True)
    location_name = Column(String, unique=True)
    location_type = Column(String)
    address = Column(String, default="")
    region = Column(String)
    latitude = Column(Float, default=0)
    longitude = Column(Float, default=0)
    storage_capacity = Column(Integer)
    fulfillment_capacity = Column(Integer, default=50000)
    active = Column(Boolean, default=True)


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("product_id", "location_id"),
        CheckConstraint(
            "quantity_on_hand >= quantity_reserved AND quantity_reserved >= 0 AND safety_stock >= 0"
        ),
    )
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), index=True)
    quantity_on_hand = Column(Integer, default=0)
    quantity_reserved = Column(Integer, default=0)
    safety_stock = Column(Integer, default=5)
    reorder_level = Column(Integer, default=15)
    version = Column(Integer, default=0)
    last_updated = Column(String, default=now)


class Sale(Base):
    __tablename__ = "sales_history"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), index=True)
    sales_channel = Column(String)
    quantity_sold = Column(Integer)
    selling_price = Column(Numeric(12, 2))
    promotion_flag = Column(Boolean, default=False)
    sale_date = Column(String, index=True)


class Forecast(Base):
    __tablename__ = "demand_forecasts"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    location_id = Column(Integer, ForeignKey("locations.id"))
    channel = Column(String)
    forecast_date = Column(String, default=now)
    predicted_demand = Column(Float)
    lower_bound = Column(Float)
    upper_bound = Column(Float)
    model_name = Column(String)
    confidence_score = Column(Float)
    metrics = Column(JSON)


class Run(Base):
    __tablename__ = "optimization_runs"
    id = Column(Integer, primary_key=True)
    run_name = Column(String)
    status = Column(String, default="running", index=True)
    objective_value = Column(Numeric(14, 2), default=0)
    total_allocated = Column(Integer, default=0)
    total_cost = Column(Numeric(14, 2), default=0)
    stockout_risk = Column(Float, default=0)
    details = Column(JSON, default=dict)
    created_at = Column(String, default=now)
    completed_at = Column(String)


class Allocation(Base):
    __tablename__ = "inventory_allocations"
    id = Column(Integer, primary_key=True)
    allocation_run_id = Column(Integer, ForeignKey("optimization_runs.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    source_location_id = Column(Integer, ForeignKey("locations.id"))
    destination_location_id = Column(Integer, ForeignKey("locations.id"))
    sales_channel = Column(String)
    allocated_quantity = Column(Integer)
    allocation_status = Column(String, default="proposed")
    estimated_cost = Column(Numeric(12, 2))
    explanation = Column(String)
    created_at = Column(String, default=now)


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    id = Column(Integer, primary_key=True)
    agent_name = Column(String)
    execution_id = Column(Integer, ForeignKey("optimization_runs.id"), index=True)
    status = Column(String)
    input_summary = Column(JSON)
    output_summary = Column(JSON)
    error_message = Column(String)
    execution_duration = Column(Float)
    confidence = Column(Float)
    created_at = Column(String, default=now)


class Message(Base):
    __tablename__ = "agent_messages"
    id = Column(Integer, primary_key=True)
    execution_id = Column(Integer, ForeignKey("optimization_runs.id"))
    sender = Column(String)
    receiver = Column(String)
    payload = Column(JSON)
    created_at = Column(String, default=now)


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password_hash = Column(String)
    role = Column(String, ForeignKey("roles.name"))


class Audit(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String)
    entity_type = Column(String)
    entity_id = Column(Integer)
    previous_value = Column(JSON)
    new_value = Column(JSON)
    timestamp = Column(String, default=now)


class Transfer(Base):
    __tablename__ = "transfers"
    id = Column(Integer, primary_key=True)
    allocation_id = Column(Integer, ForeignKey("inventory_allocations.id"), unique=True)
    source_location_id = Column(Integer, ForeignKey("locations.id"))
    destination_location_id = Column(Integer, ForeignKey("locations.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    status = Column(String, default="planned")
    estimated_cost = Column(Numeric(12, 2))
    estimated_hours = Column(Float)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    message = Column(String)
    read = Column(Boolean, default=False)
    created_at = Column(String, default=now)


class Simulation(Base):
    __tablename__ = "simulation_runs"
    id = Column(Integer, primary_key=True)
    scenario = Column(String)
    parameters = Column(JSON)
    results = Column(JSON)
    created_at = Column(String, default=now)


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    lead_days = Column(Integer)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    quantity = Column(Integer)
    status = Column(String)


class Promotion(Base):
    __tablename__ = "promotions"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    demand_multiplier = Column(Float)
    starts_at = Column(String)
    ends_at = Column(String)


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(JSON)


class SchemaVersion(Base):
    __tablename__ = "schema_versions"
    version = Column(Integer, primary_key=True)
    applied_at = Column(String, default=now)


def migrate():
    Base.metadata.create_all(engine)
    with Session.begin() as s:
        if not s.get(SchemaVersion, 1):
            s.add(SchemaVersion(version=1))

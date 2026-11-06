from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from app.analytics import monthly_sales_query
from app.database import Sale, Session


def test_postgres_aggregation_uses_one_month_expression():
    compiled = monthly_sales_query().compile(dialect=PGDialect_psycopg())
    sql = str(compiled)
    assert sql.count("substr(") == 1
    assert "GROUP BY monthly_sales.month, monthly_sales.channel" in sql
    assert len(compiled.params) == 2


def test_monthly_sales_preserves_units_and_revenue(client, auth):
    response = client.get("/api/dashboard/sales-performance", headers=auth)
    assert response.status_code == 200
    rows = response.json()
    assert rows and {r["channel"] for r in rows} == {"online", "offline"}
    assert len({(r["month"], r["channel"]) for r in rows}) == len(rows)
    with Session() as session:
        units, revenue = session.execute(
            select(
                func.sum(Sale.quantity_sold),
                func.sum(Sale.quantity_sold * Sale.selling_price),
            )
        ).one()
    assert sum(r["units"] for r in rows) == units
    assert sum(Decimal(r["revenue"]) for r in rows) == revenue

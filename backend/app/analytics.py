"""Portable aggregate queries shared by SQLite and PostgreSQL deployments."""

from sqlalchemy import select, func
from .database import Sale


def monthly_sales_query():
    # Compute the month once. Independent substr() calls generate different bind
    # parameters, which PostgreSQL correctly treats as different GROUP BY terms.
    daily = select(
        func.substr(Sale.sale_date, 1, 7).label("month"),
        Sale.sales_channel.label("channel"),
        Sale.quantity_sold.label("units"),
        (Sale.quantity_sold * Sale.selling_price).label("revenue"),
    ).subquery("monthly_sales")
    return (
        select(
            daily.c.month,
            daily.c.channel,
            func.sum(daily.c.units),
            func.sum(daily.c.revenue),
        )
        .group_by(daily.c.month, daily.c.channel)
        .order_by(daily.c.month, daily.c.channel)
    )

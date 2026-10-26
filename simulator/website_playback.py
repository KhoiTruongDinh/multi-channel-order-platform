"""Load one allow-listed S01 website state into the source database atomically."""

from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb


STATES = {"0900", "0901", "0910", "0914"}
TABLES = (
    "customers",
    "products",
    "product_variants",
    "orders",
    "order_items",
    "payment_transactions",
    "shipments",
    "shipment_items",
    "cancellation_requests",
)
DELETE_ORDER = tuple(reversed(TABLES))


def connection_kwargs() -> dict[str, object]:
    return {
        "host": os.environ.get("WEBSITE_DB_HOST", "postgres"),
        "port": int(os.environ.get("WEBSITE_DB_PORT", "5432")),
        "dbname": "website_source",
        "user": "website_writer",
        "password": os.environ["WEBSITE_WRITER_PASSWORD"],
    }


def validate(data: dict[str, list[dict[str, object]]]) -> None:
    if set(data) != set(TABLES):
        raise ValueError(f"state tables differ from contract: {sorted(data)}")
    items_by_order: dict[str, list[dict[str, object]]] = {}
    for item in data["order_items"]:
        items_by_order.setdefault(str(item["order_id"]), []).append(item)
    for order in data["orders"]:
        items = items_by_order.get(str(order["order_id"]), [])
        gross = sum(Decimal(str(i["unit_price"])) * int(i["quantity"]) for i in items)
        discount = sum(Decimal(str(i["line_discount_amount"])) for i in items)
        tax = sum(Decimal(str(i["line_tax_amount"])) for i in items)
        if gross != Decimal(str(order["items_gross_amount"])):
            raise ValueError(f"W03 failed for {order['order_id']}")
        if discount != Decimal(str(order["discount_amount"])):
            raise ValueError(f"W04 failed for {order['order_id']}")
        if tax != Decimal(str(order["tax_amount"])):
            raise ValueError(f"W05 failed for {order['order_id']}")

    order_currency = {str(row["order_id"]): row["currency"] for row in data["orders"]}
    for payment in data["payment_transactions"]:
        if payment["currency"] != order_currency[str(payment["order_id"])]:
            raise ValueError(f"payment currency mismatch: {payment['payment_transaction_id']}")

    item_order = {str(row["order_item_id"]): str(row["order_id"]) for row in data["order_items"]}
    item_quantity = {str(row["order_item_id"]): int(row["quantity"]) for row in data["order_items"]}
    shipment_order = {str(row["shipment_id"]): str(row["order_id"]) for row in data["shipments"]}
    allocated: dict[str, int] = {}
    for row in data["shipment_items"]:
        item_id = str(row["order_item_id"])
        if shipment_order[str(row["shipment_id"])] != item_order[item_id]:
            raise ValueError(f"W15 same-order allocation failed for {item_id}")
        allocated[item_id] = allocated.get(item_id, 0) + int(row["quantity"])
        if allocated[item_id] > item_quantity[item_id]:
            raise ValueError(f"W15 quantity allocation failed for {item_id}")


def insert_rows(cur: psycopg.Cursor[object], table: str, rows: list[dict[str, object]]) -> None:
    for row in rows:
        values = [Jsonb(value) if isinstance(value, (dict, list)) else value for value in row.values()]
        columns = ", ".join(row)
        placeholders = ", ".join(["%s"] * len(row))
        cur.execute(f"INSERT INTO public.{table} ({columns}) VALUES ({placeholders})", values)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", choices=sorted(STATES))
    args = parser.parse_args()

    state_path = Path("/fixtures/website") / f"{args.state}.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))
    validate(data)

    with psycopg.connect(**connection_kwargs()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('s01-website-playback'))")
            for table in DELETE_ORDER:
                cur.execute(f"DELETE FROM public.{table}")
            for table in TABLES:
                insert_rows(cur, table, data[table])
    print(f"website source state {args.state} applied")


if __name__ == "__main__":
    main()

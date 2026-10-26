"""Acquire a consistent website order window into immutable raw audit storage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


SOURCE_SYSTEM = "internal_web"
SOURCE_ACCOUNT = "WEB01"
STREAM = "orders"
CONTRACT_VERSION = "website-v0.1"
TABLE_COLUMNS = {
    "orders": "order_id, order_number, customer_id, created_at, updated_at, currency, payment_status, fulfillment_status, cancellation_status, items_gross_amount, discount_amount, shipping_amount, tax_amount, order_total_amount",
    "order_items": "order_item_id, order_id, variant_id, sku_at_purchase, title_at_purchase, quantity, unit_price, line_discount_amount, line_tax_amount, created_at, updated_at",
    "payment_transactions": "payment_transaction_id, order_id, transaction_type, status, amount, currency, provider_reference, occurred_at, updated_at",
    "cancellation_requests": "cancellation_id, order_id, reason_code, status, requested_at, resolved_at, updated_at",
    "shipments": "shipment_id, order_id, carrier, tracking_number, status, shipped_at, delivered_at, updated_at",
    "shipment_items": "shipment_id, order_item_id, quantity",
    "customers": "customer_id, display_name, email, created_at, updated_at",
    "products": "product_id, product_name, category, is_active, created_at, updated_at",
    "product_variants": "variant_id, product_id, sku, attributes, current_price, currency, is_active, updated_at",
}


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def db_kwargs(prefix: str, database: str, user: str) -> dict[str, object]:
    return {
        "host": os.environ.get(f"{prefix}_DB_HOST", "postgres"),
        "port": int(os.environ.get(f"{prefix}_DB_PORT", "5432")),
        "dbname": database,
        "user": user,
        "password": os.environ[f"{user.upper()}_PASSWORD"],
    }


def json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return value


def rows(cur: psycopg.Cursor[dict[str, Any]], query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    cur.execute(query, params)
    return [{key: json_value(value) for key, value in row.items()} for row in cur.fetchall()]


def acquire_source(window_start: datetime, window_end: datetime) -> dict[str, list[dict[str, Any]]]:
    payload = {name: [] for name in TABLE_COLUMNS}
    with psycopg.connect(**db_kwargs("WEBSITE", "website_source", "website_reader"), row_factory=dict_row) as conn:
        conn.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        with conn.cursor() as cur:
            order_rows = rows(
                cur,
                f"SELECT {TABLE_COLUMNS['orders']} FROM public.orders WHERE updated_at > %s AND updated_at <= %s ORDER BY order_id",
                (window_start, window_end),
            )
            payload["orders"] = order_rows
            order_ids = [row["order_id"] for row in order_rows]
            if not order_ids:
                conn.commit()
                return payload

            payload["order_items"] = rows(cur, f"SELECT {TABLE_COLUMNS['order_items']} FROM public.order_items WHERE order_id = ANY(%s) ORDER BY order_item_id", (order_ids,))
            payload["payment_transactions"] = rows(cur, f"SELECT {TABLE_COLUMNS['payment_transactions']} FROM public.payment_transactions WHERE order_id = ANY(%s) ORDER BY payment_transaction_id", (order_ids,))
            payload["cancellation_requests"] = rows(cur, f"SELECT {TABLE_COLUMNS['cancellation_requests']} FROM public.cancellation_requests WHERE order_id = ANY(%s) ORDER BY cancellation_id", (order_ids,))
            payload["shipments"] = rows(cur, f"SELECT {TABLE_COLUMNS['shipments']} FROM public.shipments WHERE order_id = ANY(%s) ORDER BY shipment_id", (order_ids,))
            shipment_ids = [row["shipment_id"] for row in payload["shipments"]]
            if shipment_ids:
                payload["shipment_items"] = rows(cur, f"SELECT {TABLE_COLUMNS['shipment_items']} FROM public.shipment_items WHERE shipment_id = ANY(%s) ORDER BY shipment_id, order_item_id", (shipment_ids,))
            customer_ids = sorted({row["customer_id"] for row in order_rows})
            payload["customers"] = rows(cur, f"SELECT {TABLE_COLUMNS['customers']} FROM public.customers WHERE customer_id = ANY(%s) ORDER BY customer_id", (customer_ids,))
            variant_ids = sorted({row["variant_id"] for row in payload["order_items"]})
            payload["product_variants"] = rows(cur, f"SELECT {TABLE_COLUMNS['product_variants']} FROM public.product_variants WHERE variant_id = ANY(%s) ORDER BY variant_id", (variant_ids,))
            product_ids = sorted({row["product_id"] for row in payload["product_variants"]})
            payload["products"] = rows(cur, f"SELECT {TABLE_COLUMNS['products']} FROM public.products WHERE product_id = ANY(%s) ORDER BY product_id", (product_ids,))
        conn.commit()
    return payload


def start_run(conn: psycopg.Connection[Any], run_id: uuid.UUID, start: datetime, end: datetime, observed_at: datetime, execution_id: str, run_kind: str) -> None:
    conn.execute(
        """INSERT INTO ops.pipeline_runs
        (run_id, stage, source_system, source_account_id, stream_name, requested_window_start,
         requested_window_end, started_at, status, log_reference)
        VALUES (%s, 'ACQUIRE', %s, %s, %s, %s, %s, %s, 'RUNNING', %s)""",
        (run_id, SOURCE_SYSTEM, SOURCE_ACCOUNT, STREAM, start, end, observed_at, f"m02:{execution_id}:{run_kind}"),
    )
    conn.commit()


def fail_run(conn: psycopg.Connection[Any], run_id: uuid.UUID, at: datetime, error: Exception) -> None:
    conn.execute(
        "UPDATE ops.pipeline_runs SET status='FAILED', finished_at=%s, error_code=%s, error_message=%s WHERE run_id=%s",
        (at, type(error).__name__, str(error)[:1000], run_id),
    )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-start", required=True, type=parse_time)
    parser.add_argument("--window-end", required=True, type=parse_time)
    parser.add_argument("--observed-at", required=True, type=parse_time)
    parser.add_argument("--execution-id", default="manual")
    parser.add_argument("--run-kind", choices=("scheduled", "replay", "failure-test"), default="scheduled")
    parser.add_argument("--fail-after-raw", action="store_true", help="M02 acceptance fault injection")
    args = parser.parse_args()
    if args.window_end < args.window_start:
        parser.error("window end must not precede start")

    run_id = uuid.uuid4()
    raw_id = uuid.uuid4()
    platform_kwargs = db_kwargs("PLATFORM", "data_platform", "platform_ingest")
    with psycopg.connect(**platform_kwargs) as platform:
        start_run(platform, run_id, args.window_start, args.window_end, args.observed_at, args.execution_id, args.run_kind)
        try:
            payload = acquire_source(args.window_start, args.window_end)
            raw_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            metadata = {
                "execution_id": args.execution_id,
                "run_kind": args.run_kind,
                "order_count": len(payload["orders"]),
                "source_transaction": "REPEATABLE READ READ ONLY",
            }
            platform.execute(
                """INSERT INTO raw.raw_records
                (raw_record_id, run_id, source_system, source_account_id, resource_type,
                 resource_locator, request_method, request_window_start, request_window_end,
                 acquired_at, raw_bytes, parsed_payload, byte_sha256, contract_version, metadata)
                VALUES (%s, %s, %s, %s, 'website_order_window', 'website_source:relational_snapshot',
                        'SQL_READ_ONLY', %s, %s, %s, %s, %s, %s, %s, %s)""",
                (raw_id, run_id, SOURCE_SYSTEM, SOURCE_ACCOUNT, args.window_start, args.window_end,
                 args.observed_at, raw_bytes, Jsonb(payload), hashlib.sha256(raw_bytes).digest(),
                 CONTRACT_VERSION, Jsonb(metadata)),
            )
            platform.commit()
            if args.fail_after_raw:
                raise RuntimeError("intentional M02 interruption after durable raw write")

            platform.execute(
                """INSERT INTO ops.extraction_checkpoints
                (source_system, source_account_id, stream_name, completed_window_end, successful_run_id, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_system, source_account_id, stream_name) DO UPDATE
                SET completed_window_end=EXCLUDED.completed_window_end,
                    successful_run_id=EXCLUDED.successful_run_id, updated_at=EXCLUDED.updated_at
                WHERE EXCLUDED.completed_window_end >= ops.extraction_checkpoints.completed_window_end""",
                (SOURCE_SYSTEM, SOURCE_ACCOUNT, STREAM, args.window_end, run_id, args.observed_at),
            )
            platform.execute(
                "UPDATE ops.pipeline_runs SET status='SUCCEEDED', finished_at=%s WHERE run_id=%s",
                (args.observed_at, run_id),
            )
            platform.commit()
            print(f"run={run_id} raw={raw_id} orders={len(payload['orders'])} checkpoint={args.window_end.isoformat()}")
        except Exception as error:
            platform.rollback()
            fail_run(platform, run_id, args.observed_at, error)
            print(f"run={run_id} failed: {error}", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()

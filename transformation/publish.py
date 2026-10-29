"""Atomically promote tested dbt candidates without business transformations."""

from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime, timezone

import psycopg
from transformation.source_config import SOURCES


DELETE_ORDER = (
    "mart.source_health",
    "mart.order_status_current",
    "mart.product_activity_daily",
    "mart.order_activity_daily",
    "core.order_lines_current",
    "core.orders_current",
    "core.snapshot_evidence",
    "core.order_line_snapshot_history",
    "core.order_snapshot_history",
)

COPIES = (
    ("core.order_snapshot_history", "build.candidate_order_snapshot_history"),
    ("core.order_line_snapshot_history", "build.candidate_order_line_snapshot_history"),
    ("core.snapshot_evidence", "build.candidate_snapshot_evidence"),
    ("core.orders_current", "build.candidate_orders_current"),
    ("core.order_lines_current", "build.candidate_order_lines_current"),
    ("mart.order_activity_daily", "build.candidate_order_activity_daily"),
    ("mart.product_activity_daily", "build.candidate_product_activity_daily"),
    ("mart.order_status_current", "build.candidate_order_status_current"),
)


def connect() -> psycopg.Connection[object]:
    return psycopg.connect(
        host=os.environ.get("PLATFORM_DB_HOST", "postgres"),
        port=int(os.environ.get("PLATFORM_DB_PORT", "5432")),
        dbname="data_platform",
        user="platform_publisher",
        password=os.environ["PLATFORM_PUBLISHER_PASSWORD"],
    )


def publish(args: argparse.Namespace, now: datetime) -> None:
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext('website-publication'))")
        batch = conn.execute(
            "SELECT mapping_version, transformation_version, status FROM ops.transform_batches WHERE batch_id=%s FOR UPDATE",
            (args.batch_id,),
        ).fetchone()
        if batch is None or batch[2] != "TESTED":
            raise RuntimeError("only a TESTED batch can be published")
        owner = conn.execute(
            "SELECT source_system FROM ops.pipeline_runs p JOIN ops.transform_batches b ON b.run_id=p.run_id WHERE b.batch_id=%s",
            (args.batch_id,),
        ).fetchone()
        if owner != (args.source,):
            raise RuntimeError("batch source does not match requested publication")
        account, prefix, publication, _ = SOURCES[args.source]
        copies = tuple((target, candidate.replace('build.', 'build.' + prefix)) for target,candidate in COPIES)
        health = 'build.' + prefix + 'candidate_source_health'
        candidate_batches = conn.execute(
            f"SELECT batch_id FROM build.{prefix}candidate_order_snapshot_history UNION SELECT published_batch_id FROM {health}"
        ).fetchall()
        if candidate_batches != [(args.batch_id,)]:
            raise RuntimeError("candidate contents do not belong to the requested tested batch")
        for target, candidate in copies:
            conn.execute(f"LOCK TABLE {candidate} IN ACCESS SHARE MODE")
        conn.execute(f"LOCK TABLE {health} IN ACCESS SHARE MODE")
        for table in DELETE_ORDER:
            if table in ('core.order_line_snapshot_history', 'core.snapshot_evidence'):
                conn.execute(f"DELETE FROM {table} WHERE snapshot_id IN (SELECT snapshot_id FROM core.order_snapshot_history WHERE source_system=%s)", (args.source,))
            else:
                conn.execute(f"DELETE FROM {table} WHERE source_system=%s", (args.source,))
        for target, candidate in copies:
            conn.execute(f"INSERT INTO {target} SELECT * FROM {candidate}")
        conn.execute(
            f"""INSERT INTO mart.source_health
            SELECT source_system, source_account_id, stream_name, completed_window_end,
                   last_successful_acquisition_at, %s, pending_work_count,
                   failed_work_count, open_blocking_exception_count, coverage_state,
                   published_batch_id
              FROM {health}""",
            (now,),
        )
        conn.execute(
            """INSERT INTO ops.publication_state
            (publication_name, batch_id, published_at, transformation_version, mapping_version)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (publication_name) DO UPDATE
            SET batch_id=EXCLUDED.batch_id, published_at=EXCLUDED.published_at,
                transformation_version=EXCLUDED.transformation_version,
                mapping_version=EXCLUDED.mapping_version""",
            (publication,args.batch_id, now, batch[1], batch[0]),
        )
        conn.execute(
            "UPDATE ops.transform_batches SET status='PUBLISHED', published_at=%s WHERE batch_id=%s",
            (now, args.batch_id),
        )
        conn.execute(
            "UPDATE ops.pipeline_runs SET status='SUCCEEDED', finished_at=GREATEST(%s,started_at) WHERE run_id=%s",
            (now, args.run_id),
        )
    print(f"batch={args.batch_id} published")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-id', required=True, type=uuid.UUID)
    parser.add_argument('--run-id', required=True, type=uuid.UUID)
    parser.add_argument('--source', choices=tuple(SOURCES), default='internal_web')
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    with connect() as conn:
        conn.execute(
            """INSERT INTO ops.pipeline_runs
            (run_id, stage, source_system, source_account_id, stream_name, batch_id,
             started_at, status, log_reference)
            VALUES (%s, 'PUBLISH', %s, %s, 'orders', %s,
                    %s, 'RUNNING', %s)""",
            (args.run_id,args.source,SOURCES[args.source][0],
             args.batch_id, now, f'm03:publish:{args.batch_id}'),
        )
    try:
        publish(args, now)
    except Exception as error:
        # Release rolled back; retain the failed attempt in a separate transaction.
        with connect() as conn:
            conn.execute(
                """UPDATE ops.pipeline_runs SET status='FAILED', finished_at=GREATEST(%s,started_at),
                       error_code=%s, error_message=%s WHERE run_id=%s""",
                (datetime.now(timezone.utc), type(error).__name__, str(error)[:1000], args.run_id),
            )
        raise


if __name__ == "__main__":
    main()

"""Maintain immutable transform manifests and their run state."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import yaml


def connect() -> psycopg.Connection[object]:
    return psycopg.connect(
        host=os.environ.get("PLATFORM_DB_HOST", "postgres"),
        port=int(os.environ.get("PLATFORM_DB_PORT", "5432")),
        dbname="data_platform",
        user="platform_transform",
        password=os.environ["PLATFORM_TRANSFORM_PASSWORD"],
    )


def freeze(args: argparse.Namespace) -> None:
    now = datetime.now(timezone.utc)
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext('website-transform'))")
        active = conn.execute(
            "SELECT batch_id FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED') LIMIT 1"
        ).fetchone()
        if active:
            raise RuntimeError(f"another batch is active: {active[0]}; finish or fail it before rebuilding candidates")
        conn.execute(
            """INSERT INTO ops.pipeline_runs
            (run_id, stage, source_system, source_account_id, stream_name, batch_id,
             started_at, status, log_reference)
            VALUES (%s, 'TRANSFORM', 'internal_web', 'WEB01', 'orders', %s,
                    %s, 'RUNNING', %s)""",
            (args.run_id, args.batch_id, now, f"m03:transform:{args.batch_id}"),
        )
        conn.execute(
            """INSERT INTO ops.transform_batches
            (batch_id, run_id, mapping_version, transformation_version,
             manifest_frozen_at, status)
            VALUES (%s, %s, %s, %s, %s, 'FROZEN')""",
            (args.batch_id, args.run_id, args.mapping_version, args.transformation_version, now),
        )
        result = conn.execute(
            """INSERT INTO ops.batch_inputs (batch_id, raw_record_id)
            SELECT %s, r.raw_record_id
              FROM raw.raw_records r
              JOIN ops.pipeline_runs p USING (run_id)
             WHERE r.source_system = 'internal_web'
               AND r.source_account_id = 'WEB01'
               AND r.resource_type = 'website_order_window'
               AND p.status = 'SUCCEEDED'""",
            (args.batch_id,),
        )
        if result.rowcount == 0:
            raise RuntimeError("no successful website raw records are eligible")
    print(f"batch={args.batch_id} inputs={result.rowcount} frozen")


def transition(args: argparse.Namespace) -> None:
    now = datetime.now(timezone.utc)
    target = {"building": "BUILDING", "tested": "TESTED", "failed": "FAILED"}[args.command]
    if args.require_injected_failure:
        report = json.loads(Path(args.artifact).read_text())
        failures = [row for row in report['results'] if row['status'] not in ('success', 'pass')]
        if len(failures) != 1 or failures[0]['unique_id'] != 'test.multi_channel_orders.injected_failure' or failures[0]['status'] != 'fail':
            raise RuntimeError('acceptance requires exactly the injected test failure, with all other nodes passing')
    if target == "TESTED":
        artifact = Path(args.artifact)
        results = json.loads(artifact.read_text())
        manifest = json.loads((artifact.parent / "manifest.json").read_text())
        variables = results["args"]["vars"]
        if isinstance(variables, str):
            variables = yaml.safe_load(variables)
        if str(variables.get("batch_id")) != str(args.batch_id):
            raise RuntimeError("test artifact belongs to another batch")
        if results["metadata"]["invocation_id"] != manifest["metadata"]["invocation_id"]:
            raise RuntimeError("manifest and test results belong to different dbt invocations")
        expected = {key for key, node in manifest["nodes"].items() if node["resource_type"] in ("model", "test")}
        actual = {row["unique_id"] for row in results["results"]
                  if row["status"] in ("success", "pass") and row["unique_id"] in expected}
        if not expected or expected != actual:
            raise RuntimeError("all project models and required tests must pass before marking TESTED")
    with connect() as conn:
        result = conn.execute(
            """UPDATE ops.transform_batches
                  SET status = %s,
                      test_artifact_reference = CASE WHEN %s IN ('TESTED', 'FAILED') THEN %s
                                                     ELSE test_artifact_reference END
                WHERE batch_id = %s
                  AND status = %s""",
            (target, target, args.artifact, args.batch_id, args.expected_status),
        )
        if result.rowcount != 1:
            raise RuntimeError(f"batch transition to {target} rejected")
        if target in ("TESTED", "FAILED"):
            conn.execute(
                """UPDATE ops.pipeline_runs
                      SET status = %s, finished_at = %s,
                          error_code = CASE WHEN %s = 'FAILED' THEN 'DBT_TEST_FAILED' END,
                          error_message = CASE WHEN %s = 'FAILED' THEN 'dbt build/test failed; candidate was not published' END
                    WHERE batch_id = %s AND stage = 'TRANSFORM'""",
                ("SUCCEEDED" if target == "TESTED" else "FAILED", now, target, target, args.batch_id),
            )
    print(f"batch={args.batch_id} status={target}")


def uuid_arg(value: str) -> uuid.UUID:
    return uuid.UUID(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--batch-id", required=True, type=uuid_arg)
    freeze_parser.add_argument("--run-id", required=True, type=uuid_arg)
    freeze_parser.add_argument("--mapping-version", required=True)
    freeze_parser.add_argument("--transformation-version", required=True)

    for name, expected in (("building", "FROZEN"), ("tested", "BUILDING"), ("failed", "BUILDING")):
        command = sub.add_parser(name)
        command.add_argument("--batch-id", required=True, type=uuid_arg)
        command.add_argument("--expected-status", default=expected)
        command.add_argument("--artifact", default="runtime/dbt/run_results.json")
        command.add_argument("--require-injected-failure", action="store_true")

    args = parser.parse_args()
    freeze(args) if args.command == "freeze" else transition(args)


if __name__ == "__main__":
    main()

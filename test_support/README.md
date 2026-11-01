# Test support: choose the correct entrypoint

| Goal | Entry point |
| --- | --- |
| Everyday live data / DBeaver / dashboard | [tools/s02_data](../tools/s02_data/README.md) |
| Current recovery case inventory and runner | [M08C recovery](../docs/17_M08C_RECOVERY.md) |
| Historical B regression campaigns | [M08B](M08B.md), [temporal](TEMPORAL.md) |
| Disposable fixed S01 baseline and guards | M08A instructions below |

Do not execute every historical guide to start daily live operation. No test
runner silently replaces the owner's data. C coverage remains in STATUS and
its per-case evidence, not inferred from old B PASS results.

## M08A local isolated acceptance

For daily manual testing on your existing stack, use
[live local startup/generation](../tools/s02_data/README.md). This M08A harness is
for guarded automated regression/fault environments, not required to view live
data in your usual DBeaver connection. A live owner source with pending emissions
cannot be treated as quiet merely by stopping Airflow; see
[the M08 review](../docs/16_M08_LIVE_LOCAL.md).

This host-only harness creates an explicitly disposable environment for the
existing fixed S01 pipeline. It is NOT the changing-source S02 generator or a
load/fault runner. Read [finalized isolation policy](../docs/11_M08A_ISOLATION.md)
and [S02 roadmap](../docs/10_S02_TEST_STRATEGY.md).
The separate [M08B guide](M08B.md) covers the new seeded S02 profiles; do not pass a
B marker to A acceptance or seed S01 into a B scope. M08A commands remain unchanged.
The separate [temporal PostgreSQL guide](TEMPORAL.md) covers new s02-pg IDs;
legacy RAM IDs and PASS results cannot be reused for that backend.

Local verification: fresh run `49a6b80472b1` PASS61 steps; owner Airflow was
temporarily stopped with explicit permission and restored healthy afterward.
Protected owner data and all DAG pause states were unchanged. See STATUS for
failed attempts, exact evidence and the separately verified log-preservation fix.
This does not certify simultaneous dual-Airflow operation on a4GB VM or M08B-D.

## Prerequisites / safety

- Run from repository root with Python3.12+, Docker Engine/Compose, and Git.
  No host Python dependencies or new marketplace credentials are needed.
- The existing owner project must be running and idle for protected-signature
  acceptance: no active DAG runs/batches, periodic/replay DAGs paused. The harness
  will refuse otherwise; it NEVER pauses/stops owner services. Owner raw is only
  hashed for protection, never used to initialize the isolated baseline.
- Full acceptance requires Docker memory >=6GiB and >=3GiB measured container-
  memory headroom; another running M08A identity must be stopped first. This guard
  runs before service creation. Configure resources yourself; the harness never
  changes Docker settings. Services are capped and dbt builds precede isolated
  Airflow startup; isolated Airflow stops before report UI tests. A second Airflow
  on a4GB Docker VM timed out during local verification; Engine then became
  unavailable. A timeout/OOM is a failure,
  not permission to stop owner services or increase VM resources automatically.
  With a separately owner-authorized temporary stop of owner Airflow, the single-
  Airflow guard permits >=3.5GiB total, still requiring >=3GiB headroom. The harness
  never performs that owner stop; restoring it also needs an explicit safe workflow.
- Init uses `.env.example` keys and random local test credentials, NOT `.env`.
  Private env/rendered JSON/runtime/evidence stay under ignored `runtime/isolated`.
  Do not print/share generated config, passwords or raw logs unreviewed.

## PowerShell / shell commands

```powershell
python tests/test_m08a_guards.py
python -m test_support.m08a init
```

Copy the printed12-hex ID. Then, replacing the example value with YOUR printed ID:

```powershell
$testId = 'YOUR_PRINTED_ID'
python -m test_support.m08a check --id $testId
python -m test_support.m08a accept --id $testId
$LASTEXITCODE
```

`check` means config/resource preflight only, not a full runtime PASS. `accept`
requires a NEW never-used volume/ID. It builds the existing images with isolated
tags, bootstraps the actual migrations, retains Website3/eBay2/Etsy1 observations,
releases through dbt/test/publish, checks PostgreSQL restart/persistence, initializes
fresh Airflow metadata/DAGs/observer, and runs existing S01/report SQL and UI checks.
No new periodic run is enabled; no injected failure or abrupt-kill campaign runs.
Existing M02/M03/M05/M06 full fault runners are NOT rerun by this bounded baseline.

Expect exit0 and final `M08A acceptance PASS ... owner signature unchanged`.
Intermediate step PASS is not overall PASS. Command logs and final result are in
`runtime/isolated/m08a-ID/evidence/`; `result.json` includes signatures and teardown.
Normal finally-teardown removes TEST containers/network only; it preserves TEST
PostgreSQL volume, private env, dbt artifacts and evidence. No owner volume is reset.
Command logs use unique names across invocations, including a later `stop`.

On failure, inspect the named ignored log/result, do not rerun seed into the same
database. Correct the cause, `init` a NEW ID, then repeat acceptance. Failed test
volumes/evidence remain for diagnosis. A changed base Compose/config hash, engine,
marker, writable bind, service identity or conflicting host port causes refusal.
The harness is protection against accidental wrong targets, not malicious host users.

For guarded teardown of a known test ID if its configuration is unchanged:

```powershell
python -m test_support.m08a stop --id $testId
```

Do not run stop concurrently with accept. There is intentionally no reset, kill,
volume-delete or arbitrary Compose passthrough command. If a guard prevents cleanup,
inspect the exact resources and request explicit recovery direction; don't bypass
with broad prune/down-volume commands. Retained test volumes consume disk; no
automatic cleanup/removal is claimed or performed.

## CI and scope

`.github/workflows/offline-smoke.yml` runs fixture verify,10 utility tests, offline
guard tests and compile checks with SHA-pinned official actions, read-only repo
permissions and no persisted checkout credentials. The local commands are runnable
now; remote Actions execution is separate and is not claimed without a real run.
S02 generation/integration CI is M08B; fault/restart campaigns M08C; load M08D.

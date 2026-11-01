# M08A finalized isolation / safety harness contract

Selected 2026-10-30 before implementation. Scope: fresh isolated S01 baseline as
the prerequisite for S02, negative guards, migration rerun, ordinary PostgreSQL
restart/persistence and offline CI. No changing-source generator, injected-fault/
load campaign or automatic owner service restart. A separately owner-authorized
manual stop/restore of owner Airflow may provide a small-VM test window; keep
owner PostgreSQL running and verify owner health/pause states/data after restoring.
M08B-D remain separate review gates.

## Target definitions (no warehouse DDL additions)

- Host entrypoint: `python -m test_support.m08a {init,check,accept,stop} [--id ID]`.
  ID is exactly 12 lowercase hex characters. Init allocates a random ID; subsequent
  commands require it. No arbitrary Docker passthrough, reset, kill or volume
  delete command. Stop removes only validated test containers/network, preserving
  named volume, credentials and evidence. No automatic start of the next milestone.
- Root is strictly `runtime/isolated/m08a-ID/` under this repository; no symlinks/
  junction escapes. `test.env`, `compose.json`, `identity.json`, `evidence/`, and
  `binds/{dbt,airflow-logs,airflow-state}` are ignored runtime, never committed.
- Project `m08a-ID`, PostgreSQL volume `m08a-ID_postgres_data`, network
  `m08a-ID_default`. Containers/volume/network carry Compose project labels plus
  `local.m08a.identity=ID`; services come from an exact reviewed allowlist.
- `identity.json`: format_version INTEGER=1, id TEXT matching above, project TEXT,
  repository/root absolute TEXT, engine_id TEXT, created_at UTC ISO TEXT,
  model_sha256/env_sha256/base_sha256 TEXT (64 hex), db_system_id TEXT nullable
  until first verified bootstrap. Identity/hash/config mismatch is a hard error.
  Persist generated files using exclusive creation; never overwrite another run.
  Acceptance also creates an exclusive `evidence/accept.started` latch, retained
  as audit, so two processes cannot both seed the same fresh run concurrently.
- `test.env`: generated from example KEYS/defaults, never owner `.env`; random
  role passwords/tokens/signing secret/UI password. Scrub inherited Compose and
  interpolation variables. All host endpoints get distinct loopback available
  ports; internal DB/DNS remain postgres:5432, APIs remain service DNS. A free-port
  preflight is not a reservation: startup races fail safely and must be reported.
- Generate standalone canonical Compose JSON using the installed Compose renderer
  on the existing base, then replace all writable mounts/resource names/host ports
  and project-specific image tags. Do not merge arrays with an overlay that might
  retain owner mounts. Only bootstrap/migrations are normal read-only host mounts.
  Test commands may add allowlisted read-only repo/fixture mounts; normal pipeline
  services never receive them. Rendered JSON contains secrets: don't print/log it.
- Resource caps: postgres384MiB; Airflow1536MiB; dbt/publisher/checks512MiB;
  report384MiB; observer128MiB; source/receiver/collector services128MiB each.
  Caps are safety settings, not throughput guarantees. Phase business builds
  before starting isolated Airflow; stop test Airflow/observer after metadata checks
  before report AppTests. Keep default test teardown bounded and evidence-preserving.
  Isolated PostgreSQL health checks TCP (not the temporary init Unix socket).
  Isolated Airflow health uses the lightweight HTTP monitor and requires healthy
  metadata DB, scheduler AND DAG processor, not merely HTTP200. Avoid repeated
  heavyweight CLI imports during cold startup; keep CLI import-error checks as
  a separate acceptance step. Owner Compose health settings are not modified.
  After the observed 4GB dual-Airflow timeout/Engine failure, full acceptance now
  requires Docker memory >=6GiB and >=3GiB measured container-memory headroom,
  with no other active M08A identity. This is a fail-fast prerequisite before
  service creation, not an automatic Docker settings change or capacity guarantee.
  If the owner explicitly authorizes a separate temporary stop of owner Airflow,
  single-Airflow topology permits >=3.5GiB total but still requires >=3GiB headroom.
  The harness never stops/restores owner services itself.

## Guard before any Docker mutation

Check ID/path/marker/hashes/current Docker engine; re-render and validate exact
service set, DB/API endpoints, no external links/host network/privileged/socket,
all mount/port/resource/project identities. Inspect existing project containers,
volume and network: labels and actual mount/port/network bindings must match the
validated model; refuse foreign resources before up/run/restart/stop. For a running
test DB verify its system identifier (first fresh bootstrap records it); don't bind
an already populated unrecognized DB as a fresh test. No missing-label adoption.
Acceptance requires a new never-seeded volume; rerunning acceptance refuses to
rewind source history. Resume diagnosis uses check/stop; create a new ID for a new
cold acceptance. Marker is an accidental-target safety barrier, not a sandbox
against a malicious host user who can rewrite Docker resources and marker hashes.

Owner comparison uses READ ONLY REPEATABLE READ SQL via the identified existing
`multi-channel-order-platform` PostgreSQL container. Require no active DAG runs or
enabled periodic DAGs and no active transform batch; otherwise stop before creating
test services and request a quiet window. Hash source tables and protected raw,
business, work/inbox/delivery/checkpoint/run/config/publication rows; exclude
scheduler heartbeat/observer samples. Compare before/after, with a second idle
check. Concurrent owner activity makes comparison inconclusive, not PASS. Never
pause/stop/restart the owner environment to obtain a quiet window automatically.

## Ordered acceptance and evidence

1. Offline guard-negative tests (wrong ID/marker/hash, writable owner mount,
   wrong volume/project/network/service/endpoints, public/colliding ports, path
   escape, foreign labels/resources) must reject before mutation.
2. Owner idle/signature preflight, test volume absence, build required existing
   images, fresh postgres bootstrap, record test DB identity, run migration rerun
   and existing M01/source boundary checks using test services only.
3. Use existing simulator/collector commands to retain Website3/eBay2/Etsy1
   observed versions; no fault injections. Reuse existing dbt batch/build/test/
   publisher commands for three source releases. Use existing M06 golden probe
   and M07 SQL/rule/real-DB/UI/secret boundaries, not an invented warehouse seed.
4. Ordinary isolated PostgreSQL restart; stable signature/system ID preserved,
   rerun migrations idempotently. Start isolated Airflow from fresh metadata,
   wait for health/imports, verify intended DAGs and no automatic periodic runs,
   sample scheduler safely. No scheduled or abrupt-loss campaign claimed in A.
5. Report HTTP/UI checks; protected owner signature unchanged. Default stop test
   containers/network in finally; preserve volume/logs and compare owner again.
   Teardown or signature failure prevents final PASS even if business checks passed.

Per-command ignored logs and `evidence/result.json`: format_version1, ID/project,
code SHA, start/end UTC, step names/status/log paths, protected signatures before/
after, test DB identity and aggregate outcomes, teardown status, overall
PASS/FAIL/INCONCLUSIVE. No credentials or expanded config in safe summaries.
New command logs have a step prefix plus a unique UUID; a later `stop` invocation
must never overwrite a previous acceptance log under the same retained run ID.
Timeouts are bounded (config/inspection30s, ordinary commands180s, image build600s,
health wait420s, dbt300s); actual results and any unrun checks go in STATUS.

Offline CI uses standard-library Python to run fixture checks, utility tests,
guard tests and compile checks; no Docker/credentials needed. The workflow is
versioned in A; an unrun remote Actions job is not reported as executed.

Compose design references: [canonical config renderer](https://docs.docker.com/reference/cli/docker/compose/config/)
and [project-name precedence](https://docs.docker.com/compose/how-tos/project-name/).
Runtime validation, not merely a project prefix, is the acceptance evidence.

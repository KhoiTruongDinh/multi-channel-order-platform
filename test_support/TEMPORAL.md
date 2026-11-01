# M08B temporal PostgreSQL source checks

For everyday manual generation and stable local connections, use
[tools/s02_data](../tools/s02_data/README.md), not these per-case credentials.
The commands below retain the earlier wall-clock temporal regression path.
The new logical-clock scheduled gate is explicitly selected with
`python -m test_support.m08b_window --confirm-owner-airflow-window --local-replay`;
it requires current-task owner maintenance permission. Results of the old path
do not certify the new one. Both preserve owner data and retain test volumes.

Design/schema/source-branch contract and diagrams:
[document14](../docs/14_S02_TEMPORAL_SOURCE.md). Actual PASS/FAIL, hashes,
retained IDs and not-run checks are in [STATUS](../docs/STATUS.md).
Old RAM acceptance is NOT acceptance of this backend. Stop before M08C.

## Modes and boundaries

`m08b` preserves the6-order/two-wave RAM case. `m08b_temporal` creates NEW B
markers with backend=s02-pg. Never reuse RAM IDs/volumes, edit marker hashes or
seed S01 into a temporal DB. Ordinary Compose stays S01. The new migration is
applied ONLY by the guarded temporal runner, not owner bootstrap/migrate scripts.
No host dependency beyond stdlib: simulators install existing pinned psycopg.
Reader passwords are random/private per model; never print compose.json/test.env.

Prepared source versions are sealed; GET selects latest visible state with actual
PG UTC clock1x, no runtime marketplace random/status UPDATE. Website uses its
existing source writer and Etsy uses signed notifications outside a DAG.
30 products/variants,90 independent mappings (`s02-catalog-v1`),100 synthetic
customers; Website seeds references on first due order. Orders choose1..8 distinct
products and quantity1..5. Small random campaigns need not purchase every product.
No invented eBay buyer field, refund or delivery state.

## Offline checks

```powershell
python tests/test_s02_diverse.py
python tests/test_s02_temporal.py
python tests/test_m08b_sources.py
python tests/test_m08a_guards.py
python tests/test_m06_scheduling.py
python -m compileall -q simulator ingestion transformation orchestration reports test_support tests
```

From fixtures/s01 also run `python verify.py` and
`python -m unittest -v test_tools.py`. These do not certify DB/schedules.

## Allocate a NEW isolated ID

Repository root; owner PostgreSQL running/idle and periodic owner DAGs paused.
The harness verifies before/after protected signatures and NEVER stops owner
services. Docker access is required. Choose ONE runtime check per fresh ID.

```powershell
$created = python -m test_support.m08b_temporal init
if ($LASTEXITCODE -ne 0) { throw 'Init failed' }
$created
$idMatch = [regex]::Match(($created -join "`n"), 'id=([0-9a-f]{12});')
if (!$idMatch.Success) { throw 'No generated ID' }
$testId = $idMatch.Groups[1].Value
python -m test_support.m08b_temporal check --id $testId
if ($LASTEXITCODE -ne 0) { throw 'Preflight failed' }
```

### A. Storage/HTTP probe

```powershell
python -m test_support.m08b_temporal storage --id $testId
if ($LASTEXITCODE -ne 0) { throw 'Storage probe failed' }
```

Builds marketplace images, bootstraps test PG and prepares a small day schedule.
Checks DB visibility boundaries/seal/reader isolation, HTTP pending reconstruction,
migration rerun and test simulator restart persistence. Requires>=3.5GiB Docker
total. NOT pipeline/scheduled acceptance. Results: evidence/temporal-result.json.

### B. CLI initial-load/replay baseline

```powershell
python -m test_support.m08b_temporal accept --id $testId --profile baseline --seed 17
if ($LASTEXITCODE -ne 0) { throw 'Temporal baseline failed' }
```

Requires>=3.5GiB total and>=1.5GiB measured headroom. No second Airflow scheduler
starts; its project-venv CLI does acquisition/dbt/release. Defaults12 orders with
varied lines, all changes already due, independent source/warehouse reconciliation
and replay. Missing intermediate versions are not invented in history.
Results: evidence/result.json. No load/capacity claim.

### C. Real scheduled changing-source correctness

```powershell
python -m test_support.m08b_temporal accept --id $testId --profile continuous --seed 17
if ($LASTEXITCODE -ne 0) { throw 'Temporal scheduled acceptance failed' }
```

Requires>=6GiB Docker with owner Airflow running, or an explicitly owner-authorized
maintenance window with owner Airflow stopped,>=3.5GiB total and>=3GiB headroom.
The acceptance harness never stops/restores it. Use the exact idle/stop/finally-restore
procedure in [M08B.md](M08B.md), replacing only test commands with temporal commands.
Check original owner pause states and health afterward. No Docker restart/deletion.

Alternatively, ONLY after explicitly authorizing this maintenance window, use:

```powershell
python -m test_support.m08b_window --confirm-owner-airflow-window
if ($LASTEXITCODE -ne 0) { throw 'Scheduled test or owner restoration failed; inspect evidence' }
```

This separate wrapper requires an idle owner and exactly one healthy running
owner Airflow. It captures its exact container identity, DAG pause states,
protected-data signature and PostgreSQL system identity; stops only that Airflow;
allocates a NEW temporal test ID; runs continuous acceptance; and restores the
same owner Airflow in `finally`, including test/init failures. It verifies health
and all captured signatures before reporting PASS. Evidence is retained under
`runtime/isolated/window-*/owner-window.json` plus the printed test-ID directory.
It never stops PostgreSQL, deletes storage, changes owner DAG pause states or
restarts Docker. If restoration fails, the evidence identifies the exact owner
container needing attention; do not interpret a test PASS alone as window PASS.

Prepares a1200s finite1x schedule after image/bootstrap work. Enables website/eBay/
inbox once, proves omitted Etsy receipts absent before enabling recovery; waits
for final facts, observed changes per source and>=2 scheduled successes per path.
Requires raw-linked history and all terminal runs successful after drain signal.
Final explicit CLI phase is replay only. Wait budget3600s, synchronous commands
separately bounded; not a hard1h process kill or a24h load certification.

## Prepare one day BEFORE testing

On another NEW temporal ID, before runtime:

```powershell
python -m test_support.m08b_temporal prepare --id $testId --seed 17 --orders-per-channel 1000 --duration-seconds 86400
if ($LASTEXITCODE -ne 0) { throw 'Preparation failed' }
```

Writes ignored host-only evidence/prepared-source.json, SHA256 and marker binding.
No DB/pipeline verification implied. Source-shaped versions/references are not
warehouse expected outputs. Repeat prepare refuses overwrite. Count2..10000/channel
is an input bound, NOT tested capacity. Choices/timestamps fixed before serving;
actual reads/deliveries remain separate evidence. No normal Compose auto-seed.

`accept` consumes a prepared dataset if present. CLI baseline requires all changes
already due; continuous correctness requires future changes within its budget.
A future24h playback plan is refused by short continuous correctness acceptance;
an all-due day may be used as CLI initial load, subject to finite command/resource
limits (not a capacity claim). A general
24h playback/load driver and accelerated clock remain later workload work; this
prepare command does NOT run a24h pipeline load test. For prepared initial load,
use duration30 and `--start-delay-seconds -120`; a full day entirely in the past
needs an earlier start, such as delay -90000. Without a file, acceptance prepares
its own bounded dataset. No runtime random regeneration after preparation.

## Evidence and cleanup

```powershell
$result = Get-Content "runtime/isolated/m08a-$testId/evidence/result.json" -Raw | ConvertFrom-Json
$result | Select-Object status,teardown,protected_check
$result.s02
```

PASS requires exit0 plus status/teardown/protected_check PASS. Failure/logs and
volumes remain; use a NEW ID after failure, never rewind its source DB. Teardown
removes only test containers/network. Stop an idle/completed test with:

```powershell
python -m test_support.m08b_temporal stop --id $testId
```

Owner dashboard stays unchanged: all generated warehouse data is isolated.
Clock pause/resume/fault matrices and measured load envelopes remain M08C/D.
Offline CI includes new tests; remote Actions is not verified unless STATUS says so.

Developer-only `verify-retained --id COMPLETED_PASS_ID` starts ONLY the validated
retained test PostgreSQL and performs final-code read-only raw-linked history and
report-role totals checks, then tears it down again without deleting storage. It
requires a completed PASS/result and bound prepared checksum, records separate
temporal-readonly-*.json evidence, and is NOT a second cold/scheduled acceptance.
`replay-retained` is different: it writes new raw/work/audit in that completed
test scope by rereading sources and releasing them again, then compares logical
signatures. `notification-retained` sends two actual retained webhook duplicates
and verifies physical/logical counters. Both record separate scoped evidence,
retain storage, verify owner protection and are not a new cold/scheduled run.

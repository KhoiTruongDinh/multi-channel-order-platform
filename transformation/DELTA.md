# Experimental M08D delta execution

Checkpoint2026-11-13: retained-main rollout and the UNCHANGED900 finite envelope
PASS (900orders/3801lines, zero reconciliation errors, observed drain96.438s).
The MAX<=10s target is NOT achieved; marketplace collection, including mutable
eBay pagination retries, now dominates. Burst/soak and full M08D remain pending.
Exact commands, resource/stage measurements and report links are in STATUS.

Delta requires an **explicit verified deployment**, not an automatic `live-up`
upgrade. Main Compose now exposes optional `LIVE_DELTA_PLAN_DIR`, default blank,
to the existing polling coordinator. Setting it alone is not enough: live-up
refuses plans without matching verified publication pointers. Do not manually
replace a live workflow with these Python functions.
Migration012 remains outside the ordinary bootstrap/migrate/live-up lists.
Bounded daily scope revision2026-11-14 also needs013_daily_scope_access.sql
(SELECT on existing daily marts for bootstrap scope); guarded delta deployment
applies012 then013 before compile/bootstrap. Existing releases must not be reused.
Daily helpers recompute old/new affected UTC creation dates; publisher reconciliation
is limited to that tested scope, not source-wide absence deletion. Source-created
business cohorts and actual execution-time monitoring remain distinct. See
../docs/24_ACTIVITY_TIME_REVIEW.md for model/publisher and staging-clock details.
The explicit `tools.s02_data.delta_deploy` command drains main, applies additive
migration012, compiles three plans and runs full-dbt-verified cold bootstrap
before activation. See STATUS for actual rollout progress; implementation and
private gates do not certify retained-main load900 or the warm latency target.

Design and acceptance clock: [21_M08D_DELTA_RUNTIME.md](../docs/21_M08D_DELTA_RUNTIME.md).
Actual verification, failed checks and remaining work: [STATUS](../docs/STATUS.md).

## Code order

1. `transformations/macros/delta.sql`: raw-to-order identity routing, session batch
   binding, private schema naming and effective current-state mart inputs.
2. `transformation/delta_plan.py`: deployment-time dbt compilation, dependency
   ordering, source-local invariant test selection and plan/source/mapping identity.
3. `transformation/delta_runtime.py`: explicit bootstrap, immutable affected keys
   and exact new inputs; dbt-derived CTAS graph and quality gates in a transaction.
4. `transformation/delta_publish.py`: affected-history/current replacement,
   dbt-calculated mart merge, publication pointer and raw consumption in one commit.
5. `tests/delta_runtime_probe.py`: disposable integration test and full dbt oracle.
6. `orchestration/delta_workflow.py`: deployment validation, pinned cycle identity
   and adapters for the existing freeze/build/test/publish stage ledger.
7. `transformation/admission.py`: shared short registration fence for legacy and
   delta paths; an unrelated live owner cannot be bypassed by manual freeze.
8. `transformation/delta_bootstrap.py`: explicit cold full-dbt/multiset oracle
   before publication, including retention of observed source identities.
9. `tools/s02_data/delta_deploy.py`: guarded retained-main deployment; requires
   passing strict restart/mapping reports and observes actual scheduled successes.

The compiled plan is a local deployment artifact, not a hand-maintained SQL file.
Plan/source/mapping mismatch refuses execution. A new plan requires an explicit
cold bootstrap; it cannot silently mark old raw as already processed.
Only the pinned table/view graph, canonical-function project hooks, Etsy cache
pre-hook and zero-failure ERROR tests are supported. Unsupported materializations,
enforced model contracts, extra hooks or changed test policies refuse compilation;
extend the runner and regression deliberately rather than silently ignoring them.
The experimental build uses transaction-local `jit=off` and analyzes each new
candidate table. Diagnostic evidence and scope are in STATUS; neither policy
changes server-wide configuration or the full dbt regression path.

## Run the disposable check

From the repository root in PowerShell, with Docker Desktop running and the
project Airflow image already built:

```powershell
python -m unittest -v tests.test_delta_plan
python tests/delta_runtime_probe.py --docker --report runtime/delta-review-01.json
# Optional longer check: 27 collector cycles, retaining all warehouse/raw rows.
python tests/delta_runtime_probe.py --docker --http-rounds 3 --report runtime/delta-review-retained-01.json
```

Choose a new report path for another run. The test reads the existing Airflow
container's image ID, not its database or credentials. It creates a labeled,
internal-only Docker network, PostgreSQL with temporary storage and a short-lived
dbt worker. No published host port, owner `.env`, owner runtime directory or owner
volume is mounted. There is no second Airflow scheduler. Cleanup removes only
the exact generated resources after their probe label is verified.
Compilation of three plans plus the separate full dbt oracle can take several
minutes. Test duration is not the warm cycle latency target.
`--http-rounds` accepts only1..3;3 repeats the1/10/100 pattern three times and
creates333distinct new orders/source, in addition to the small regression seed.
It never clears warehouse/raw between waves. Source current-state test setup
remains bounded to100orders/wave. This is not the owner900 campaign or a soak.

It reapplies012, bootstraps all three source graphs from synthetic S01 interface
responses, exercises duplicate acquisitions, failed tests, publication rollback/
retry, no-input ticks, an unaffected order, late versions, real invalid-money
refusal, physical/durable source fencing and Python interruption after real DDL
(not a process-kill claim). Finally, ordinary `dbt build` runs on all the same
evidence and all eight core/mart output
relations are compared as multisets, excluding only batch lineage columns.
Source payloads are seeded by **test code**, not by a pipeline source adapter.

The probe now also runs real read-only Website SQL and marketplace HTTP
collectors for 1/10/100 changed orders, then checks the independently readable
publication pointer. `tests/delta_http_cases.py` records each phase and explicitly
separates these end-to-end samples from SQL-only timings. Profiling is opt-in via
`DELTA_PROFILE_ETSY=1` inside the worker; instrumented times are not SLA samples.

Coordinator cases exercise durable five-attempt exhaustion, explicit abort,
handoff without raw loss, same-source exclusion, independent-source progress
without the legacy global build lock, actual Airflow owner metadata, atomic
publication audit, pinned-plan refusal and already-published reentry.

`tests/delta_process_cases.py` extends the same disposable probe with real child
SIGKILL after uncommitted candidate CTAS and during uncommitted publication.
It checks lock release, retained last-good reader state, unconsumed raw, durable
interrupted publisher audit and successful retry. A two-process barrier also
releases Website/eBay builds together and checks both committed pointers. These
are real SQL/process tests, not an Airflow task/scheduler/container-kill claim.
Execution results, including failures, belong in STATUS; implementation is not PASS.

PASS here does not certify scheduled Airflow integration, Airflow/container-kill
recovery, retained owner-scale data performance or the
<=10s target across workloads. Those are separate rollout gates. A correctness
PASS is not a latency PASS; inspect individual samples and STATUS.

## Explicit private bootstrap interface

After applying migration012 in a disposable scope and compiling a source plan,
the operator interface is `python -m transformation.delta_runtime --plan PATH
--bootstrap --batch-id UUID --run-id UUID --publish-run-id UUID [--attempt N]`.
Preserve the batch/run identities on reentry; advance build attempt only after
failure/interruption (1..5). A failed publication needs a fresh publish-run UUID;
an already-published batch does not create another publication attempt.
Compilation artifacts use the system temporary directory, not a writable source
tree. Compiled plan output must be retained separately for deployment.
This is not a main-stack activation procedure: retained-data bootstrap, real
scheduler retry/restart and larger-load gates remain before rollout.

## Optional real scheduler gate (owner approval required)

`python tests/delta_scheduler_probe.py --allow-owner-idle-stop --report
runtime/delta-scheduler-review-01.json` uses a separate labeled internal network,
temporary PostgreSQL and the existing image with read-only review code mounts.
It does not activate delta or apply migration012 on main. On the approximately
4GB Docker topology, it first places its own token in the supported main drain
signal (only if absent), preserving all DAG pause flags and existing retries.
Only after no active runs/batches/nonterminal owners remain continuously for15s
does it stop the exact main Airflow container. This quiet check handles intervals
already calculated before drain; it stays inside the same600s timeout and fresh
pre/post-stop checks remain mandatory. Timeout refuses, never aborts.

The test uses the production Website DAG configured with its supported
fault_after_freeze_once parameter. It requires actual scheduled retry, restart
of the test Airflow container between attempts, successful reentry without
recollection, SUCCESS on that exact interrupted DAG and two successful scheduled
runs ending after restart. Final Airflow task/run states and the publication
pointer are recorded/asserted; pre-restart warm-ups cannot satisfy that gate.
The wrapper sets the supported fault param on both DAG AND tasks because task
params take precedence. A real SDK serialization check runs before unpause.
It does not replace operators
or collectors with mocks. This single-source scheduler gate is not all-source
or load/SLA certification; actual results belong in STATUS.

Cleanup verifies labels before removing exact test resources. A finally block
restores the same main container, verifies health and unchanged pause flags,
and removes only its own drain token. It writes an ignored runtime journal and
new report even on failure; never remove an externally changed signal. No owner
`.env`, database volume or runtime directory is mounted in the test containers.

### Retry diagnostics and four-DAG extension

Task logs are now archived inside the private container and copied as a portable
tar.gz to the ignored evidence directory even on PASS, before containers are
removed. Do not extract colon-containing native run IDs onto Windows. Reports include native task history and
reschedule rows, separately from the logical business-stage attempt ledger.
The configured one-time freeze fault applies once **per workflow cycle**, not once
per deployment: later scheduled fault-enabled cycles normally also need a retry.
Do not attribute additional tries to resource pressure without the actual logs.

The diagnostic rerun reproduced four tries: intended freeze failure; an attempt
started during the30s shutdown grace period; an orphan-reset attempt dispatched
before the standalone Execution API was listening (ConnectError111); then success.
This explains the observed retries but does not harden main's startup. A future
startup gate must wait for API readiness without circularly requiring scheduler
health before starting the scheduler. Do not increase retry budgets to hide it.

`python tests/delta_scheduler_probe.py --all-sources --allow-owner-idle-stop
--report runtime/delta-scheduler-four-dags-01.json` selects a separate gate with
the same owner protections. It compiles/bootstraps three plans, runs all four
production periodic DAGs, and starts private marketplace HTTP listeners plus the
real webhook receiver outside Airflow. No host ports are published. Test setup
adds one signed notification and a second receipt without a notification.

A bounded physical Etsy source advisory lock forces both Etsy sensors to
reschedule while Website/eBay must complete. After release, each of the four
DAGs must finish at least two actual scheduled runs, preserve its plan identity,
complete every business stage once, and retain both Etsy receipts, including
the one found only by recovery. Native task state is never updated by the test.
This gate disables intentional freeze faults; it is not a load benchmark or an
owner-stack delta rollout. Implementation alone is not runtime acceptance;
consult STATUS for the exact executed commands and outcomes.

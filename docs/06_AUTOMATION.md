# Local automation and acceptance contract

Daily local M08B live revision (2026-11-01): [live sources](16_M08_LIVE_LOCAL.md).
Start source services/worker and schedules once; manual generate admits additional
source batches without dataset configuration in consumers. Uses actual UTC,
normal SQL/HTTP interfaces and retained checkpoints. Per-batch clock selection
below applies to explicit replay, not this live path. Acceptance status: STATUS.
New live cycles use actual UTC at cycle entry, not stale Airflow interval ends;
the window/policy is persisted and retries never resample it. Coordinator waits
can still delay acquisition; this does not promise every source state is observed.

Planning revision: 2026-10-30; the M08 stabilization split is defined in
[10_S02_TEST_STRATEGY.md](10_S02_TEST_STRATEGY.md). M05B implements the website/eBay
requirements below; exact runtime evidence
and limits are in STATUS. M06 implements the local Etsy requirements; M07 reporting
is implemented. M08A isolates test storage/runtime; M08B adds finite seeded S02
generation/scheduled correctness with local case-based checks. Recovery faults/load remain
planned M08C-D work. M09 packages verified demos. M08A's actual commands/
prerequisites are in [the host harness guide](../test_support/README.md), with
local acceptance and resource limits recorded in STATUS. Do not infer runnable
C-D commands from this plan. B commands/limits are in
[the S02 guide](../test_support/M08B.md); STATUS records actual acceptance.
Approved S01 payloads, source interfaces, identities, money and observed-history
rules remain fixed. The current executable checkpoint is in [STATUS.md](STATUS.md).

## Current versus planned execution

| Path | Implemented now | Required delivery |
| --- | --- | --- |
| Website | M02/M03 pipeline, M04 manual S01 DAG, M05B opt-in periodic polling | M08A isolated setup; B generation; C recovery; D load |
| eBay | M05A HTTP pipeline, M05B bounded periodic/replay DAGs | M08A isolated setup; B generation; C recovery; D load |
| Etsy | M06 always-on receiver, leased work, scheduled inbox/recovery, tested publication | M08A isolated setup; B generation; C recovery; D load |
| Changing local sources | Manual fixed-state playback | M08B opt-in independent current-clock S02 driver after A |
| Dashboard | M07 read-only three-screen UI, release labels and real stage/slot/scheduler monitoring | S02 correctness/lag/load evidence in B-D; no automatic browser refresh implied |

## Clock and execution modes

**S01 replay** uses the approved 2026-10-17 source clock and retained observations.
The test driver advances source fixtures outside ingestion/DAGs; it pauses source
state during reads. Replay uses explicit windows and records actual acquired
snapshots. It must not silently run today's windows against historical checkpoints
or synthesize old states from a final response.

**Periodic polling** is an opt-in local runtime mode, implemented at a configurable
five-minute interval for website/eBay. Schedules must start disabled/paused until
the operator selects the mode, source/account and initial extraction start. Do
not reinterpret the existing manual S01 DAG's dates as live defaults. Services
must stay running for jobs to execute; enabling a schedule is a one-time operator
action, not a command per polling cycle. Automatic historical catchup is disabled
initially; a restart reads the last successful checkpoint rather than pretending
all missed intervals ran.

**Continuous demo** additionally needs actual source changes with current-clock
timestamps. M08B's finite opt-in simulator/driver supplies them independently of the DAG.
Polling a frozen S01 source may correctly return empty windows; it does not advance
the source clock, create orders or recover previously unobserved history. Original
S01 golden tests and continuous-demo assertions must use separate evidence/scopes.
Do not mix historical and current-clock checkpoint state in the owner's dataset;
use an explicitly isolated disposable acceptance environment or a separately
designed operational scope. No automatic checkpoint rewind or data reset.

S02 acceptance campaigns require the dedicated M08A isolated scope, including
all writable bind mounts, not just a Compose project prefix. Everyday manual
generation may instead use an explicitly clean local scope under document15;
there is no automatic owner S01 transition. The generator/test ledger is inaccessible to
pipeline/report services. M08C distinguishes graceful restart, abrupt process loss,
normal DAG pause and drain maintenance; recovery may be a tested explicit operator
procedure rather than guaranteed automatic handling. M08D adds bounded load,
burst/soak and predeclared resource/deadline criteria; full-history rebuild/snapshot
publication remain potential limits until measured and safely improved.

## Bounded polling and durable execution

At the first run require an explicit initial start. For subsequent cycles use the
last successful source/account/stream upper bound minus 120 seconds of configurable
overlap. Fix one upper bound per cycle (the scheduled interval end, or an explicitly
captured manual bound), persist start/end and execution identity before work, and
reuse them on retries/restart. Observation/fetch time is distinct from source time
and the requested bound; do not stamp current responses with historical S01 times.
Retain both the source observation clock and actual execution provenance where
simulation requires them. Recovery after downtime must cover the checkpoint gap;
any maximum-window chunking must finish each chunk without silently skipping time.

Advance acquisition only when required responses and identified work are durable;
preserve M05A's stronger requirement that required details also succeed before
its window completes. Failed pages or malformed envelopes cannot advance it.
Successful empty windows are recorded as successes. Acquisition completion and
tested business publication are independent; dbt failure keeps raw/checkpoint
evidence and leaves the good release intact.

Retain at most five durable stage attempts per explicit workflow/replay cycle
across Airflow retries/restarts/clears. HTTP retries must also remain bounded;
record their attempt provenance and the nested stage/request limits so retries
do not create an undocumented unbounded loop. A new recovery cycle must be an
explicitly identified action/policy, not a hidden reset on each task retry.
Preserve run/batch/raw/artifact links and a failing terminal workflow outcome.

The shared `build` schema requires global serialization from freeze through
build/test/publication, including CLI runs and all source DAGs. One active run
per DAG or one pool slot per individual task does not reserve the gaps between
tasks. M05B uses a session advisory coordinator spanning the whole cycle, a
same-connection freeze, and the durable active-batch guard across task crashes;
contention should wait/defer without consuming the business failure budget.
Do not loosen the current active-batch guard to make concurrent schedules pass.
M07 makes collection independent across source/accounts: a source session lock
spans its cycle and durable collect precedes the global release barrier. Slot
waits/stage execution have separate actual-clock measurements; see
`09_M07_SCALE_MONITORING.md`. No task gets simulator controls,
fixtures, source-writer credentials or Docker socket access.

## Runtime quality versus fixture assertions

Current `website_s01_*` tests assume exactly one website order/three observations;
`ebay_s01` assumes one order/two observations and fixed amounts. These are valid
fixture assertions, not general continuous-processing rules. M05B separates
the validation modes and binds them to immutable batch configuration/artifacts.

Runtime checks always cover identity/uniqueness, relationships, source time/order,
money grain/currency, mapping/status limitations, valid parcel allocations and
raw lineage. S01 mode additionally runs the unchanged golden counts/timestamps.
Persist or otherwise bind the selected validation mode to the immutable batch
and its verified dbt invocation/artifacts; a retry cannot silently change mode.
Do not bypass all tests or alter approved fixture expectations to make scheduling
work. Finalize any needed operational fields/constraints before dependent DDL.

## Etsy and reporting integration

M06's implementation sequence, missing operational definitions and explicit
acceptance matrix are in [07_M06_READINESS.md](07_M06_READINESS.md). Implemented
commands and limits are in [the Etsy guide](../orchestration/ETSY.md); exact runtime
results, including the initial failed campaigns, are in STATUS.

Implemented commands, environment options and the acceptance runner are in
[the polling guide](../orchestration/POLLING.md). Scheduled DAGs start paused;
polling uses `orders_polling`, not the historical S01 `orders` checkpoint stream.

M06's receiver remains an always-on service outside a DAG: durable inbox/delivery
audit precedes acknowledgment. Bounded scheduled jobs drain pending work and run
receipt recovery scans even when notifications are absent. They use HTTP, durable
attempts, and the same serialized tested-release mechanism. The callback does not
run dbt or wait for a scheduled DAG before acknowledging stored notifications.

Maintenance must stop new intervals without stranding existing retries. The M06
runner temporarily sets `POLLING_DRAIN_MODE=true` (periodic `schedule=None`), waits
for serialized timetable refresh and leaves existing runs unpaused until terminal.
Only then does it pause and restore normal configuration. Timed-out FAILED DAGs
whose watcher was skipped can have their platform parent closed through guarded
abort; no attempt reset or fabricated success. Full campaign PASS is printed only
after safe cleanup. See `orchestration/ETSY.md` for drain-only recovery.

Publications are source-specific (`website_orders`, `ebay_orders`, `etsy_orders`),
so M07 must display a source-to-batch/time mapping, not invent a single global
batch label. Read that mapping and business datasets in one read-only repeatable
read transaction. Add restricted live health views for newer failed runs/work/
tests; the last successful `mart.source_health` alone cannot expose failures
after its publication. Label live-health read time separately. Acquisition, good
publication and browser refresh are three distinct events. Coverage remains
UNKNOWN unless continuity is actually proven. This plan does not change the
approved sales/state definitions or select a second dashboard tool.

## Evidence required before claiming automatic operation

- Preserve existing fixture, CLI and manual-DAG acceptance results.
- With real Airflow scheduler processes, observe at least two consecutive runs
  created by the enabled schedule, without manual `dags trigger`/test commands.
  Record DAG/run IDs, windows, raw HTTP/SQL audit, checkpoints and publication.
- Verify first-run configuration, empty windows, replay/dedupe, restart after
  durable progress, exhausted attempt budget after clear, and last-good-release
  preservation. CLI and DAG must agree for equivalent retained inputs.
- Exercise overlapping website/eBay releases in M05B and Etsy in M06; no shared
  candidates may be overwritten between freeze/test/publish. Verify source roles.
- M06 demonstrates scheduled inbox draining and a missed-notification recovery
  scan; M08A proves isolated cold setup, B demonstrates changing-source processing,
  C verifies lifecycle/recovery and D measures load/stability. M09 packages these
  verified results. Keep deterministic S01 counts separate.
- Publish tested startup, enable/pause/resume and controlled recovery instructions
  only when commands exist. Record all unrun checks in STATUS; a plan or green
  manually triggered run is not evidence of a working periodic schedule.

## Opt-in S02 local business-clock revision

The manual local workflow in `15_S02_LOCAL_WORKFLOW.md` adds a separate logical
business time, not an Airflow/OS clock change. `S02_LOCAL_PLAYBACK=true` is set only
by the explicit S02 overlay. Polling obtains replay/realtime source bounds from the
authenticated simulator clock endpoint over HTTP, persists them with campaign/
mode metadata in polling cycle settings, and reuses the same bounds on retry.
Legacy `clock_mode=current` remains the physical schema label; the opt-in logical
mode is explicitly recorded in `settings.logical_clock`, not falsely reported as
changing the scheduler clock. Observed timestamps, leases, retries and signatures
remain wall-clock UTC. Ordinary S01/current-clock operation is unchanged.
Real scheduled acceptance of the new logical path is a separate gate in STATUS.
Initial source materialization precedes polling enable: run the source-only
driver while DAGs are paused, verify due rows/notifications, then enable once.
The finite runner enforces this barrier rather than allowing an empty startup
watermark to skip subsequently inserted old planned timestamps. A prepared
dataset is not itself proof that Website source rows are already materialized.

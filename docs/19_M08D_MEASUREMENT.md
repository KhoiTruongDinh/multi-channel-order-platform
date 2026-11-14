# M08D bounded baseline measurement

Owner reviewed the observable normal/recovery demos on2026-11-06 and authorized
the next step. Implement the finite correctness/warm-history baseline FIRST.
This slice is not the full burst/soak/stress or production-capacity certification.
It uses the existing live stack, source interfaces and one shared workload JSON.
No warehouse/source DDL or business transformation changes are needed here.

## Next authorized slice: finite rate steps (2026-11-07)

Owner-approved next implementation2026-11-12: priorities1/2 are finalized in
[20_M08D_REUSE_COORDINATION.md](20_M08D_REUSE_COORDINATION.md). They supersede
the statement-only Etsy optimization below: cache pure normalization per scoped
bytes/code version and reschedule live coordinator waits without consuming a
worker. Full manifest/lineage/tests/publication and historical FAILs stay fixed.
Do not compare warm cache SELECT timings with uncached whole dbt/load timings.

### Etsy normalization reuse (2026-11-12)

Follow-up to the retained 900-order cadence failure: evaluate the unchanged
`build.etsy_canonical_json(parsed_payload)` once per eligible raw receipt using
a statement-local MATERIALIZED CTE. Reuse that exact order_json for hashing.
Preserve all raw columns, column order/types, source/account/resource/status and
manifest filters, exceptions, canonical fingerprints and downstream contracts.
No function changes, stable DDL, incremental cache, executor/lock/budget changes
or relaxed cadence gate. This is a bounded SQL experiment, not a load verdict.

Run `python tests/etsy_staging_probe.py --report runtime/etsy-staging-review.json`.
This creates only a uniquely named, labeled PostgreSQL16 container with private
tmpfs data, no network/ports/owner volumes, one CPU and512MiB memory. No host
Python database packages are required. The probe uses real production functions,
compares old/new complete row multisets plus independent payload/hash assertions,
checks invalid aliases/duplicate line IDs, and profiles10/100/300receipt reads
with four alternating old/new EXPLAIN samples. Cleanup removes only the verified
probe container. A SQL PASS still requires full dbt/release and same-envelope
cadence qualification before deployment can be called successful.

Actual deployment2026-11-12: first Etsy release has54passing nodes, staging54.920s.
Unchanged900 report `runtime/campaign-83fb057f5a0e48ed96a1d35043139e15/report.json`
FAILS both cadence1/1/1/0 (Website/eBay/inbox/recovery;2each required) and drain:
761/900final at deadline observation,139eBay pending. Independent later read
PASS900/3801lines/904observed versions,zero errors, but eBay published after the
deadline. Do not relabel the failed report. All78hashes match,58resource samples,
no ceiling breach; retained baseline is now6679orders/32319raw. Eight in-window
published batches each pass54nodes, Etsy staging70.747..140.600s in Etsy batches.
No controlled whole-load speedup/capacity claim. Stop escalation; review retained
raw parsing/full-build growth and executor occupancy before another rate run.
STATUS records exact commands, clocks, resource/stage evidence and unrun gates.

### Website JSON expansion experiment (2026-11-08)

Owner authorized the proposed profiling-first sequence. This slice changes ONLY
Website staging child-array expansion: group each child array once per raw/order,
then join to headers. Shipment-item membership retains EXISTS semantics via a
distinct raw/order/shipment relation; preserve child ordinality and duplicates.
Output columns, types, null/empty behavior for supported envelopes, source/account
scope and canonical fingerprint remain unchanged. No DDL, incremental storage,
model selection, parallel release, transaction/chunk, or budget changes.

Before deployment, compare the frozen pre-change SELECT in
tests/sql/website_staging_before.sql against the model using bidirectional
EXCEPT ALL over ALL staging columns, including fingerprint. Independent Python
payload/fingerprint checks cover S01, empty/missing children, repeated headers,
repeated acquisitions, duplicate/cross-order shipment IDs and source array order.
Use session-temp tables/functions only and rollback. Profile alternating old/new
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON), four samples each at1/10/100/300/600 synthetic
orders per raw; additionally compare at most200 retained Website acquisitions.
Shared stack activity can affect timings: these are SQL diagnostics, not capacity
or whole-dbt acceptance. Do not mutate shared build while scheduler is running.
Full dbt/release and unchanged900 qualification remain separate runtime gates.

Reproduce from repository root with Docker already running and an existing
Airflow project environment (no container restart or shared code replacement):

```powershell
python tests/website_staging_probe.py --container multi-channel-order-platform-airflow-1 --report runtime/website-staging-review.json
```

The runner sends the current model, frozen baseline, S01 inputs and canonical
macro through Python subprocess stdin (not PowerShell JSON serialization).
Only temporary SQL objects are written; they are rolled back on success/failure.
The transform role reads at most200 retained raw acquisitions for parity. The
report path must be new; existing evidence is never overwritten. Per-statement
timeout90s, lock timeout2s, outer subprocess timeout600s. Shared-stack contention
means these numbers are not an isolated-hardware benchmark. Missing/non-array
child behavior is checked separately; invalid non-arrays must still raise22023.

Actual2026-11-08: final temporary probe v2 PASS;200retained raw/2091observations
match on every output column. Four alternating samples at600orders/raw yield
old median9190.573ms versus new432.450ms (~21.25x for this SELECT only); all
new array Function Scan loops=1. Tiny1-order median1.1605ms versus1.1565ms.
Three invalid-array cases remain22023 for both variants. Initial v1 retained a
planner-driven item re-expansion and was refined, not presented as final SQL.
Full measurements/commands and explicit undeployed/full-build/900 gates are in
STATUS; no load or end-to-end improvement is certified by this diagnostic.

Deployment prerequisite discovered2026-11-08: the transform run was exposed with
FROZEN before finally-time annotation filled its Airflow owner. The campaign
orphan guard could therefore refuse a genuinely RUNNING owner during that gap.
Fix existing owner columns in the initial TRANSFORM INSERT, atomically with the
manifest; pass actual DAG/run context through both workflow freeze paths. No
guard bypass, retry/window relaxation, DDL or business transformation change.
Preserve the refused startup report (no data admitted); rerun only after focused
ownership regression and safe deployment. Do not abort the live batch merely
because the earlier guard observed incomplete metadata.

Actual retry2026-11-08 after deployment: report
runtime/campaign-262f579dff4943a1bc8b9ef0fb03a5cb/report.json FAILED the SAME
scheduled cadence gate1/1/1/1 versus2each. All900final versions observed within
751.029038s of source end; independent reconciliation PASS900/3801lines/
907observed versions,zero errors.78hashes match,63samples,no ceiling failure.
Ten published batches each pass54dbt nodes. Etsy staging81.541..109.353s in Etsy
batches and source/release waits up to235/177s remain measured review targets.
Do not turn the isolated Website SQL speedup into a whole-load PASS. Retained
warm history/phase differ from previous runs. Full evidence/unrun gates in STATUS.

### Configurable marketplace list pages

After the narrow drain fix, profile list overhead with configurable pagination.
Predeclare live list limits50 (eBay1..200, Etsy1..100), with base/S01 default1.
Persist page_size in immutable polling-cycle JSON settings (legacy absent=1)
and pass it explicitly to collectors; retries restore the prior limit. Direct
Etsy recovery also checks its retained list-request limits before cache reuse.
No DDL, source detail changes, HTTP concurrency, worker count, dbt selection,
time-window or acceptance-budget changes. Every physical response remains audited.
Keep page cardinality, duplicate/order, fixed-window and next-link checks.
Retain the existing eBay1000-order safety bound independently of page size.
Measure fewer list calls separately from unchanged per-order detail requests.
After focused HTTP/SQL and legacy regression, rerun the SAME900 envelope; no
capacity verdict from unit tests or request-count reductions alone.

Actual page50 qualification: 125 selected tests and17rollback HTTP/SQL checks
PASS. Same900 runtime ends FAILED at15:26:25UTC2026-11-07, scheduled successes
1/1/1/1 versus2 each. Final data reconciliation PASS900/3801lines/zero errors,
observed drain751.877s within900s. A real recovery collection used6list pages
for300receipts, with300detail audits still required. All78hashes match; no
mid-run code/gate edits. Remaining detail/SQL/build/queue costs need profiling;
different retained history and scheduler phase rule out causal whole-run A/B
claims. Full burst/soak and exact commit latency remain unverified.

### Narrow drain prerequisite after the 900 failure

Replace the arbitrary 100-claim loop in Etsy drain with a finite claim budget
equal to the number of work IDs selected at invocation entry (or the explicit
recovery/replay scope). Each successful work becomes nonclaimable as before;
new arrivals cannot extend the running invocation. Existing HTTP/work/stage
attempt limits, lease fencing, Retry-After, task timeout, unfinished-work error
and recovery checkpoint barrier remain unchanged. No stored procedures, new
fields/DDL, page-size changes, dbt edits or load-gate relaxation in this slice.

This is an invocation snapshot, NOT a new persisted collection manifest: an
inbox retry still selects outstanding work using the existing behavior. Do not
claim fixed membership across restarts or a complete backlog/cadence solution.
Prove >100 successful work, interrupted resume, no false success when blocked,
and unchanged error budgets before the SAME 900 envelope can be rerun. Previous
failed load reports remain failed regardless of these focused checks.

Actual unchanged 900 rerun after this fix: FAILED scheduled cadence (Website/
eBay/inbox/recovery2/1/1/1 versus2 each). Live inbox390 and recovery300 receipt
work complete within one collection each, max work attempt1; the 100 cutoff is
gone. Final-data reconciliation PASS900/3801lines/zero errors, observed drain
843.241s within900s. This verifies the narrow fix, not complete load acceptance.
Remaining HTTP/paging, queue and full-build costs require profiling; do not relax
the original gate or infer an A/B speedup on different retained histories.

### Cadence experiment: materialize repeated Website expansion once per batch

After the live recovery fix, the unchanged144 envelope still failed cadence.
Retained run artifacts show Website snapshot evidence, line history and header
queries repeatedly executing JSON expansion/canonicalization through two views.
Predeclare one physical-plan change: staging.stg_website_observations and
intermediate.int_website_versions become dbt table materializations in build.
Their SELECT SQL, column names/types, scope/fingerprint/dedup rules and all54
project nodes/tests remain unchanged. No incremental processing, model selection,
new source interface or stable-table DDL. Derived rows are rebuilt from the SAME
immutable frozen manifest while the existing global release barrier is held.
Extra build-schema storage is a measured tradeoff, not an assumed free speedup.

First run a controlled SQL parity/elapsed diagnostic using compiled SELECTs from
one retained PUBLISHED batch: temporary view graph versus temporary table graph,
same connection/manifest/mapping and full-row EXCEPT ALL in both directions for
Website header history, line history and snapshot evidence. Hold the release
barrier and drain/restore schedules; never publish or alter stable data in this
diagnostic. Then deploy the two-line dbt config change through normal idle startup,
run ALL models/tests and repeat SAME144 envelope with identical limits. Do not
alter source windows, two-success gate, worker count, locks or budgets. Stop
escalation on failure; a SQL speedup alone does not certify full cadence/capacity.

Observed checkpoint (2026-11-07): the parity diagnostic passed for all three
outputs; the unchanged 144/12-minute and 600/12-minute finite envelopes then
passed. The 900/10-minute step FAILS scheduled cadence (3/1/0/1 versus 2 each),
despite independent final-data reconciliation PASS and observed drain 730.423s.
Escalation stopped; collection/workflow profiling is the next prerequisite.
No runtime code or gate was changed between admissions. See STATUS for exact report paths,
latencies, resources and final verdict; these results do not certify soak or
exact source-commit-to-publication latency.

After the baseline review, implement/run Website-only24 orders in360 seconds,
then mixed72 orders in360 seconds (24 per source). Offered means configured
source eligibility, not committed or processed throughput. Uniform seeded
sampling can vary minute counts; freeze actual planned minute buckets before
admission. Keep other live schedules running: single-source means only this
campaign's offered orders, not an otherwise idle/exclusive machine. Both runs
retain warm history; their different retained sizes prohibit a strict controlled
before/after optimization claim. Run sequentially; do not admit the second if
the first fails. Single-source eBay/Etsy, burst and genuine soak remain later gates.

Finalize these additive report/config fields before implementation (no DDL):

| Field | Definition / constraint |
| --- | --- |
| campaign.load | Optional finite low-rate-step gate; requires measurement, forbids a campaign outage, active source intervals at least360 seconds; absent keeps baseline/review profiles compatible |
| load.min_scheduled_successes | Integer1..10, default2; each active source's live DAG(s) must have this many actual scheduled successes whose DAG run started between admission and configured source-window end |
| load.max_drain_seconds | Integer30..1800, default900; wall budget after configured source-window end, in addition to campaign timeout; never silently extended |
| source_plan.minute_buckets | Planned first order eligibility and version counts by source and UTC-minute offset from earliest configured source start; not actual commits |
| final_progress | Actual SQL observation clock, currently matching final orders, eligible-but-not-current count/oldest age and per-source counts; nullable current timestamps are missing, not successes |
| load_assessment | Fixed shifted configured window end; actual scheduled run IDs/state/start/end; first observed final/source-send drain clock and elapsed seconds; separate observed drain/cycle verdict; no exact commit clock |

All required live DAGs: Website website_polling; eBay ebay_polling; Etsy both
etsy_inbox and etsy_recovery. Count only scheduled runs, not manual CLI work or
historical successes. Runs may finish during bounded drain. Sampling confirms
observed backlog, not every transient backlog peak. First observed drain requires
all final current timestamps, no future source version/pending send and window
end reached. Late/reordered notification plans and service faults are not enabled
in these two rate profiles. Exact source commits/publication remain NOT_MEASURED.

Both profiles predeclare100-order/500-version/10MiB limits, Docker reported-memory
90%/2400MiB per container,512MiB DB growth,2048MiB minimum free disk,500 pending
sends,1200-second final observation budget,900-second observed drain budget,
1800-second post-admission timeout. Six minutes is a short low-rate step, NOT a
soak, sustained-capacity certification or production SLA. Correctness, resources,
final observed-delay and scheduled/drain gates must ALL pass. Missing cycles or
expired drain fails; retain evidence and do not clear/abort/reset to turn it green.
If the stack is stopped, normal guarded startup/resume/drain is allowed; orphan
release refusal still requires explicit operator direction, never automatic abort.
Campaign startup rechecks release ownership during drain as well as before
restart: scheduler recovery may make a retained RUNNING owner terminal. Refusal
is not load acceptance; inspect STATUS before retrying on a retained local stack.

### Owner-authorized escalation after recovery (2026-11-07)

Owner approved official abort of ONLY orphan batch
d0b60a58-f9fe-5b0c-8fc5-486f584195b7 after rechecking terminal/idle ownership and
explicitly requested more meaningful load. Run24 Website then72 mixed first;
only after PASS escalate sequentially to300 mixed orders/360s (100 per source,
0.833 offered orders/s), then900/600s (300 per source,1.5 offered orders/s).
These are finite rate steps, not a million-order or long-soak certification.
Stop escalation on failure/ceiling; no automatic reset or selective success.

Larger profiles predeclare max1000 orders/3000 source versions/10MiB generated
JSON and1000 unfinished planned sends (includes future sends, not only due retry
backlog). RAM/disk/DB-growth,1200s final-observation,900s drain and1800s campaign
timeout budgets stay unchanged. At900 orders, even a finite prepared timeline
can exceed the earlier500 planned-send ceiling; declare this count limit before
admission rather than relaxing a violated limit mid-run. Source interfaces,
fingerprints, business SQL, polling intervals and two-success DAG gate stay fixed.
Record retained history, resources, exact offered plans, observed published totals
and clocks separately; actual source commit/first publication remain unmeasured.

### Predeclared scheduler contention experiment if the low mixed gate fails

The2-worker LocalExecutor can queue a ready cycle while another worker waits for
the same-source/global release slot. Investigate this from actual task queued_dttm
and start_date, not a guessed queue clock. If the72/6min normal gate fails,
retain that FAILED result and stop the300/900 escalation. One scoped experiment
may then rerun the SAME72/6min seeds/baskets/cycle/delay/drain/resource limits with
live-only executor parallelism4; do not change business SQL or the failed verdict.

Configuration dictionary before implementation: LIVE_AIRFLOW_PARALLELISM is an
optional non-secret .env integer, supported values2 or4, default2. It overrides
only the live overlay's AIRFLOW__CORE__PARALLELISM; base/disposable settings remain
unchanged. Reject other values before schedule drain/startup. Keep per-DAG active
tasks1, per-source locks and the single global freeze/build/publish coordinator.
Four executor slots do NOT mean four concurrent dbt publications. Drain idle
before container recreation. Keep the same2CPU/4GB VM and existing RAM ceilings;
increased waiting-worker memory must be measured, never assumed safe.

Record frozen config/image/hardware/retained sizes for both attempts. Shared warm
history grows between them, so comparison is diagnostic, not strict controlled
capacity certification. Count actual scheduled cycle successes as before. Only
if that unchanged mixed envelope passes may300/900 resume; another failure stops
the experiment/escalation. No auto retry clearing, budget reset or source rewind.
Read-only queue measurements use cycle task start_date minus queued_dttm, joined
to actual scheduled DAG/run IDs in the fixed admission/source-start window;
never treat missing timestamps as zero queue time.

### One bounded exposure calibration, not a rewritten failed verdict

If the4-slot72/6min experiment still misses the fixed two-cycle gate, retain its
FAIL and stop that escalation. A shared serial4-DAG build round takes multiple
minutes even with no executor queue; a six-minute source window can be too short
to observe two rounds at every phase. Do not call a longer window a software
speedup or retroactively pass either short attempt.

Predeclare ONE longer qualification:144 mixed orders/720s (48/source), same
0.2 offered orders/s, seeds, baskets,2-success gate,1200s final-observation,
900s drain and existing RAM/disk/DB-growth ceilings. It doubles exposure and total
orders, not lowers offered pressure. If qualification passes, use600/720s
(200/source,0.8333/s) as the longer equivalent of the original300/360s offered
rate; then original900/600s (1.5/s). Keep300/360s as an unverified short diagnostic
template, not a passed envelope. All three longer/escalated profiles use
predeclared1000order/3000version/10MiB/1000planned-send caps and1800s timeout.
Do not keep lengthening windows or weakening criteria until green: if this
qualification or a subsequent step fails, stop and report the measured limit.
No new business/source schema or simulation mechanism is required.
The4-slot experiment did reduce executor queue but did not pass the full short
envelope. Revert local live parallelism to the default2 before this longer
qualification; do not retain an unproven overall performance improvement. The
longer profiles retain their identical gates/resource limits and frozen config.

## Measurement contract before implementation

### Runtime blocker discovered in the longer qualification

Fix continuation (2026-11-07): migration009 and the scan/cache protocol are
finalized in [the target dictionary](05_TARGET_SCHEMA.md#m08d-bounded-etsy-reconciliation-finalized-before-migration-009).
The collector invalidates count/order-inconsistent scans, preserves all HTTP
attempts and starts a bounded fresh scan on retry. RUNNING/VALIDATED cache and
legacy scan1 adoption preserve resume. Five attempts per URL across ALL scans
still apply; five scan identities is an additional ceiling, not another HTTP
budget. Partial pages no longer enqueue receipt work. Bootstrap/migrate/live-up
apply the additive migration; no SIM or business output schema change.
The real HTTP/SQL rollback probe tests fresh scans, cache resume and budget
fencing; the SAME144 scheduled envelope must pass before escalation. STATUS,
not this design description, records actual runtime outcomes.

Latest rerun: the live successor scan VALIDATED and144-order independent
reconciliation passed; the unchanged scheduled-cycle gate still FAILED (only one
recovery start in the fixed window). No600/900 admission. Remaining prerequisite
is measured cadence/build stabilization, not another exposure extension.009's
NULL-error presence constraint was hardened AFTER the frozen run and passed an
additional rollback SQL negative test; see STATUS for revision/evidence bounds.

The144-order qualification reproduced a mutable Etsy recovery page set:
HTTP200 offsets0/1/2 returned counts23/23/22 within one second. The collector
correctly refuses an inconsistent scan, but subsequent invocations reuse those
successful cached pages and repeat `changing recovery count; retry/reconcile
window`. Whole-envelope acceptance therefore cannot be inferred from all144
final orders being present via other successful work. See STATUS for the fixed
run/deadline and retained verdict. Do not blindly escalate or relax the count gate.

The follow-up design must distinguish a bounded reconciliation scan from replay
of an internally consistent successful page set, preserve every HTTP raw/attempt,
never reset the five-attempt budgets, avoid advancing checkpoints on a partial
scan, and preserve approved S01 resume/identity behavior. Disabling validation,
deleting audits, silently allocating unlimited HTTP attempts or synthesizing
missing snapshots are not fixes. This qualification's frozen code is not patched
mid-run. Larger profiles remain templates until the preceding complete gate passes.

Optional `campaign.measurement` enables a test-only host observer. Existing
profiles without it keep their review-only behavior. No simulator or DAG imports
the test oracle. All measurement artifacts stay in the ignored campaign report.

| Record | Definition / constraint |
| --- | --- |
| frozen | resolved config, host code hashes, Git HEAD, Docker RAM/CPU/version, service image/container identities, initial DB sizes and retained core/raw row counts; never environment/passwords |
| source_plan | finite orders, source versions, serialized generated bytes, channel mix and final per-order source facts; prepared before admission |
| samples | UTC start/end brackets, Docker per-container CPU/memory, scoped-stack memory sum, workspace/PG-volume free space, DB sizes/growth, source-send backlog |
| final_observations | one record per source/account/order: effective final source timestamp, first actual SQL observation of a matching current timestamp, observed delay seconds; missing observations remain censored |
| reconciliation | independent source-derived header states/currency/timestamps/money, exact current and observed-history line keys/quantities/prices/canonical mapping, raw evidence presence/source scope; missed source versions are NOT required history |
| stage_summary | actual stage/slot duration distributions, counts/outcomes from ops.execution_measurements since admission; whole-stack, not exclusive campaign attribution |
| verdicts | separate correctness, observed-delay budget and resource outcomes; exact commit-to-first-publication latency NOT_MEASURED; milestone_complete false |

The publisher replaces source snapshots on every release. Its current batch_id
is NOT a first-publication ledger. `first_observed_at` is an acquisition clock,
and existing published_at is recorded before transaction commit. None is silently
substituted for an exact source-commit-to-first-publication latency measurement.
This baseline reports **scheduled final source eligibility to first matching SQL
observation**, including worker/polling/build/observer delay. It is not exact
commit-to-publication p95. Website eligibility is planned time, not actual SQL
commit time. Exact latency requires a separately finalized durable clock/receipt
contract before any DDL; it remains a full-D gate, not a fabricated PASS.

## Predeclared baseline envelope

Example: `tools/s02_data/config/campaign_baseline.json`:12 orders, four per source,
three-minute source interval, at most100 orders/500 versions/10MiB source JSON,
30-minute post-admission timeout and20-minute final observed-delay budget.
Ceilings: scoped container memory sum90% of Docker RAM, any container2400MiB,
DB growth512MiB, pending source sends500, free workspace and PG-volume space2048MiB.
These are local safety/review budgets, not measured marketplace SLAs or capacity.
CPU is sampled but is not an automatic kill threshold: busy CPU alone is not
corruption. Memory is Docker CLI reported usage (cache-adjusted on Linux), not
complete VM/host memory accounting or an OOM-prevention guarantee.

Check finite order/version/byte limits before Docker/startup, resource ceilings
before preparation and again before admission. Once admitted, the source timeline
is immutable: ceiling breach stops the observer/new admission, preserves evidence
and restores any campaign-owned fault; it does NOT erase admitted events, kill
main services or secretly pause other campaigns. Remaining emission is bounded by
the prechecked finite plan. Missing/invalid resource telemetry refuses admission.

## Run and inspect

```powershell
python -m tools.s02_data campaign --config tools/s02_data/config/campaign_baseline.json --confirm-local
```

The existing campaign startup/drain path is retained. Generation/preparation is
recorded as preparation_and_admission_seconds and excluded from post-admission
observations. Read the printed
runtime/campaign-UUID/report.json, its measurement section, Airflow and the
existing dashboard. A baseline failure exits nonzero and retains evidence/data.
No timeout extension, reset, task clear or manual publication to make it pass.

Read-only preflight (no preparation/admission) and independent reread of a retained
campaign are also available:

```powershell
python -m test_support.m08d_measure --preflight-config tools/s02_data/config/campaign_baseline.json
python -m test_support.m08d_measure --report runtime/campaign-REPLACE_WITH_PRINTED_ID/report.json
```

The second command rechecks business correctness against retained source config;
it cannot recreate old resource samples or first-observation clocks. The report's
raw_window counts physical raw audits/received bytes using fetched_at where
present, otherwise acquired_at. Like stage_summary, this is whole-stack activity
since admission, not exclusive campaign traffic. Its received_bytes field sums
audit payload bytes: multiple raw resources may preserve the same HTTP response,
so it is NOT deduplicated wire traffic/network throughput. Memory/disk `_mb` limits use MiB;
Docker CPU percentages are per-container and can exceed100 on multiple CPUs.

### Find slow stages while it runs

In DBeaver, database `data_platform`, read the last30 minutes of existing telemetry:

```sql
SELECT source_system,stage,outcome,count(*) AS attempts,
       count(duration_ms) AS completed_duration_samples,
       round((percentile_cont(.95) WITHIN GROUP (ORDER BY duration_ms)/1000)::numeric,2) AS p95_seconds,
       round(max(extract(epoch FROM clock_timestamp()-started_at))
             FILTER (WHERE outcome='RUNNING')::numeric,2) AS oldest_running_seconds
FROM ops.execution_measurements
WHERE started_at >= clock_timestamp()-interval '30 minutes'
GROUP BY source_system,stage,outcome
ORDER BY source_system,stage,outcome;
```

`release_slot` measures shared publisher contention; `source_slot` measures
per-source contention; `collect`, `freeze`, `build_and_test`, `publish` are actual
workflow stages. In-flight rows have no completed duration and cannot be treated
as zero-duration successes. Airflow can additionally show executor queueing;
these stage timings alone do not include every scheduler/queue delay. The manual
30-minute query covers the whole stack, not just the admitted batch. Use the
report's fixed admission timestamp instead for the exact baseline window.

Next gates after this slice: single-source sustained steps, mixed-source rate
steps, bounded burst/drain, a predeclared genuine soak, exact latency/commit
measurement design, and evidence-driven same-workload fixes plus regressions.
Record actual outcomes in STATUS; baseline PASS alone never completes M08D.

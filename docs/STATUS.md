# Actual project status

Updated: 2026-11-18 (Asia/Bangkok).

## Current checkpoint

### Owner-authorized feature commit packaging (2026-11-18)

Owner explicitly requested a README review/update followed by a local commit.
Scope: opt-in marketplace page reuse/bounded workers, migration014 and its
dictionary, required staging/cache/evidence adapters, migration/config wiring,
focused tests/runbooks and the README verification summary. Updated README with
the feature and the recorded collect/dbt correctness evidence, without throughput
or deployed-path claims. Existing screenshots/project introduction preserved.

Reused recorded collect PASS and dbt60nodes per branch/21comparisons only for
unchanged code. No new Docker service, DB/HTTP/dbt/full-flow test, campaign or load
run for packaging. Python AST17files/README20local links and diff --check PASS;
explicit staged-file review PASS:41feature files only. Initial PowerShell quoting of the AST file
list failed before checking code; corrected argv invocation PASS. No credentials, runtime reports,
artifacts, local configs, unrelated CI/campaign/measurement/layout/AGENTS changes
or HANDOFF_SHA256SUMS.txt in the commit scope. Git author configured; no push.
Compiled delta/runtime/release/bootstrap qualification remains the next separately
authorized task, not waived by this feature checkpoint. See Git history for the
resulting commit ID; older no-commit entries below describe prior task history.

### Partial-commit readiness review (2026-11-18)

Owner asked whether a portion can be committed for the CV/portfolio handoff.
Read-only review only; no new integration, dbt build, scheduler or campaign.
Retained collect report ce912fab58fc PASS/cleanup PASS and ordinary dbt report
157f78dfe5b2 PASS/21comparisons. Current source hash673cbce2ca50fe5105f541df2184a799ba138e188701d1b6c4f90dd85b5c4c5c
still matches that dbt evidence. diff --check PASS, index empty, Git author
configured. .env/runtime are not tracked; both README dashboard assets exist.

Suitable feature checkpoint: opt-in marketplace page reuse + bounded detail
workers, migration014/dictionary, necessary dbt input/cache/evidence adapters,
configuration/migration wiring and their focused tests/runbooks. Keep these
dependencies together, not a dbt-only commit that omits the new relations.
Suggested title: `feat(ingestion): add verified marketplace page reuse and bounded workers`.
"Verified" here means the documented collect/ordinary-dbt fixture scope only;
compiled delta/release/bootstrap/main activation and load remain pending.

Exclude unrelated dirty CI/campaign/measurement/layout/AGENTS changes, local
workload configs and HANDOFF_SHA256SUMS.txt from this proposed feature checkpoint.
README/dashboard portfolio packaging already exists in committed history; CV
claims need not wait for further M08D tuning. A local commit alone does not update
the remote GitHub page. No stage/commit/push performed for this review question;
await explicit instruction to create the proposed commit. No source code changed.

### M08D new acquired-input dbt parity (2026-11-18)

Owner authorized the next dbt check and requested the temporary Vietnamese review
doc be updated. Ran dbt-only legacy/page-input parity, NOT another collection,
publish, scheduler/restart, deployment or load/campaign test. Main containers were
all stopped before and after; .env, owner credentials/volumes/plans untouched.
Branch main/HEAD0fc82bb; no stage/commit/push. Existing dirty changes preserved.

Added explicit `tests/dbt_acquisition_probe.py`: real PostgreSQL16.15 tmpfs test
container (512MiB/1CPU, no external network/ports) plus project-venv dbt client
(768MiB/1CPU) sharing only its network namespace. Existing image, read-only code/
fixture/profile mounts; generated dbt artifacts in client /tmp. Real platform
prerequisites001..011 and014; no delta012/013. Two test-owned immutable manifests
select equivalent singleton or page+accepted-element raw. No production freeze
workflow is invoked; this fixture isolates SQL representation parity only.

Exact host command (each attempt below):

```powershell
python tests/dbt_acquisition_probe.py
```

Final `runtime/dbt-acquisition-157f78dfe5b2.json`: PASS; both cleanup entries PASS.
Source hash673cbce2ca50fe5105f541df2184a799ba138e188701d1b6c4f90dd85b5c4c5c.
Report retains exact Docker/dbt command arguments and each node status. dbt uses
`build --project-dir /review/transformations --profiles-dir /review/infra/dbt`
with branch-specific /tmp target/log paths, mapping s01-v1, transformation
acquisition-dbt-probe, release_source etsy_sim, validation_mode runtime and the
actual batch UUID. This is the ordinary complete runtime dbt graph, not a new
compiled delta plan or the fixed-S01 full acceptance suite.

- Legacy60nodes and page60nodes all success/pass, zero failing/skipped nodes;
  counts include models/tests/hooks, not60models. No business SQL changes needed.
-21exact multiset comparisons PASS: all7business outputs x3sources, excluding
  only batch_id/published_batch_id lineage. Includes history/current, lines,
  source-created daily order/product activity and independent status/money fields.
  Each marketplace has2current orders/3snapshots from4observations; Website1/1.
-4fingerprint checks (both marketplaces/both representations) match the independent
  fixture utility. Source-version identity unchanged, repeated reads preserve
  observations without duplicate logical snapshots; unaccepted entities excluded.
-6evidence checks: actual manifest membership/raw byte hash/resource role; Website
  retains WEBSITE_RELATIONAL_SNAPSHOT. eBay legacy8/page11evidence rows reflect
  real differing page/detail/shipping shapes. Evidence UUID/role/count equality
  between transports is intentionally NOT required. No fabricated detail records.
- Page input covers multi-order envelopes, actual cancellation detail fallback,
  partial shipping collection + actual fulfillment detail, Etsy missing-field
  receipt fallback, a subsequent source version, duplicate pages and unaccepted
  page entities. Etsy element cache0->2rows; duplicate page shares content entry.
  Stable core.orders_current remains empty: no publication occurred.

Earlier failed probe attempts retained, not labelled dbt business failures:

- `dbt-acquisition-5b2e20f0957e.json`: fixture SUCCEEDED run omitted finished_at;
  actual schema rejected it before dbt. Fixed fixture, not the constraint.
- `dbt-acquisition-7d89d38a218c.json`: legacy build passed, evidence helper wrongly
  expected resource-uppercase role for Website. Preserved its established role.
  Cleanup helper also misclassified lowercase 'no such object' after --rm client
  deletion; corrected recognition, no owner target involved.
- `dbt-acquisition-5182e546fff1.json`: pg_isready saw socket-only init server;
  subsequent psql raced its shutdown. Now waits for final TCP readiness.
- Final fresh attempt reran both representations successfully. Subsequent host
  stdout compaction is presentation-only/AST-checked, not another dbt invocation.

Updated docs/TAM_THOI_M08_GIAI_TRINH_VI.md with scope, diagram, cases, command,
expected fields, failures, actual PASS and boundaries. AST/diff checks PASS;
index empty. Test containers/tmpfs data removed (test data not recoverable);
no owner data deleted. Final docker ps empty, matching initial running state.

Not run: collector/HTTP integration rerun, invalid-money/negative-page extension,
compiled delta route/runtime parity, release/bootstrap, scheduler/crash/rate-budget
matrix, main activation, unchanged900, performance or campaigns. The existing
collect-only DB proof remains separately scoped. This closes ordinary dbt input
parity for this fixture; not full M08D or a live release. Next needs explicit
authorization for compiled-plan/release/bootstrap qualification before enabling
page-reuse on main; do not bypass guards or auto-run broader gates.

### M08D collect-only PostgreSQL qualification (2026-11-14)

Owner explicitly authorized only the new collect path on a test DB. Main
containers were all stopped at preflight and were not started/reconfigured.
No .env, main credentials, retained volumes, source data or published plans used.
HEAD remains0fc82bb; all task changes unstaged, no commit/push.

Added `tests/acquisition_db_probe.py`: stdlib host orchestrator starts a uniquely
labelled, no-network/no-port PostgreSQL16.15 container with512MiB/1CPU and tmpfs
PGDATA. A512MiB/1CPU client uses the existing Airflow image's project Python,
read-only ingestion/tests mounts and the test DB's network namespace. Actual
collector CLI subprocesses connect as platform_ingest and call a controlled
loopback HTTP server. No Airflow scheduler, Compose, production SIM/backing DB,
dbt models or business oracle. Real platform migrations001..011 and014 applied;
014 applied a second time successfully. Delta012/013 are not collect prerequisites
and were not run. Exact Docker commands and output are retained in each report.

Actual command, run three times during development:

```powershell
python tests/acquisition_db_probe.py
```

- `runtime/collect-db-67076dc7c2e5.json`: PASS,2tests/16.989s, cleanup PASS.
- `runtime/collect-db-3279ed11cd61.json`: FAILED,3tests/17.586s; two source tests
  passed but JSON-null options were incorrectly accepted by migration014's CHECK.
  PostgreSQL CHECK accepts UNKNOWN. Finalized the non-null dictionary in05, then
  fixed the new migration predicate to require `IS TRUE`. No applied main
  migration/data changed. Stale-token fencing had passed before that assertion.
- `runtime/collect-db-ce912fab58fc.json`: final PASS,3tests/9.730s, cleanup PASS.
  Expected SQL failures assert SQLSTATE23514/P0001/42501, not just any DB error.
  These durations describe the small test suite, NOT throughput or an SLA result.

Final verified scope:

- eBay four orders/two pages: two accepted page references, two actual order-detail
  responses (cancellation and missing fields), four successful work items and
  required shipping requests. Two shipping requests rendezvous concurrently;
  parent succeeds only after workers finish. Successful collection reentry adds
  no raw/HTTP. A403 on a new collection retains audit/FAILED state and leaves the
  prior successful checkpoint unchanged. Persisted raw byte hashes match bytes.
- Etsy four receipts/two pages: two accepted page elements, two actual fallback
  receipt fetches with distinct lease tokens and overlapping HTTP requests.
  Successful reentry adds no HTTP. A403 leaves the preceding checkpoint unchanged
  and retains its HTTP attempt. Array references resolve through real raw, HTTP
  attempt and validated scan records; wrong-index/identity/scan inserts rejected.
- Immutable options/elements and terminal eBay scans reject rewrites; report role
  cannot read element evidence; transform can INSERT element cache, ingest cannot.
  JSON-null mode/workers/page_size and invalid bounds rejected. With an actual
  claimed Etsy work item, a stale-token response is audited once, creates no
  eligible receipt and cannot change the real owner's LEASED work state.

The probe removes only its exact fresh labelled client/DB containers and their
disposable tmpfs data (not recoverable; no owner data removed). Main was not
started, stopped or reset. Added the repeatable command/scope to ACQUISITION.md.
AST parse and `git -c core.safecrlf=false diff --check` PASS; index remains empty.

Not run: full dbt/new-input semantic parity, production-SIM integration,
crash/restart/lease-expiry races, persisted multi-cycle cooldown/attempt-exhaustion
fault matrix, scheduler gates, release/bootstrap/main activation, campaigns,
unchanged900, performance or load. Earlier mock/loopback evidence remains scoped
as recorded below. This closes this requested collect-only DB slice, not full
M08D or permission to activate the new acquired-envelope graph. Next: explicit
new-input dbt parity and release-plan qualification before any main activation;
ask before broader gates, do not bypass existing guards.

### M08D collect page reuse: code and focused checks (2026-11-14)

Owner requested the agreed acquisition enhancement, not another full-flow test.
Implemented opt-in page-reuse mode with defaults legacy/1; main services, .env,
data, mappings and verified deployed plans were NOT changed. No stage/commit/push.
Existing unrelated dirty CI/campaign/measurement/layout/config files preserved.

Final dictionary in05 precedes014_acquisition_elements.sql: immutable collection
options, eBay bounded scans and append-only enrichment restart markers, actual
raw+entity+array-index eligibility references, and separate versioned Etsy element
cache (source/account/receipt/element hash/normalization version). Guard references
against the actual successful response and validated scan; preserve parent raw
bytes/hash and source fingerprints. New indexes support real cooldown lookups.
Migration014 is wired into fresh/ordinary/guarded migration entry points but was
NOT executed here; SQL trigger/grant/runtime behavior is not yet verified.

eBay: finish sequential discovery before enrichment; reuse complete NONE_REQUESTED
Orders, retain authoritative cancellation/missing-field detail and shipping
requests. Complete shipping collections skip redundant fulfillment detail reads;
partial collections require actual consistent detail. Two-worker bounded pool,
separate DB/client per worker, parent account fence, durable UUID/scan/work and
five HTTP attempts per URL spanning retries/scans. Malformed200 bodies cannot
poison success cache; cached requests match scan/parent metadata. Enrichment
version drift appends restart evidence and permits the next bounded scan instead
of fabricating a combined order. Parent joins workers before checkpoint.
eBay SIM adds orderIds1..50/query precedence/list cancellation gap; request-state
and fault counters are reserved under lock, HTTP/DB reads/delays/socket writes
occur outside that lock. No Etsy SIM or Website extraction changes.

Etsy: validated complete recovery elements are eligible without redundant receipt
GET/work/HTTP-success records. Incomplete elements retain normal leased receipt
GET fallback. Inbox/replay still fetch receipts, with up to2 independently
connected/token-fenced workers. Retain unresolved-work checks, attempts, source
scope and completion barrier. Shared429/503 cooldown checks honor the longest
still-active recorded delay instead of letting a newer shorter response cancel it.
Already in-flight HTTP cannot be revoked. Website remains set-based/read-only.

Necessary input-only dbt changes: accepted page routes, source-private staging,
Etsy element cache/evidence and eBay raw+order shipping-parent joins. Legacy
single-order rows lacking redundant order_id metadata remain readable; no such
fallback for multi-order pages. Business marts, observed-version fingerprints
and atomic publication semantics are unchanged by design, not newly full-parity
certified. Adjusted legacy Etsy probe renderer/empty-element setup for compatibility;
did NOT run that database/profile probe. Opt-in options persist per polling cycle;
old missing options/retries remain legacy/1. Current compiled source hash:
673cbce2ca50fe5105f541df2184a799ba138e188701d1b6c4f90dd85b5c4c5c.
Older dbt/runtime evidence does not qualify this acquired-envelope change.

Checks actually run:

- Host `python -m unittest -q tests.test_etsy_drain tests.test_etsy_http
  tests.test_dbt_sql_style` failed importing the first two modules because host
  Python lacks psycopg. No DB was contacted. Used the existing project image
  instead of installing host packages or rebuilding/restarting main services.
- The following exact isolated unit invocation exited0:44tests PASS/5.304s.
  This includes mock-DB control flow, real loopback SIM requests, Jinja rendering
  and style checks, NOT warehouse integration or a pipeline latency measurement.

```powershell
$collectRoot=(Get-Location).Path
$unitMounts=@()
foreach ($part in @('ingestion','simulator','orchestration','transformation','transformations','tests','fixtures/s01')) {
    $unitMounts+=@('--mount',"type=bind,source=$collectRoot/$part,target=/review/$part,readonly")
}
docker run --rm --network none --read-only --memory 512m --cpus 1 --tmpfs /tmp -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/review -e PROJECT_ROOT=/review --workdir /review @unitMounts --entrypoint /opt/airflow/project-venv/bin/python multi-channel-order-platform-airflow -m unittest -q tests.test_acquisition_reuse tests.test_ebay_reuse_sim tests.test_acquisition_sql tests.test_etsy_drain tests.test_etsy_http tests.test_dbt_sql_style
```

- Added cycle-retry policy tests, then same isolated image/flags with
  `-m unittest -q tests.test_acquisition_reuse.CyclePolicyTests`:2PASS/0.492s.
  That invocation mounted only ingestion/orchestration/transformation/
  transformations/tests. Saved legacy and worker counts override changed env.
- After cache/lookup hardening and updating the legacy probe renderer, same
  isolated command/mounts as44test run, replacing module list with
  `tests.test_acquisition_reuse.EbayReuseTests tests.test_acquisition_sql`:
  17PASS/2.390s. Includes malformed cached200 response, scoped cached pages,
  grouped membership, enrichment conflicts and5offline SQL/render checks.
- Changed Python files compileall PASS; `git -c core.safecrlf=false diff --check`
  PASS; inspected actual diff, no staged files. The final worker connect/SQL-lock
  timeout settings were statically checked, not fault-injected against PostgreSQL.

Not run: migration014/trigger/grant execution, live PostgreSQL lease/cooldown/crash
races, new-mode full dbt/input parity, S01 verification suite, new image deployment,
bootstrap, scheduler/restart, unchanged900, performance/burst/soak or campaigns.
No claim of throughput/SLA improvement or full M08D PASS. These require a separate
explicit owner request; do not auto-run broader gates or bypass plan validation.
Next: owner code review, then authorize input/database qualification and new
verified release/bootstrap before enabling page-reuse on main. Operational/code
map and supported settings: ingestion/ACQUISITION.md; design22 updated accordingly.

### Owner testing-workflow revision (2026-11-14)

Default to small, change-focused checks. Full-flow testing requires an explicit
owner request for the current task; fixing, continuing, deployment or committing
does not automatically authorize full regression, scheduler/restart gates, load
or campaigns. If broader testing is a mandatory gate, report it before running;
do not bypass the gate or claim unrun coverage. Persisted in AGENTS.md. This
documentation-only revision launches no tests and changes no running service.

### M08D dbt scope closed from retained evidence (2026-11-14)

Owner narrowed closure to dbt correctness only: do not rerun tests, performance
checks or campaigns. Read existing reports only; no new test was launched for
this confirmation. The committed dbt checkpoint is0fc82bb.

runtime/delta-main-rollout-20261114-01.json records PUBLISHED bootstraps for
internal_web, ebay_sim and etsy_sim. For EACH source: full_dbt_oracle PASS,
60 nodes success/pass (zero non-passing nodes), all8 output comparisons PASS,
preserved_observed_source_versions=true. Migration013 was already verified in
the preceding deployment. This is sufficient to close the requested dbt scope.
Fresh strict scheduler/restart/mapping prerequisite report also PASS:
runtime/delta-startup-mapping-20261114-01.json.

At the history read, the deployment report was RUNNING/scheduled-warm-observation,
with no error; activation had passed and the existing process was observing native
schedules. Do not equate this unfinished observation with a dbt failure or claim
the entire deployment/M08D/load/ten-second target is certified. No new campaign
or performance measurement is authorized by this closure. Leave services alone.

Additional UI-only history: first AppTest invocation was rejected by PowerShell
stdin syntax, the next discovered0tests (not PASS), then4tests ran with one stale
title expectation failure. Updated that expectation to the approved source-created
heading, not the business query. Its rerun was interrupted/unconfirmed; do not
claim UI AppTest PASS. This is separate from the completed dbt oracles above.
STATUS and the one-line layout-test correction remain unstaged; no new commit/push.

### M08D retained daily-scope rollout in progress (2026-11-14)

Owner authorized step1 only: deploy the committed dbt revision on retained main,
without collection enhancements, load escalation or a data reset. HEAD0fc82bb.
Preflight: all main services initially stopped; Docker memory4109369344bytes.
Started only main PostgreSQL, then verified no queued/running DAG runs, active
FROZEN/BUILDING/TESTED batches or nonterminal source owners. Seven pause flags:
website_polling/ebay_polling/etsy_inbox/etsy_recovery unpaused, three replay/manual
DAGs paused. Retained baseline Web/eBay/Etsy current2919/2723/2837,
history3195/2736/2869, raw629/16826/24517. No abort required.

Created an owned maintenance drain `dbt-rollout-20261114-step1` before starting
the existing Airflow container, preventing new intervals during prequalification.
Airflow became healthy. Local ignored .env release changed from delta-20261113-v1
to delta-20261114-v2; no credential changed. Ran21offline SQL/plan/deploy/report
clock tests PASS. Started fresh strict scheduler/restart/mapping gate:
`python tests/delta_scheduler_probe.py --allow-owner-idle-stop --mapping-check
--report runtime/delta-startup-mapping-20261114-01.json`.
Scope identity26bc6795cc70 PASS: three native cycle tasks SUCCESS/try2, two
scheduled successes after restart, preserved113source snapshots/234raw in mapping
transition and full60-node dbt/all8-output parity. Main exact container/health,
seven pause flags and owned drain restored; disposable resources cleaned up.
From fixtures/s01, verify.py PASS and test_tools.py10PASS. Compose config--quiet
and build airflow/report PASS. Restarted existing live SIM/receiver/source worker/
observer and rebuilt report, all healthy; no new generated campaign.

After verifying its exact content, removed only this task's maintenance signal
to hand over to the guarded deployment's drain. Command started:
`python -m tools.s02_data.delta_deploy --startup-report
runtime/delta-startup-mapping-20261114-01.json --report
runtime/delta-main-rollout-20261114-01.json --confirm-local`.
Report initially RUNNING/draining-main. Guarded012/013 applied; catalog confirms
013 stamp and both required SELECT grants. All three retained-main cold bootstraps
PUBLISHED after full60-node dbt PASS, exact8-output parity and preserved observed
source versions: Web4295987c-da1e-4b35-a774-16dec4ed0e69 (46.162s),
eBay4e421e94-1136-4ac6-8749-a526adb5d62e (73.762s),
Etsy36d08995-2e6c-4214-a615-675f25fef4b3 (256.692s). Cold times are not warm SLA.
One read-only diagnostic mistakenly selected source_system from transform_batches
(column absent); corrected to batch_id/status, with no data mutation. Another
diagnostic read a disposable container just after its normal cleanup and reported
No such container; neither was an acceptance gate failure.

Turn interruption occurred while the deployment continued in background.
Read-only recovery confirmed the same retained process/report, all three batches
published and no active batch; no command/bootstrap was duplicated. Deployment
now activating verified plans; main Airflow recreated and health starting, drain
still present. Scheduled-success and dashboard-read gates remain pending.
No commit/push.

### M08D owner-authorized dbt checkpoint commit (2026-11-14)

Owner requested a local dbt checkpoint commit before continuing other work.
Scope: authored models/macros/tests, canonical cache, compiled delta execution,
scope-aware publication, required migrations/coordinator/deployment integration,
report clock labels and supporting regression/runbook files. Collection tuning,
local generator profiles, CI and load/campaign measurement changes are excluded.
No remote push, service start, database mutation or release activation in this task.

Rechecked `python -m unittest -q tests.test_report_clocks tests.test_dbt_sql_style
tests.test_delta_plan tests.test_delta_deploy`: 21 tests PASS. Also rechecked
`python -m unittest -q tests.test_airflow_local tests.test_s02_live`: 40 tests PASS.
From fixtures/s01, `python verify.py` PASS and `python -m unittest -q test_tools.py`:
10 tests PASS. `git -c core.safecrlf=false diff --check` PASS. Git identity is set.
Current `transformation.delta_plan.source_hash()` remains
67bc2c2d3cd979dd164a22a3ead7e6fe662533c35a16a123913f2947bd3aad23,
the source revision recorded for the prior disposable runtime PASS below.
That runtime suite was not rerun during this commit-only task. Offline mocks do
not replace its PostgreSQL/dbt evidence or scheduled rollout gates.

This is a verified dbt checkpoint, not complete M08D/SLA certification. Next:
explicitly qualify/deploy new compiled plans with migration013 and bootstrap
before enabling main delta, then continue collection enhancements and unchanged
900/burst/soak measurements. Main's old compiled plans must not bypass hash guards.
Unrelated working-tree files are retained outside the checkpoint commit.

### M08D bounded daily marts/report clocks; private regression PASS (2026-11-14)

Owner clarified clocks belong to each report, not one date choice for all metrics.
Implemented source-created UTC cohort maintenance for existing order/product
daily marts, actual pipeline-attempt headings for monitoring and explicit cohort/
latest-state/non-revenue captions. No invented receipt/new-order throughput and
no rewrite of S01 business/source dates. Review24_ACTIVITY_TIME_REVIEW.md now
supersedes its earlier pending global-clock question.

Dictionary finalized in05 before dependent code: two source-private dbt helpers
per source, candidate_activity_scope(date/source/account/batch) and
candidate_daily_orders(scoped order/created timestamp/currency/amount). Scope
includes old current dates AND new candidate dates for affected orders; bootstrap
also covers retained mart dates. Models aggregate only touched days, with product
line membership restricted by scoped order IDs. Delta publisher requires tested
scope, rejects out-of-scope candidates and reconciles deletes ONLY within scope;
untouched days/lineage remain, including when a touched old bucket becomes empty.
Status-current remains source-wide. Migration013 only grants platform_transform
SELECT on the two daily marts for bootstrap scope; no stable output schema change.

Staging remains materialized with existing canonical/version dedup semantics.
Added config-validation, prepare/drop/finish hook timers and per-model CTAS vs
ANALYZE times to delta_results. Wrapper/commit and individual JSON operation costs
remain partly unitemized. No unverified JSON-cache or parallel-transaction rewrite.
Normal dbt threads2 differs from the sequential compiled live runner; documented.

New tests/delta_daily_cases.py covers old/new days, changed currency, empty former
day, late old-day data, duplicate replay, empty tick and untouched day/value/lineage.
Extended existing staging probe with optional bounded sizes, invoked by private
runtime harness for multiset/fingerprint/invalid-array parity. New offline report
clock tests; style+plan+clock13tests PASS. compileall on changed Python PASS.

First private command `python tests/delta_runtime_probe.py --docker --report
runtime/daily-scope-20261114-01.json` failed at crash-test mock: new _merge_mart
batch/scope keyword arguments were not forwarded by its armed wrapper. Production
flow had reached the earlier gates; no final PASS/report produced. Updated the
test wrapper to forward keyword args without removing the kill/rollback barrier.
Rerun `python tests/delta_runtime_probe.py --docker --report
runtime/daily-scope-20261114-02.json` exit0/PASS on disposable tmpfs PostgreSQL,
not main. Three graphs now13models each; full dbt oracle60nodes PASS and all8
core/mart business outputs match delta (batch lineage excluded by established
oracle). Mapping-transition cold bootstrap also preserved113snapshots/234raw,
new mapping/plan and unchanged source identities, with full-dbt parity.

New daily regression PASS: old/new scope dates, emptied former day removed,
currency change, untouched dates retain exact values AND publication lineage,
empty tick causes no daily rewrite, duplicate replay does not inflate counts,
late old-date order updates that day rather than CURRENT_DATE. Existing real
process kill/rollback/concurrent-source and HTTP1/10/100 source probes also PASS.

Website staging multiset/fingerprint PASS on S01, duplicate/cross-linked/NULL
children, missing children, empty orders, repeated acquisitions and Unicode.
Retained-input case131rows/23raw; three malformed-array cases retain SQLSTATE22023
in old and current SQL. Bounded SELECT-profile median old/current ms:1order
1.075/1.164;10orders8.910/6.575;100orders242.657/60.966. Baseline is the historical
correlated SQL, not the previous turn's already optimized staging. These timings
are not evidence that this slice improved staging latency, and not a900/SLA claim.
New CTAS/ANALYZE fields are present in node evidence; hook phases remain in actual
delta_results. The existing harness exports only selected node timings, not all
hook phase values; do not claim a complete production subphase attribution.

Updated guarded delta_deploy to apply013 after012 before compile/bootstrap;
documented the prerequisite. No main migration was applied. Current source hash:
67bc2c2d3cd979dd164a22a3ead7e6fe662533c35a16a123913f2947bd3aad23.
Offline command `python -m unittest -q tests.test_report_clocks
tests.test_dbt_sql_style tests.test_delta_plan tests.test_delta_deploy`:21PASS.
From fixtures/s01 verify.py PASS and test_tools.py10PASS. Changed Python compileall
PASS. `git -c core.safecrlf=false diff --check` PASS; inspected task diff and new
file references. Index remains empty (`git diff --cached --name-only`).
Cleanup verified: no delta-runtime labeled containers/networks and no main
containers running. Only disposable tmpfs test data was removed; owner volumes/
data unchanged. Runtime report is ignored local evidence, not committed fixture.

No main start/release/bootstrap, real scheduled rollout, full M07 Streamlit UI
integration or unchanged900/burst/soak run for this slice. Existing plans must be
explicitly recompiled/rebootstrapped before live activation. Changes unstaged;
no stage/commit/push. Main/HEAD af82381.

### M08D authored dbt SQL cleanup; private regression PASS (2026-11-14)

Owner requested explicit projections/counts/joins/grouped deduplication plus
index/filter/CTE review. Implemented in repo-authored models/macros/tests:
no SELECT/qualified wildcard or COUNT(*); plain DISTINCT and aggregate DISTINCT
rewritten at the same grouping grain, preserving SQL NULL exclusion where needed.
IS DISTINCT FROM remains a NULL-safe comparison. Explicit INNER JOIN replaces
implicit inner joins; LEFT/CROSS LATERAL remain semantically unchanged. Removed
two trivial Etsy test CTE wrappers, retained justified MATERIALIZED JSON reuse.
Staging no longer forwards unused raw byte/HTTP metadata columns; raw acquisition
storage/audit unchanged. effective_current takes consumer-selected columns on
both retained/candidate branches. Frozen-input/source/affected-order filters and
required retained-current aggregation are preserved, not replaced by lossy LIMITs.

Declared DDL index review and PostgreSQL EXISTS/CTE caveats documented in
transformations/SQL_STYLE.md and STAGING, plan/index/Vietnamese notes synchronized.
No speculative DDL/index, collector/SIM, business definition or live deployment
change. Main stack remains stopped. New model/macros/source/cache hashes require
fresh compile/parity/bootstrap; do NOT reuse or patch existing deployed plan hashes.

New tests/test_dbt_sql_style.py checks authored projection/count/join/dedup rules
and explicit effective_current projections. `python -m unittest -v
tests.test_dbt_sql_style tests.test_delta_plan` from repo root:11tests PASS.
Initial invocation from fixtures/s01 failed module discovery; rerun from root.
First style run exposed one remaining Etsy wildcard wrapper and a false positive
for Jinja's join filter; wrappers removed and scanner now ignores Jinja blocks
when checking JOIN spelling. These failures were corrected, not runtime success.
From fixtures/s01: `python verify.py` PASS; `python -m unittest -v test_tools.py`
10tests PASS (offline fixtures, not database acceptance).

Pre-edit SQL snapshot retained under ignored runtime/sql-style-before/transformations
for51authored files, including existing user edits; unrelated dirty work preserved.
First `python tests/delta_runtime_probe.py --docker --report
runtime/sql-style-delta-20261114.json` refused a source hash change while edits were
still in progress; no PASS/report was produced and its labeled tmpfs scope cleaned.
Retry with final stable SQL: `python tests/delta_runtime_probe.py --docker --report
runtime/sql-style-delta-20261114-final.json` exit0/PASS on isolated PostgreSQL16
and existing local worker image; no main PostgreSQL/Airflow start or owner volumes.
Three source graphs11models each (Web14/eBay3/Etsy2 applicable tests), real collector
HTTP/read-only Website waves1/10/100 per source, duplicate/empty/late data, stale-owner
fencing, real process kill/concurrent-source publication and rollback checks PASS.
Full dbt oracle54nodes PASS; all8core/mart business outputs match compiled delta
(batch lineage intentionally excluded by the established harness). This is NOT a
standalone complete S01 golden DB suite or actual Airflow scheduled rollout.
Existing harness also captured a bounded disposable eBay staging SELECT profile;
not an installed-main join/index or900 execution-plan certification.

Build/test seconds in isolated100-order HTTP waves: Web0.733/eBay1.197/Etsy0.898.
These are small private regression samples on fresh retained test history, NOT
comparable evidence of speedup against the prior main900 run or MAX<=10s PASS.
Current source hash:1927abcc2705e97203a350268d9f40879b7708057bb5ff2c7f5708ecaf65cdb0.
No main compiled release/bootstrap or activation was performed. Existing deployed
plans intentionally refuse this changed source tree until explicitly replaced.
Harness cleanup verified: no delta-runtime labeled containers/networks remain;
no main containers running. Only disposable tmpfs test data was removed; main
volumes/data were never touched. Runtime JSON and before-edit SQL snapshot are
ignored local evidence, not staged fixtures.

Final checks: root unittest style/plan11PASS; S01 offline verify PASS/utility10PASS;
`git -c core.safecrlf=false diff --check` exit0; authored SQL convention scan PASS.
Inspected task SQL against the before-edit snapshot and Git diff; existing user
COUNT(1) edit and unrelated dirty work preserved. `git diff --cached --name-only`
empty. Whitespace/local documentation references checked; all task changes unstaged.

No main runtime, scheduled startup, unchanged900/burst/soak or real-provider test
has been run for these edits. SQL-style changes alone do not prove a speedup.
Leave changes unstaged; no stage/commit/push. Main/HEAD af82381.

### M08D Etsy collect scope and historical900 build/test report (2026-11-14)

DOCS/DIAGNOSTICS ONLY. Etsy SIM stays unchanged in the planned slice; remove
redundant complete-receipt recovery GETs in collect, with required raw eligibility,
route/cache/staging/evidence input adaptations. Keep webhook/fallback GETs and
S01 semantics. A demonstrated SIM concurrency limitation is a reportable finding,
not authority to refactor the SIM. Synchronized22 design, plan, architecture,
contracts/index and temporary Vietnamese review. No collector/model implementation.

New [timing report](23_M08D_BUILD_TIMING.md) and reproducible read-only SQL
tools/s02_data/inspect_build_900.sql. Read ledger of actual saved campaign
campaign-55425905726c48c880d022e0fbface94 for admission14:52:56.547078Z through
finish15:04:46.054387Z on2026-11-13;35 successful nonbootstrap stages,385 model
and208 test timings. Joined batch AND attempt identity; stage p50/p95 match the
saved report exactly. Runtime export: runtime/build900-review-20261114.json,
ignored evidence, not a committed fixture or new run.

Build/test p50/p95/max seconds: Website1.842/6.971/7.895(n11),
eBay2.641/3.797/4.080(n6), Etsy4.982/6.916/8.066(n18). Mean model/test/unitemized
seconds: Web2.890/0.036/0.197, eBay2.359/0.225/0.139, Etsy1.540/0.046/3.653.
Website product activity max5.061s; Etsy empty affected/raw set still6.607s,
including5.679s outside timed models/tests. Unitemized time is NOT proven network,
cache, Python or lock cost. No new EXPLAIN or per-hook/commit timing was run.
Proposed order: subphase attribution, product-aggregate execution plans, audited
no-business-change tick, then demonstrated fixed-cost optimizations. Publish
tuning deferred. No test removal or runtime improvement claim.

Docker initially had no running containers; PostgreSQL exited0. Owner explicitly
allowed temporary PostgreSQL-only start/read/stop. Initial non-escalated Docker
access was denied; authorized elevated diagnostics succeeded. `docker start
multi-channel-order-platform-postgres-1` succeeded; first pg_isready transiently
reported no response, next accepted connections. Historical SELECTs used
PGOPTIONS default_transaction_read_only=on, statement_timeout=30000, plus SQL
BEGIN READ ONLY/ROLLBACK, psql -X -qAt -v ON_ERROR_STOP=1. Main SQL run twice
(initial inspection and local JSON evidence export), both exit0; a targeted
SELECT for two batch detail ledgers also succeeded. Exact report query command is in23.
`docker stop --time 30 multi-channel-order-platform-postgres-1` exit0 (flag
deprecation warning only); final inspect state exited/code0 and docker ps empty.
No Airflow/SIM start, business-data reset/write or volume deletion.

No new900/burst/soak, collector/SIM runtime changes, source generation,
EXPLAIN/BUFFERS, S01 DB regression or new-plan parity/bootstrap. These are not
required to claim this historical report, and remain mandatory before proposed
runtime activation. Checks: read-only historical SQL exit0; PowerShell comparison
of sample counts and p50/p95 against saved report PASS for all3sources (1e-6s
tolerance);35cycles,385model/208test samples confirmed. `git check-ignore
runtime/build900-review-20261114.json` confirms ignored evidence. New report/SQL
whitespace and relative-link checks PASS; `git -c core.safecrlf=false diff --check`
exit0/PASS; `git diff --cached --name-only` empty. No runtime optimization claimed.
Leave all task changes unstaged; no stage/commit/push. Branch main/HEAD af82381.

### M08D revised acquisition plan: detail workers and payload reuse (2026-11-14)

DOCS ONLY, superseding the two-PAGE-worker direction immediately below. Owner
now selected up to TWO DETAIL/ENRICHMENT workers per source/account where needed,
not concurrent page crawling. Apply the policy to required marketplace HTTP work,
not mechanically to Website or to independent concurrent source owners.

Revised [design](22_M08D_EBAY_ACQUISITION.md), plan, source/architecture notes,
delta next-step, index and temporary Vietnamese explanation. Etsy recovery may
reuse complete page receipts rather than refetching every ID; webhook/fallback
detail remains required. SIM already supplies receipt payloads, but its lock scope
and concurrency safety still need qualification. Versioned cache inputs must
distinguish multiple receipt elements in a single page; no synthetic detail audit.
eBay similarly reuses complete page Orders, retains required cancellation/shipping
enrichment and optional grouped lookup of at most50 IDs, not mandatory duplicate
refresh. Both pools need independent worker connections, shared quotas/cooldowns,
durable attempt/lease fencing and one parent completion barrier.

Code inspection: Website uses one read-only repeatable-read snapshot and bulk
ANY(id-set) related-table reads, not a query per order. Delta freeze uses set-based
raw/key membership; build loops dbt nodes, publish loops target tables with
set-based SQL and atomic publication, not one business pipeline/commit per order.
This is structural inspection, not a new runtime or scalability measurement.

No Python/SQL/SIM/env/DDL or running-service changes. No Docker operations, tests900
or data generation. HTTP concurrency, lease/crash, new page/cache/staging parity,
S01 DB and release/bootstrap acceptance have NOT RUN for this revision. Prior
runtime PASS evidence remains unchanged and does not qualify the proposed path.
Checks: `git -c core.safecrlf=false diff --check` exit0/PASS after doc edits;
PowerShell UTF-8 source/doc inspection and stale-direction search performed.
PowerShell new-design required-section/whitespace/local-target checks PASS. Branch main,
HEAD af82381; `git diff --cached --name-only` empty. All changes remain unstaged.
Next: implement/qualify payload reuse and required detail pool, then release gates
and unchanged900, before any burst/soak escalation. No stage/commit/push.

### Superseded earlier acquisition proposal: page workers (2026-11-14)

DOCS ONLY. Owner selected TWO PAGE workers (not detail workers), then batch
`getOrders?orderIds=...` reads of at most50 and targeted cancellation/completeness
fallback. New [design and gates](22_M08D_EBAY_ACQUISITION.md) includes SIM lock
scope/batch support, actual raw-envelope/element provenance, scoped shipping-parent
joins, immutable cycle settings, shared retry/rate budgets and one checkpoint
barrier. Parallel pages do not provide provider snapshot isolation; mutable-window
reconciliation remains mandatory. Batch getOrders does not enrich cancellation;
per-order shipping evidence is still required where applicable. New batch-aware
models require a new compiled-plan release/parity/bootstrap before activation.

Inspected branch main/HEAD af82381 and existing dirty/untracked work, collector,
SIM, eBay staging/evidence and Etsy recovery paths. Published eBay Fulfillment
reference/OpenAPI and Etsy reference/webhooks/rate-limit docs were researched.
Etsy findings are presented to the owner for review, NOT adopted into its plan
or implementation. No authenticated real-provider call was made; published
schemas are not proof of field completeness for every seller/permission scope.

Synchronized plan, architecture, source-contract extension, documentation index,
delta next-step note and temporary Vietnamese review document. No Python/SQL,
SIM, `.env`, DDL or running-service changes in this task. No Docker operation,
data generation or900 rerun. Required implementation gates remain NOT RUN for
this design, including HTTP/concurrency/crash, S01 DB and compiled/full-dbt parity.
Historical runtime results below are unchanged, not evidence for this proposal.

Checks actually run: `git -c core.safecrlf=false diff --check` exit0/PASS;
PowerShell UTF-8 inspection/reference check PASS across all8 task documents and
new local design/STATUS link targets. `git diff --cached --name-only` empty;
`git branch --show-current` main; `git rev-parse --short HEAD` af82381. Existing
dirty work was retained; aggregate diff sizes include prior tasks, not only this
documentation change. New design file also checked for trailing whitespace.
Changes remain unstaged; no stage/commit/push. Next: owner review of Etsy findings,
then implement the eBay design and pass isolated gates before live activation.

### M08D retained delta rollout and UNCHANGED900 PASS; ten-second target pending (2026-11-13)

LATEST OUTCOME: retained-main activation and the finite900 envelope PASS. This
does NOT complete all M08D or satisfy MAX<=10s collect-to-publication. No burst,
sustained/soak or further load escalation was run. Next review: marketplace
collection/pagination, then repeat the SAME envelope; do not keep tuning dbt
blindly or relax limits. The detailed execution log below retains failed gates.

Final900 command (exit0): `python -m tools.s02_data campaign --config
tools/s02_data/config/campaign_rate_900.json --confirm-local`.
Report runtime/campaign-55425905726c48c880d022e0fbface94/report.json, finished
15:04:46.054387Z: READY_FOR_REVIEW, measurement BASELINE_PASS, load_assessment PASS.

- Independent reconciliation:900orders,3801current lines,0errors;300/source.
  Observed989snapshots versus1941planned source versions: the oracle validates
  actual observations and does NOT demand/fabricate every scheduled snapshot.
- Scheduled successes in offered window: Website10/eBay5/Etsy inbox9/recovery7,
  each above unchanged minimum2. Observed drain96.438092s after15:02:52Z window
  end, below unchanged900s. Final pending sends/future versions/eligible missing=0.
- Final-eligibility to first matching SQL observation:900samples,0censored,
  p50=77.376s/p95=236.711s,1200s budget PASS. This includes polling/retries and
  observer cadence; NOT exact commit latency and NOT collect-to-publish latency.
-28resource samples on Docker2CPU/4109369344bytes RAM: observed peak stack
  2249338122bytes, largest container1515049713bytes, DB growth32260096bytes.
  These are sampled peaks, not a continuous resource proof or capacity ceiling.
- Successful stage p95 seconds: build/test Web6.971/eBay3.797/Etsy6.916;
  collect Web5.274/eBay59.427/Etsy40.153. eBay had5failed collection attempts,
  with actual ValueError `mutable page total; reconcile window`, followed by
  successful retry. HTTP error audits=0 does NOT mean collection had no failures.
  No retry budget, source interface or fingerprint rule was changed mid-run.

Diagnostic stage-ledger spans use MIN(collect.started_at) to
MAX(successful publish.finished_at), only workflows started AND published inside
14:52:56.547078Z..15:04:46.054387Z with a pinned delta plan. They are conservative
publication-ACK spans, not stored published_at or exact commit timestamps:

| DAG | Completed | With retry | No-retry spans >10s | No-retry max ACK seconds |
| --- | ---: | ---: | ---: | ---: |
| website_polling | 11 | 0 | 3 | 17.443 |
| ebay_polling | 6 | 5 | 1 | 61.320 |
| etsy_inbox | 10 | 0 | 10 | 40.511 |
| etsy_recovery | 8 | 0 | 7 | 53.703 |

Even excluding retried workflows, the ten-second target is NOT achieved. Do not
substitute the finite900 PASS or a small private sample for that target.
Read-only code review identifies eBay acquire() fetching details for a whole
page BEFORE requesting the next page (ingestion/ebay.py:133). This widens the
mutable-pagination race; separating list crawl from detail work is the proposed
next change, not implemented here. Preserve list/detail raw audit, strict window
validation, source identities and checkpoint semantics. Bounded HTTP concurrency
needs explicit regression/measurement rather than assuming more workers fix it.

Post900 readiness command (exit0): `python -c "from tools.s02_data.delta_deploy
import require_ready; from tools.s02_data.load import LocalDB;
require_ready(LocalDB(), '/opt/airflow/state/delta-plans/delta-20261113-v1');
print('Retained delta plans/publications readiness PASS')"`.
All3active delta publications PUBLISHED and current source/mapping hashes valid.
Final Airflow container2b091b56d5d3f89fd98ee4daafd5a57406b9767ba60bd30b74985e11327f259c,
image sha256:4a3c34378f5bb7e68d8cd86f2ab6e75545aabb0542cd8fe245a14cc32aa2ca8f,
healthy, original7pause flags unchanged. Final total current orders
Web2919/eBay2723/Etsy2837 = retained7579 + new900; no reset or abort.

Final offline command `python -m unittest -q tests.test_delta_deploy
tests.test_airflow_local tests.test_delta_plan`: exit0,27tests PASS (two extra
admission refusal cases). `git -c core.safecrlf=false diff --check`: exit0.
Index remains empty, HEAD af82381 unchanged; no stage/commit/push. Full M08C
matrix, S01 database/HTTP golden regression, further burst/soak and universal
ten-second certification were NOT run/achieved in this task. The cold full54-node
oracle ran separately for EACH retained source; S01 offline checks are below.

Owner authorized startup hardening -> mapping/bootstrap -> retained main rollout ->
UNCHANGED900 in this order. No source/money/history semantics, retry/load budgets,
or Git actions authorized to change. Existing dirty and personal files preserved.

Added orchestration.airflow_local: retains pinned3.3.2 standalone initialization,
gates scheduler thread on reachable API/healthy metadatabase, forwards SIGTERM to
upstream shutdown. Compose selects it, but MAIN HAS NOT been redeployed.10offline
readiness/cancel/key-persistence tests PASS. Image remains the old deployed image.

First real gate `python tests/delta_scheduler_probe.py --allow-owner-idle-stop
--report runtime/delta-startup-ready-20261113-01.json` FAILS before the intentional
freeze/restart could be reached: the first adapter bypassed CLI shared-key setup
and API rejected scheduler JWTs with InvalidSignatureError. This is a regression
in the new private adapter, NOT evidence that legacy main had this JWT failure.
No business stage ran in that failed test and no main delta activation occurred.
Earlier live-log commentary described it as after restart; final journal shows
NO interrupted_cycle/restart marker, correcting that interpretation here.

Fixed adapter BEFORE importing Airflow: use an explicit configured JWT secret or
generate once into ignored state/execution-jwt.key with exclusive creation/0600;
reuse across process/container restarts, never print/commit or silently rotate.
Optional AIRFLOW_EXECUTION_JWT_SECRET in.env.example maps to the supported API_AUTH
setting; blank uses persistent local state. Not disabling token verification.
Source: [Airflow3.3.2 JWT authentication](https://airflow.apache.org/docs/apache-airflow/3.3.2/security/jwt_token_authentication.html).

Added disposable mapping transition probe: close old active eBay mapping rows,
open explicit replacement under existing unique constraints, reject stale and
unbootstrapped plans, verify raw/source identity and new canonical mapping after
rebootstrap. Added explicit cold helper transformation.delta_bootstrap: complete
ordinary dbt build plus all8source candidate multiset comparisons BEFORE publish.
The main mapping/storage has NOT been changed; these new integration checks are
not yet verified. Runtime evidence and remaining blockers will be updated below.

Follow-up command currently running: `python tests/delta_scheduler_probe.py
--allow-owner-idle-stop --mapping-check --report
runtime/delta-startup-mapping-20261113-02.json`. Private scope e1cbe2df6a12:
the strict restart part has three native Website cycle successes, all try2;
each is one intentional freeze fault followed by successful reentry. No extra
infrastructure retry. Its scheduler is stopped before the independent SQL/HTTP,
mapping and full-dbt child gate to stay inside the4GB topology. Root PASS still
requires that child gate plus exact main restoration; do not infer it yet.

The active-publication guard now rejects old consumed plans even if an old
mapping config hash is restored. Current compiled business/runtime source hash
is a35848631f876fd078f83dcb4525a771c4da40fbc21f000e875f4771a851d979.
Added explicit tools.s02_data.delta_deploy and disabled-by-default
LIVE_DELTA_PLAN_DIR: guarded cold full-dbt parity/bootstrap for all3sources,
then actual retained Airflow replacement and >=2scheduled successes per live DAG.
Ordinary live-up checks readiness rather than activating an unbootstrapped plan.
This operator path has NOT been run; local.env has NOT been changed.

Offline checks in this task:
- `python -m unittest -q tests.test_delta_deploy tests.test_airflow_local
  tests.test_delta_plan`: exit0,25tests PASS.
- `python tests/test_s02_live.py`:30tests PASS.
- From fixtures/s01: `python verify.py`: exit0/PASS, offline fixtures only;
  `python -m unittest -q test_tools.py`: exit0,10tests PASS.
- `git diff --check`: exit0; only existing LF/CRLF conversion warnings.
No staged changes/commit/push. Retained-main activation, new900, burst and soak
have NOT run at this checkpoint.

Strict startup/mapping gate FINISHED exit0/PASS at14:26:54.146201Z:
runtime/delta-startup-mapping-20261113-02.json. All3Website cycles SUCCESS/try2;
original interrupted run recovered without recollection. Mapping child PASS:
113retained source snapshots,234raw inputs reprocessed,8candidate outputs equal
to full54-node dbt, cold rebootstrap25.356s (NOT a warm latency sample). Raw audit,
source IDs/fingerprint/first observation unchanged; stale, unbootstrapped and old
reactivated plans refused. Both private scopes cleaned. Original main exact
container/image restored healthy, all7pause flags and absent drain restored.

Started `python -m tools.s02_data.delta_deploy --startup-report
runtime/delta-startup-mapping-20261113-02.json --report
runtime/delta-main-rollout-20261113-01.json --confirm-local`.
Task-owned nonsecret local.env addition:
LIVE_DELTA_PLAN_DIR=/opt/airflow/state/delta-plans/delta-20261113-v1.
The ignored.env and signing key must not be staged. Rollout journal currently
draining-main; no main delta activation or900 PASS is claimed yet.

Retained rollout progress: main became idle naturally, no abort/reset needed.
Migration012 applied; all3cold bootstraps PUBLISHED only AFTER full54-node dbt
and all8candidate parity plus existing source-identity preservation checks:
Web e9d0bde1-65c8-4d8b-b591-cbc817d46eeb (40.967s),
eBay568a7242-cb84-4ce1-8467-4413ba524627 (81.901s),
Etsy966895a3-7777-49be-9fd2-a218e51c74d0 (61.074s).
These are cold bootstrap timings, NOT healthy warm<=10s evidence. Main retained
baseline before900: Web2619/eBay2423/Etsy2537current orders. Activation health and
scheduled observations still pending at this intermediate checkpoint.

Retained rollout FINISHED exit0/PASS at14:44:27.461774Z in
runtime/delta-main-rollout-20261113-01.json. Main Airflow is intentionally replaced:
container1919e8d32891802278546cd2341a3aa9fd6274e5f375f8475caee06ab19c3141,
image sha256:4f9ca683fd0492bf1391c02fb8fcf1c595ff675ee9192c274969bd790f81bd58.
Healthy; all7pause flags unchanged; each of Website/eBay/Etsy inbox/Etsy recovery
has2actual scheduled successes after activation. All3active publications use their
verified local-live-v1/m08d-delta-v1 plans. PostgreSQL/SIM/raw/volumes not reset.

Started `python -m tools.s02_data campaign --config
tools/s02_data/config/campaign_rate_900.json --confirm-local` with the JSON
UNCHANGED.900new orders,300/source,10minute offered window; same retry, resource,
cadence>=2successes/DAG and drain<=900s gates. No result claimed until measured.
Active report: runtime/campaign-55425905726c48c880d022e0fbface94/report.json;
dataset campaign-rate-900-8eab0dfd3312, source campaign9caed6c79e22,
admitted14:52:56.547078Z. Source configuration file SHA256 remains
9c8c46fe6e4dfde377d1a5d51bd638b1aa6d45033fe2be8d004a2b4698780c32.
Campaign live-up rebuilt/recreated Airflow through the normal drained path while
retaining verified plans and persistent signing key; final identity belongs to
the campaign's actual runtime, not the earlier rollout image ID alone.
Pre-admission successful stage-ledger collect-to-publish-ack samples ranged
1.626..10.180s. At least one exceeds10s: no universal MAX<=10s claim. These
include preparation concurrency, not the later admitted load window, and are
conservative DB audit acknowledgment spans, not exact commit timestamps.

### Delta scheduler follow-up: retry cause reproduced; four-DAG gate PASS (2026-11-13)

Final command `python tests/delta_scheduler_probe.py --all-sources
--allow-owner-idle-stop --report runtime/delta-scheduled-four-dags-20261113-03.json`:
exit0/PASS at11:21:01.796749Z. Private test83bdc8bac403, three compiled plans and
the production Website/eBay/Etsy inbox/Etsy recovery DAGs, real SQL/HTTP and
signed webhook receiver outside Airflow. No business-stage/operator mocks.

- Final26scheduled DAG runs: Website10, eBay9, Etsy inbox4, Etsy recovery3;
  ALL native SUCCESS and cycle try1. All26SQL workflows SUCCEEDED and pin the
  correct per-source plan; all104business-stage attempts SUCCEEDED/attempt1.
- Actual physical Etsy source fence held: inbox/recovery source_slot waits
  persisted with task_try_number1, both sensors produced native reschedule rows;
  Website/eBay completed while neither Etsy collect could start. Fence released
  without changing task state, stealing ownership or consuming business attempts.
  Final two source waits SUCCEEDED at try1; three native reschedule rows retained.
- One real signed notification accepted202. Actual HTTP lineage: inbox1detail,
  recovery6details across3runs. Receipt9001002 had NO webhook and was discovered
  by recovery. Validated receipt rows link through metadata.http_raw_id to the
  distinct HTTP audit and its collection run, not by equating their raw IDs.
- Final core: WebW1001, eBay12-10001-10001, Etsy9001001/9001002. Marketplace
  snapshots exactly1/order despite4/3receipt observations; Website2observed
  snapshots (bootstrap then explicit source update). No frozen new input remains
  unconsumed. All3publication pointers match the final completed source cycles.
- Portable archive successfully written/read:26task log files in
  runtime/delta-scheduler-83bdc8bac403/test-task-logs.tar.gz; native task history
  empty (no actual task failures/retries). No colon paths extracted on Windows.
- Exact main containerf4f4e7ba... and image40dfb207... restored healthy; all7pause
  flags identical, initially absent drain signal absent again. Independent
  docker ps/network label checks exit0/empty; all main services healthy, observer
  running. No main PG/SIM stop, reset, extra abort, delta activation or migration012.

This closes the requested diagnostic and isolated four-DAG scheduling/contention
slice, NOT full M08D. Still pending: standalone API-ready startup hardening,
mapping-change/rebootstrap, retained-owner bootstrap/rollout and unchanged900/
burst/soak. Do not infer healthy<=10s or marketplace container-kill coverage from
this tiny/fenced scheduler gate. Main still runs the legacy image/path.

Final checks: `python -m unittest -v tests.test_delta_plan`:9PASS;
`python -m compileall -q tests/delta_scheduler_probe.py tests/delta_scheduler_sources.py
tests/dags/delta_scheduled.py`:exit0; source_hash unchanged
c99a51f0bc23fd3776fda08fd8afca685031fc718a8b7be6fce05d144ae2a0a3.
S01 verify10checks/utilities10PASS earlier in this same task. Full54-node dbt oracle
not rerun in this test-only slice; prior parity evidence remains separately scoped.
Git diff--check exit0; staging empty, main/HEADaf82381 unchanged. Personal untracked
HANDOFF_SHA256SUMS.txt/local_now.json/quick_6min.json untouched. Changes unstaged.

#### Diagnostic evidence and failed harness iterations (preserved, not relabeled)

Owner requested priorities1/2 only: diagnose the four native task tries, then
verify actual scheduled marketplace operation and coordinator contention. No main
delta rollout or900 rerun in this slice. Existing dirty/personal files preserved;
no stage/commit/push. Main initially healthy on main/af82381, Python3.12.7 available.

Diagnostic command: `python tests/delta_scheduler_probe.py --allow-owner-idle-stop
--report runtime/delta-scheduled-diagnostics-20261113-01.json`. Main naturally
drained from10:34:40Z to idle by10:41:44Z, then only exact owner Airflow stopped.
Test identity c0fe357083ff; bootstrap plan SHA unchanged712cdefb...,
batcha1fc62b3-7a3d-4d9e-96bc-2c332abc7f7b. Actual restart reproduced four tries:

- Original scheduled run2026-11-13T10:44:44.390114+00:00,
  workflow8888f461-7fc8-5923-b3ac-9ef238c84ed7,
  batch0d654693-707c-5906-80a8-39d0bf6934e5.
- Try1: intended durable-freeze interruption,10:45:06.071626Z.
- Try2 started10:45:36.415964Z during the30s container shutdown grace period;
  its log ends after worker startup parse, with no second collect/freeze stage.
  Container restart recorded10:45:39.596857Z.
- Restarted scheduler reset the one orphaned running task at10:46:50.284293Z,
  queued try3 at10:46:50.923295Z. LocalExecutor's SDK supervisor then failed
  with httpcore/httpx ConnectError `[Errno111] Connection refused` before task
  execution, while the standalone Execution API was not ready. Scheduler recorded
  executor failure and UP_FOR_RETRY at10:47:04.554392Z.
- Try4 subsequently SUCCESS. Logical ledger remains collect1SUCCEEDED,
  freeze1RETRYABLE/freeze2SUCCEEDED/build1SUCCEEDED/publish1SUCCEEDED.
  Later fault-enabled cycles intentionally also fault once PER WORKFLOW, not
  once per deployment, explaining their usual two tries.

Evidence was read from the private task log, native task_instance_history and
`docker logs --since 4m delta-sched-airflow-c0fe357083ff` filtered for
orphan/reset/try3/Connection refused. This is a reproduced shutdown/API-readiness
race, NOT a dbt SQL failure or evidence of OOM. Do not raise budgets to hide it.
Future startup hardening should gate scheduler dispatch on Execution API readiness;
this slice has not changed the main standalone topology or restart semantics.

The diagnostic command ultimately exited1: workflow/native-DAG assertions passed,
but `docker cp /opt/airflow/logs` failed on Windows because scheduled run folder
names contain colons. Report remains FAIL (not relabeled). Main restoration
healthy/identical pause flags/drain state verified despite this failure. Fixed
log capture to create a tar.gz INSIDE the private container and copy one portable
archive; raw log directory names are never extracted onto Windows.

First four-DAG command `python tests/delta_scheduler_probe.py --all-sources
--allow-owner-idle-stop --report runtime/delta-scheduled-four-dags-20261113-01.json`
exited1 safely BEFORE main stop: a previously calculated Etsy interval appeared
between the two idle reads. No test containers started; main healthy and pause/
drain state restored. The runner now requires15s continuously quiet inside the
same600s drain limit, with a fresh check immediately before and after stop.
It never marks a newly arrived interval successful or aborts it.

Four-DAG rerun02 (`--report runtime/delta-scheduled-four-dags-20261113-02.json`)
also exits1, on a TEST assertion: it joined validated `etsy_receipt` raw IDs to
`etsy_http_attempts.raw_record_id`, which references the distinct `etsy_http`
audit raw instead. Do not change production ingestion to accommodate this test.
Corrected the probe to follow the explicit `receipt.metadata.http_raw_id` link,
then the HTTP attempt's collection_run_id and actual annotated Airflow DAG ID.
Before that assertion, actual evidence:20native DAG runs all SUCCESS/try1 and
20SQL cycles SUCCEEDED, signed webhook202 accepted, core Web1/eBay1/Etsy2,
both Etsy sensors rescheduled while Website/eBay succeeded. These are partial
observations, not a passing overall gate. Main restored healthy with identical
pause/drain state; private resources removed. Portable tar.gz log capture now
exists and was independently read without extracting colon paths to Windows.
Rerun03 passes above; no production behavior or required gates relaxed.

Harness now archives task logs even on PASS and native task history/reschedules.
Added optional `--all-sources` gate and private HTTP source/receiver helper:
four production scheduled DAGs, physical Etsy source lock, native reschedules,
independent Website/eBay progress, signed webhook plus a receipt omitted from
notification for HTTP recovery. Both Etsy DAGs must resume without repeated
business stages; all four require two scheduled successes, pinned plans, correct
pointers/raw consumption and no duplicate marketplace snapshots. No expected
warehouse outputs are served as source data. Implementation is not runtime PASS.

Checks so far: plan unit tests9PASS, S01 verify10checksPASS and utilities10PASS;
compileall and diff--check exit0. Installed Airflow SDK four-DAG serialization/
reschedule check exit0/PASS in a network-none384MB container. No production SQL,
DDL, source schema, source fingerprint or retry budget changed in this slice.

### Real delta Website scheduler retry/restart gate PASS (2026-11-13)

Final command `python tests/delta_scheduler_probe.py --allow-owner-idle-stop
--report runtime/delta-scheduled-20261113-02.json`:exit0/PASS with strengthened
assertions (not just SQL workflow completion). A real LocalExecutor standalone,
production Website DAG/sensor/collector and compiled dbt path ran in the labeled
isolated network/PG. No operator/collector/business-stage mocks. Main was drained
to actual idle naturally, then ONLY its exact Airflow container stopped.

- Fault correctly configured from the first run on both DAG AND task params,
  checked with the installed SDK and serialization before unpause.
- Interrupted DAG scheduled__2026-11-13T10:09:01.491939+00:00:
  workflow972f90af-eca9-5f6f-922d-ef8915832a3c,
  batchf1e052b3-897a-5ffd-a9e7-834015c19719. Freeze1RETRYABLE was observed while
  Airflow task up_for_retry; the test Airflow container was stopped/restarted.
  Same cycle/batch then collect1SUCCEEDED (no recollection), freeze2SUCCEEDED,
  build1/publish1SUCCEEDED. Airflow DAG itself SUCCESS at10:12:28.175550Z.
- Restart recorded at10:09:58.024609Z. Two scheduled runs ending AFTER restart
  SUCCESS at10:12:28.175550Z and10:13:13.839907Z; an additional already-created run
  drained to SUCCESS at10:13:58.764757Z. All3final Airflow runs and SQL workflows
  SUCCESS/SUCCEEDED; final task states recorded. Exact latest publication pointer
  matches latest scheduled cycle. Every cycle pins the same validated plan SHA
  712cdefbeb1e8639748390b475fc6af89b172a004eef8cb1201964b6e9944d1f.
- Review limitation: interrupted Airflow task needed4tries (later two cycles2
  each); business ledger still collect1/freeze1RETRYABLE+2SUCCEEDED/build1/pub1.
  No attempt budget reset or forced success. Extra task-level restart retries
  were not diagnosed from retained logs (success-path task logs not archived),
  so do not assert an API-startup or RAM root cause. This is a passing recovery
  within the existing budget, not evidence of retry-free infrastructure startup.
- Main restored to the SAME container/image, healthy; all7pause states exactly
  unchanged, its initially absent drain signal absent again. Test containers and
  network cleaned by exact identity/label. No main delta activation/migration012,
  owner data reset, source contract change, additional batch abort, stage/commit/push.

This closes the single-Website scheduled retry/container-restart gate only.
Intentional freeze fault/retry/restart cycles are NOT healthy warm10s latency
samples. Still unrun: marketplace/all-source delta scheduled operation and real
contention/reschedule, mapping-change bootstrap, retained-owner activation,
unchanged900-load/sustained/burst/soak acceptance. M08D remains IN PROGRESS.

Final independent checks: `docker ps -a --filter label=de.probe=delta-scheduler
--format '{{.Names}} {{.Status}}'` and `docker network ls --filter
label=de.probe=delta-scheduler --format '{{.Name}}'`:exit0/empty. Owner drain
absence independently confirmed True; owner Airflow/PostgreSQL/SIMs/receiver/
live-source/report healthy, observer running. `git -c core.safecrlf=false diff
--check`:exit0/no output; cached stat empty, main/HEADaf82381 unchanged. New tests
and documentation remain unstaged. Source hash remains
c99a51f0bc23fd3776fda08fd8afca685031fc718a8b7be6fce05d144ae2a0a3.

#### Scheduler test development and earlier partial evidence

Continuing M08D only. Added tests/delta_scheduler_probe.py and the disposable
tests/dags/delta_scheduled.py wrapper, using the production Website DAG/sensor/
collector with its supported fault_after_freeze_once parameter. No production
business SQL, DDL, source schema or retry algorithm changed. Runbook:DELTA.md.

First command: `python tests/delta_scheduler_probe.py
--allow-owner-idle-stop --report runtime/delta-scheduled-20261113-01.json`.
Owner previously permitted temporarily stopping only main Airflow IF idle and
restoring exact health/pause state. Main was not idle at entry. The controller
verified the deployed drain helper, recorded exact owner ID/image/pause states,
and placed its exclusive token in the previously absent drain signal. This
stops new intervals, not existing retries, without pausing any DAG. A600s wait
requires no active DAG runs/batches/nonterminal source owners before stop.
No automatic abort, lease stealing or forced task success. Cleanup restores
only its own signal, same container health and original pause flags on failure.

Initial observations:4active periodic DAG runs and main batch
30a9b5b9-c3cc-5d31-853d-7681184eda96 BUILDING; later no active batch and3active
periodic runs with current nonterminal owners (not assumed stale). Drain reached
idle naturally: no active runs/batches/nonterminal owners. No additional abort.
Controller stopped only exact main Airflow, bootstrapped Website delta in a
temporary PG and ran the production DAG in a separate Airflow container.

First command exited0/root PASS, but it is PARTIAL scheduler evidence: initial
wrapper changed only DAG params, while task params overrode the fault to false.
Fourteen scheduled warm-up runs succeeded without injection. Fixed the test
wrapper to configure both DAG and tasks; no production DAG code changed. A real
freeze1 RETRYABLE then occurred in scheduled__2026-11-13T09:49:38.073922+00:00,
workflow57bf48cd-94e4-578b-950c-cc34f86a9818,
batcha2c55b56-e1c6-516f-99dc-724cb054b502. Test container restarted; same workflow
retained collect1SUCCEEDED, freeze1RETRYABLE/freeze2SUCCEEDED, build1/publish1
SUCCEEDED. Main exact container/image restored healthy; all7pause flags unchanged;
its initially absent drain signal removed. No main delta activation/data reset.
The first report's success list was read before final retry drained and includes
warm-ups: it does NOT prove the interrupted Airflow DAG terminal state or two
post-restart successes. Do not count it as the full scheduler gate.

Strengthened the runner: require two successes with end_date AFTER recorded test
restart, snapshot final Airflow run/task states, assert the exact interrupted DAG
itself SUCCESS and all runs successful, assert latest publication pointer; retain
test-only diagnostics before cleanup on failure. Second command (final result above):
`python tests/delta_scheduler_probe.py --allow-owner-idle-stop
--report runtime/delta-scheduled-20261113-02.json`.

SDK check in a network-none/read-only 384MB image worker:
`python /review/tests/delta_scheduler_probe.py --sdk-check`, with PROJECT_ROOT/
PYTHONPATH=/review and POLLING_NONBLOCKING=true:final exit0/PASS; DAG/task fault
params survive actual DagSerialization. First SDK check exited1 because it read
runtime-only sensor.mode on a SerializedBaseOperator; fixed test to assert mode
on the actual sensor and params on both actual/serialized operators. No runtime
policy was relaxed.
`python -m unittest -v tests.test_delta_plan`:exit0/PASS9;
`python -m compileall -q tests/delta_scheduler_probe.py tests/dags/delta_scheduled.py`
and `git -c core.safecrlf=false diff --check`:exit0.

### Authorized exact stale-owner abort (2026-11-13)

Owner explicitly authorized official abort of batch
0bf4d6be-5ed6-5b56-85c7-d8b56c3e4781. Reverified batch TESTED, TRANSFORM SUCCEEDED,
workflow87fa9b00-e4a8-501a-8a81-d9292ec3b64b RUNNING, original etsy_inbox Airflow
run FAILED and its tasks skipped; no non-idle data_platform SQL at inspection.
Verified deployed CLI derives exactly these batch/workflow IDs. Existing source
wait attempts1..4 were TIMED_OUT; attempt5 source/release waits SUCCEEDED. Reused
attempt5 for abort, never allocated a new wait or reset history.

Exact official command:

```powershell
docker exec multi-channel-order-platform-airflow-1 /opt/airflow/project-venv/bin/python -m orchestration.polling --source etsy_sim --collection-mode drain --execution-id scheduled__2026-11-13T05:00:31.450511+00:00:drain --dag-id etsy_inbox --airflow-run-id scheduled__2026-11-13T05:00:31.450511+00:00 --mapping-version local-live-v1 --reuse-cycle-config --nonblocking --wait-seconds 300 --coordinator-attempt 5 --abort
```

Exit0, output `batch=0bf4d6be-5ed6-5b56-85c7-d8b56c3e4781 status=FAILED`.
Independent SQL confirms batch and RECOVER workflow both FAILED. Before/after:

- Etsy last-good pointer unchanged:24abd23c-c7df-5fb6-afb3-9bf09dda30d0.
- Frozen manifest count20961/ID-signature MD5d7e151d6c6377a9142c308219949e235 unchanged.
- Joined raw count20961/full-row-signature MD5862bdb8430dd2874fb909feefd646fbc unchanged.
- Task ledger retained: collect1SUCCEEDED, freeze1SUCCEEDED, build_and_test1RUNNING;
  the stale historical RUNNING row was NOT rewritten or forced successful.
- Old Airflow run remains FAILED; all7DAG pause states unchanged. Source owner
  naturally handed off to48832b3f-a7df-5a98-aa87-162d17680dc0 after terminalization;
  no owner pointer was manually changed. Handoff is not publication acceptance.
- Owner Airflow/PostgreSQL/SIMs/report/source/receiver healthy; observer running.
  No stop/restart, admission drain, second scheduler, data deletion, budget reset,
  source/mapping change, stage, commit or push. Scheduler gate remains pending.

This resolves only the specifically authorized stale batch, not M08D acceptance.

### Further M08D crash/concurrency/retained-history verification (2026-11-13)

No production algorithm, target schema or source contract changed in this slice.
Added tests/delta_process_cases.py to the disposable delta probe. No main delta
activation, owner-data reset, owner container stop/abort, stage, commit or push.

- `python tests/delta_runtime_probe.py --docker --report runtime/delta-recovery-20261113-01.json`:
  exit0/PASS. Real child SIGKILL after uncommitted candidate CTAS releases the
  physical source lock, leaves BUILDING/no result1/no raw consumption; attempt2
  builds/publishes. SIGKILL during real publication deletes/inserts/mart merge
  leaves the independent reader on last-good, rolls back the transaction and
  leaves TESTED/raw unconsumed. Retry records the prior PUBLISH audit FAILED/
  INTERRUPTED and commits once. Two real source processes cross a shared build
  barrier and publish to both source pointers. These are process/SQL cases, NOT
  scheduler/task/container-kill certification. Full dbt54nodes/all8business-output
  multiset parity, coordinator13cases and invalid-money refusal still PASS.
  Real collector wall upper bounds for100orders: Website4.624s/eBay5.170s/
  Etsy7.609s; all9finite samples below10s in that disposable scope.
- Added bounded `--http-rounds {1,2,3}`. Three rounds repeat1/10/100orders per
  source, with333distinct generated orders/source and all raw/warehouse rows
  retained between waves. Source test-state RAM stays bounded to100orders/wave.
  Every cycle checks actual retained order count against its starting baseline
  plus cumulative generated orders. Explicit nested latency verdict is separate
  from correctness PASS; any wall upper bound>10s fails that sample set.
- Extended command: `python tests/delta_runtime_probe.py --docker
  --http-rounds 3 --report runtime/delta-retained-20261113-01.json`.
  Exit0/PASS correctness, all13 coordinator cases, all3 process/concurrency
  cases, full dbt54nodes/all8business-output multisets, genuine invalid-money
  refusal. Nested finite-sample latency PASS:27/27 below10s,0violations.
  Nine samples/source: max Website3.579860s/eBay5.873752s/Etsy8.558430s.
  Final retained current orders335/334/334 respectively (333new/source plus
  regression baseline); no warehouse/raw clear between waves. Worst sample:
  Etsy100changed/334retained, collect4507ms/freeze808ms/build-test1301ms/
  publish1485ms; conservative independently observed wall8.558s. Temporary PG,
  bounded local HTTP source and1/2line fixture shapes, not owner900 or soak/SLA.
- `python -m unittest -v tests.test_delta_plan`:exit0/PASS9.
  From fixtures/s01: `python verify.py`:exit0/PASS10offline checks;
  `python -m unittest -v test_tools.py`:exit0/PASS10.
  `python -m compileall -q tests/delta_process_cases.py tests/delta_runtime_probe.py
  tests/delta_http_cases.py`:exit0; `git -c core.safecrlf=false diff --check`:exit0.
- Docker info reports4109369344bytes memory (about3.83GiB). Owner Airflow and
  PostgreSQL/SIM/report/source/receiver healthy at inspection. A second scheduler
  has NOT been started concurrently. Requested permission to verify owner idle,
  temporarily stop only owner Airflow for isolated scheduler testing, then restore
  exact health/pause state; no owner stop is inferred without that approval.

Owner subsequently approved stopping only main Airflow IF idle. Two read-only
owner checks did NOT meet that condition:4active DAG runs (cycles rescheduling/
retrying) and retained TESTED Etsy batch0bf4d6be-5ed6-5b56-85c7-d8b56c3e4781.
Owner is etsy_inbox/scheduled__2026-11-13T05:00:31.450511+00:00, Airflow run FAILED
at05:30:42.523986Z, both its tasks skipped; TRANSFORM completed SUCCEEDED at
05:30:45.694603Z while workflow build_and_test attempt1 remains RUNNING and its
RECOVER parent87fa9b00-e4a8-501a-8a81-d9292ec3b64b remains RUNNING. There was no
active non-idle data_platform SQL in the diagnostic snapshot. This is retained
main legacy-path state, not a delta fault-probe mutation. Did NOT stop/restart
owner, change DAG pause states, drain it, abort that batch or start a second
scheduler. A protected quiet window and explicit official abort/recovery decision
for that exact stale owner are needed before the isolated scheduler gate.

Final source hash remainsc99a51f0bc23fd3776fda08fd8afca685031fc718a8b7be6fce05d144ae2a0a3.
Labeled delta probe ps is empty after cleanup. No task changes staged/committed.

Remaining gates: actual scheduled delta retry/restart, mapping-change bootstrap,
main retained-data bootstrap/activation, owner900 and sustained/burst/soak. The
new process tests close their specific crash points, not the full crash matrix.

### Latest M08D coordinator integration slice (2026-11-13)

This entry supersedes the experimental source hash and pending-coordinator
statements in the historical entries below. Main is NOT switched to delta;
migration012 remains out of ordinary bootstrap/migrate/live-up lists. No owner
database reset, owner service stop/abort, pause-state change, stage, commit or push.

Implemented: optional private `POLLING_DELTA_PLAN_DIR`, immutable plan SHA in
existing polling-cycle settings, pinned retry configuration, shared legacy/live
registration fence, source-private execution through the existing four-stage
workflow and durable five-attempt ledger. Missing/stale plans refuse before
collection; explicit abort and published reentry remain available. Publication
success audit commits atomically with data/pointer/exact raw consumption. CLI
bootstrap has explicit attempt1..5 and published reentry skips another publisher.
Compiler scratch output now uses the system temporary directory, not source.
Contracts/runbook:21_M08D_DELTA_RUNTIME.md and transformation/DELTA.md.

Actual checks this slice:

- `python tests/delta_runtime_probe.py --docker --report runtime/delta-integration-20261113-01.json`:
  exit1 at final full-oracle comparison (one evidence-row difference). Valid raw
  from an intentionally aborted owner was correctly retained but not yet caught
  up when compared against full rebuild over all raw. Fixed probe sequencing:
  execute a normal successor through the real workflow before comparison. No
  raw deletion, expected-output relaxation or retry reset; no report file emitted.
- Same command with report `runtime/delta-integration-20261113-02.json`:exit0/PASS
  coordinator10checks, real Website SQL and eBay/Etsy HTTP collectors, full dbt
 54nodes and all8 output multisets (batch lineage excluded) match. Uninstrumented
 100-order wall upper bounds: Website3.673s/eBay6.831s/Etsy15.532s. Etsy FAILS10s;
  collect12.635s vs build/test0.838s. Root report PASS means correctness, NOT SLA.
- Same command with report `runtime/delta-integration-20261113-03.json`:exit0/PASS,
  expanded coordinator13checks, real collectors and full parity again. Etsy100
  instrumented profile: fetch14.432s/102calls; claim1.506s/100calls. Wall23.380s
  is instrumented, not a qualification sample. Other100-order samples:
  Website4.046s/eBay6.682s; finite disposable fixtures only.
- No-network image microbenchmark:100 `urllib.request.build_opener()` calls
 14.706s;14.299s in loading default CA paths. Etsy was rebuilding this per HTTP
  request. It now reuses one opener per worker thread, preserving TLS checking,
  redirect refusal, request-local credentials and per-response raw/audit/retry.
- `python tests/coordinator_probe.py --docker --report runtime/coordinator-delta-20261113-01.json`:
  exit0/PASS13real coordination SQL cases, real dbt compile/empty build and
  installed Airflow SDK import/poke for all4DAGs. Business stages in these
  coordinator cases are test doubles; SDK import is NOT scheduled execution.
- HTTP/drain regression: Docker project-venv `python -m unittest -v
  tests.test_etsy_http tests.test_etsy_drain`, network none/read-only code mount,
  workdir and PROJECT_ROOT=/review:exit0/PASS15. First invocation without those
  path overrides imported the image's old collector:4new tests errored before
  exercising source,11drain tests passed. Corrected invocation passed all15;
  owner image/files unchanged.
- `python -m unittest -v tests.test_delta_plan`:exit0/PASS9.
  `python tests/test_s02_live.py`:exit0/PASS30;
  `python tests/test_s02_campaign.py`:exit0/PASS18;
  `python tests/test_m08d_measure.py`:exit0/PASS12.
  From fixtures/s01: `python verify.py`:exit0/PASS10offline checks;
  `python -m unittest -v test_tools.py`:exit0/PASS10.
- `python -m compileall -q transformation orchestration ingestion/etsy.py
  tests/test_etsy_http.py tests/delta_coordinator_cases.py tests/delta_http_cases.py
  tests/delta_runtime_probe.py`:exit0. `git diff --check`:exit0, LF/CRLF warnings only.

Report04 (`python tests/delta_runtime_probe.py --docker --report
runtime/delta-integration-20261113-04.json`) exited0/PASS correctness/full oracle,
but Etsy100 still took24.484s collecting. Investigation found the child
`python -m ingestion.etsy` preferred image-baked code because worker cwd remained
`/opt/project`, despite PYTHONPATH=/review. Reports02..04 therefore measure the
old image collector with the NEW mounted coordinator/dbt runtime; they do NOT
verify the opener optimization. The parent coordinator/runtime used mounted
source. Probe now sets cwd=/review and asserts all three collector module paths
in a child process before measurement. Report05 reruns the corrected setup.

Corrected final command `python tests/delta_runtime_probe.py --docker --report
runtime/delta-integration-20261113-05.json`:exit0/PASS. All13 coordinator cases,
real mounted-source collectors, full ordinary dbt54nodes, all8 business-output
multiset comparisons and genuine invalid-money refusal pass again. All9 finite
healthy samples are below10s, including the conservative wall upper bound from
source admission to an independent publication-pointer read:

| Changed orders/source | Website seconds | eBay seconds | Etsy seconds |
| --- | --- | --- | --- |
| 1 | 3.541 | 3.675 | 4.244 |
| 10 | 6.775 | 3.761 | 4.778 |
| 100 | 4.173 | 9.213 | 7.048 |

At100orders, collect/build-test/publish ms: Web674/904/1721,
eBay4497/1796/1613, Etsy4123/955/1174 (freeze/inter-stage overhead is also included
in the total). Old-image report02 Etsy15.532s vs corrected report05 7.048s is NOT
a controlled A/B; machine load differed. The CA-store microbenchmark/profile and
HTTP unit tests independently identify setup reuse; do not promise that ratio.
Scope: one sample per source/size,1Website/Etsy line and2eBay lines/order, retained
small fixture history, temporary PG storage, local HTTP handlers, no scheduler.
eBay100 has only0.787s headroom: this is not sustained SLA/capacity certification.
Current compiled source hash:
`c99a51f0bc23fd3776fda08fd8afca685031fc718a8b7be6fce05d144ae2a0a3`.
Final `git -c core.safecrlf=false diff --check`:exit0/no output;
`git diff --cached --stat`:empty. HEAD remains af82381, all task files unstaged.
Final Docker ps filters for de.probe=delta-runtime and de.probe=reuse-coordinator:
exit0/empty after labeled-resource cleanup. Owner-project ps: PostgreSQL, Airflow,
both SIMs, receiver, live-source and report healthy; observer running. Container
health does not qualify delta because main is still on its original path.

Unrun: main retained-data bootstrap/activation, actual
scheduled delta retries/process-kill recovery, simultaneous cross-source builds
and publication, mapping-change bootstrap, owner900 workload and sustained/burst/
soak acceptance. No completed M08D or universal <=10s claim.

### M08D ten-second redesign IN PROGRESS (2026-11-13)

Owner specified acquisition-start to committed/readable publication<=10s,
including waits after acquisition, and approved an incremental redesign. Existing
full-project cycles do NOT meet this target. Additional parse-only measurement
in the running Airflow image:44.122331s (exit0); CLI startup/parsing alone can
exceed10s. Design/clock/workloads:21_M08D_DELTA_RUNTIME.md; field dictionary was
finalized before migration012. SQL remains dbt-owned; compile a source-validated
deployment plan once, execute affected-order graphs with source-private tables,
merge dbt-calculated effective marts and consume exact new raw only on commit.

New experimental files: delta_plan.py/delta_runtime.py/delta_publish.py,
macros/delta.sql and migration012. NOT activated in main, NOT in ordinary
bootstrap/migrate/live-up lists. Main remains on the previously verified image.
No owner data reset, pause-state changes, abort, stage, commit or push this slice.
Integration runbook:transformation/DELTA.md. This is not completed M08D or a10s claim.

Actual current checks:

- `python tests/delta_runtime_probe.py --docker` final exit0/PASS: real disposable
  PG16 migration012 and reapplication;3 compiled dbt source graphs, each11models,
  Website14tests/eBay3/Etsy2. Bootstrap batches ecd43441-8fe1-4a14-bb39-0b5e201a3299,
  17d6be3b-7706-45b4-942c-8e202c483b17,54f63c84-9cda-470a-b4bb-0b7883fdf845.
  Duplicate raw retains audit/evidence without duplicate history; injected test
  failure and failed publication consume nothing and retry; empty tick preserves
  core/marts; unchanged order retains its row lineage. Independent full `dbt build`
 54nodes PASS; all8 core/mart relations match as multisets of every business field
  (batch lineage excluded intentionally). This is SQL/storage verification,
  NOT HTTP/Website collector, Airflow scheduling, retained-load or latency acceptance.
- Earlier executions of the SAME probe exited1: run-operation overwrote the
  compiled manifest (fixed by retaining it first); publisher lacked config schema
  USAGE (fixed explicitly in012); a probe-only mart assertion used the restricted
  transform role (fixed to disposable admin; no extra mart permission granted).
  Generated labeled temporary containers/network were cleaned after each run;
  no main resources or volumes removed.
- `python tests/delta_runtime_probe.py --docker --report runtime/delta-probe-20261113-01.json`:
  exit0/PASS after attempt-ledger/hash hardening, plus a previously unseen late
  intermediate Website version (history retained, current remains canceled),
  single-dirty-order scope and genuine invalid-money refusal with last-good/raw
  consumption unchanged. Full dbt54nodes/all8relations parity PASS again.
  Healthy warm Website SQL/storage-cycle samples4.188/4.298/4.190s, no-input4.502s,
  terminal update5.340s. Cold bootstrap Web4.281/eBay10.456/Etsy3.956s; injected
  failure+retry10.561s. These INCLUDE repeated plan checks/freeze/build/test/publish,
  but EXCLUDE acquisition. Disposable small fixture data, not retained owner load
  or a controlled A/B; not the10s acceptance. No cold/fault samples hidden.
  Afterward, source-hash traversal prunes generated directories before walking;
  compilation refuses unsupported dbt configs/hooks/test policies.
- `python tests/delta_runtime_probe.py --docker --report runtime/delta-probe-20261113-02.json`:
  exit0/PASS final guards and all parity/failure checks again. Warm SQL/storage
  Website2.638..3.246s (no-input2.347s), Etsy2.746s; eBay8.096s. eBay
  build/test5.957s is now the measured slow phase even for this tiny affected-order
  fixture. Its cold bootstrap8.519s vs Web3.305/Etsy2.571s; injected retry4.904s.
  Do not extrapolate a target PASS: acquisition is excluded and only small
  disposable fixture samples were run. Read full phases in that report.
  Main PostgreSQL settings are unchanged.
- `python tests/delta_runtime_probe.py --docker --report runtime/delta-probe-20261113-03.json`:
  exit0/PASS all checks/full oracle. Slowest warm eBay nodes: line-history2.392s
  and fulfillment-integrity test2.254s. Actual EXPLAIN of line-history:
  estimated cost2426733.84; JIT-on execution2967.709ms, including2904.663ms LLVM
  compilation; JIT-off execution0.489ms on the same disposable SELECT. These are
  controlled diagnostic SELECTs, not full-cycle A/B or a whole-pipeline speedup.
  Official reference:postgresql.org/docs/16/jit-decision.html. The experimental
  delta runner now scopes jit=off to its build transaction and ANALYZEs each
  materialized table before downstream nodes. No server-wide/full-dbt change.
  Report04 rechecks these changes below.
- `python tests/delta_runtime_probe.py --docker --report runtime/delta-probe-20261113-04.json`:
  exit0/PASS CURRENT runner after transaction-local JIT policy, fresh table
  statistics and source-fence hardening. Each source11models; Website14/eBay3/
  Etsy2tests. Full dbt54nodes and all8core/mart multiset comparisons PASS again.
  Warm SQL/storage eBay2.095s (build/test0.480s), Etsy2.308s (0.642s),
  Website2.259..2.619s (0.516..0.668s); no-input2.185s; injected failures+retry3.883s.
  Cold Web2.602/eBay1.895/Etsy2.464s. These remain SMALL DISPOSABLE SQL fixtures,
  excluding collector acquisition. No end-to-end SLA/capacity/Airflow claim.
  Report03's2.967s->0.489ms comparison is not a whole-cycle ratio; report04 combines
  JIT policy AND fresh statistics, under uncontrolled concurrent main workload.
  Additional PASS: actual physical source lock blocks a peer using the legacy
  key; nonterminal durable source owner refuses; retained FAILED terminal owner
  permits the experimental probe. KeyboardInterrupt after REAL candidate CTAS
  rolls back DDL, releases the session lock, retains BUILDING and permits durable
  attempt2 without inventing an attempt1 result. This tests Python interruption
  unwinding, NOT a killed process/container or a production coordinator rollout.
  Cleanup rolled back unfinished transactions before releasing source locks.
- `python -m unittest -v tests.test_delta_plan`:exit0/PASS9tests, including duplicate
  node-ID refusal, generated-artifact hash independence and unsupported dbt-config
  refusal. Offline plan validation, not runtime.
- `python verify.py` in fixtures/s01:exit0/PASS10offline checks.
- `python -m unittest -v test_tools.py` there:exit0/PASS10tests.
- `python tests/test_s02_live.py`:exit0/PASS30;
  `python tests/test_s02_campaign.py`:exit0/PASS18;
  `python tests/test_m08d_measure.py`:exit0/PASS12. Mocked/local unit scope only.
- `python -m compileall -q transformation tests/delta_runtime_probe.py`:exit0.
  `git diff --check`:exit0 (only repository LF/CRLF conversion warnings).

Final current checks also exit0:
`python -m compileall -q transformation tests/delta_runtime_probe.py tests/test_delta_plan.py tests/website_staging_probe.py tests/ebay_evidence_probe.py tests/etsy_staging_probe.py`;
`git -c core.safecrlf=false diff --check` (no output).
Current source hash from `python -c "from transformation.delta_plan import source_hash; print(source_hash())"`:
aae745b5ba456f6e5a3ef666ce26ed23776981d7a5056b520db340d49138a612.
`docker ps --filter label=de.probe=delta-runtime --format '{{.Names}} {{.Status}}'`
exit0/empty: no probe containers remain. Owner-project docker ps exit0: Airflow,
live-source, Etsy/eBay SIMs, report, receiver and PostgreSQL all healthy;
scheduler-observer running. This is container health only, not new SLA acceptance.
`git diff --cached --stat` empty; branch main/HEADaf82381 unchanged. All changes
remain unstaged, including pre-existing owner work and personal configs.

Remaining gates before activation: durable Airflow/source ownership integration
(including legacy/manual freeze admission, not just the shared physical key),
interrupted-attempt/publication audit; mapping/code
change, concurrent-source and recovery parity; reporting lineage checks; explicit
cold bootstrap; measured healthy warm collector-to-commit samples1/10 then100
changed orders/source on the retained baseline. Do not replace these with CTAS-only
timings or infer the old900 drain/cadence failures passed.

NEXT TASK: wire the verified experimental runner into the existing durable
polling coordinator behind an explicit OFF-by-default deployment option. Pin plan
identity in each polling cycle; retain actual Airflow owner annotation atomically
at freeze, existing five-attempt ledger and publication-attempt audit. Fence legacy
manual registration as well as new live cycles; avoid self-deadlocking two existing
coordinator sessions. No global build wait on the new path, short atomic publisher
only. Then disposable coordinator/recovery and full S01/report parity, explicit
cold bootstrap and real collector-to-commit1/10/100 qualification BEFORE activation.

### Final SQL live PASS; polling restored; no abort needed (2026-11-13)

Owner approved abort of1513a865-d10b-536d-a01f-135de14f73f5 and continuation.
Revalidation takes precedence over the previous interim snapshot: all owner
containers had stopped overnight. `docker compose --env-file .env --file
infra/compose.yaml start postgres` retained its volume; PG TCP ready. Exact batch
is now PUBLISHED, TRANSFORM and source-owner workflow SUCCEEDED; stored
published_at2026-11-12T14:59:12.713208UTC. Airflow run remains FAILED. No active
release barrier or active DAG run. Therefore NO ABORT WAS EXECUTED: never abort a
published batch. Earlier TESTED read was not its final committed state. The stored
published_at is the publisher-supplied clock, NOT an observed transaction commit
clock; do not infer it had committed before the earlier TESTED read/DAG timeout.
No task-state correction, attempt reset, owner-pointer deletion or data reset.

Started the existing Airflow container with the retained drain marker, then ran
the SAME guarded startup_lock/up command used below. Natural idle drain passed;
migrations remained additive and the final model is now in the recreated image:
Airflow started2026-11-13T03:25:53.002918UTC, evidence SHA
5bd4e0132837179039c0e7f30fb7b915cadcd89d4ee490c67400071ae6dff110;
FIFO SHA8fd93d882bb57885b608368db4cebd8253f2ecb65c3a8141eea6b583898ac901,
both match workspace. Guarded startup exited0/LIVE_SERVICES_READY; authenticated
source probes/import checks passed. All four periodic DAGs unpaused, drain marker
removed, healthchecked services healthy and observer running. No new source
campaign/load admitted. Actual command:

```powershell
python -u -c "from tools.s02_data.load import LocalDB; from tools.s02_data.live import up,startup_lock; from tools.s02_data.campaign import require_no_orphaned_release; d=LocalDB(); exec('with startup_lock():\n print(up(d,drain_guard=lambda:require_no_orphaned_release(d)),flush=True)')"
```

Populated full-runtime evidence from actual run_results.json and warehouse SQL:

| Batch / owner | dbt gate | dbt elapsed | eBay evidence node | Warehouse state |
| --- | --- | --- | --- | --- |
| 01e211e4-7a80-5624-9638-f9c1c17e5eec / eBay | 54passing,0nonpassing | 52.807982s | 1.597402s;13700rows | PUBLISHED,stored timestamp03:32:39.751654UTC |
| a367ec1c-ef94-52d4-af8f-79efe8d6ff9d / Etsy inbox | 54passing,0nonpassing | 78.360189s | 3.504091s;13700rows | PUBLISHED,stored timestamp03:35:51.320423UTC |

Etsy populated staging7345rows/7.187185s; cache2567payloads, versioncc843455...
and max cached_at2026-11-12T11:16:30.427479UTC unchanged: warm reuse is real.
New Website9d87bced-0ef4-507c-8b2a-a02e671f5dce also PUBLISHED. These are
normal scheduled retained-data executions, NOT a controlled end-to-end A/B or
a new900workload. Previous68.932/79.408s node observations remain valid; do not
turn their ratio into a whole-pipeline/capacity claim. Remaining measured work in
the inbox build includes eBay staging33.717873s, Website staging24.262484s and
eBay fulfillment-integrity test15.330299s (parallel timings must not be summed).

Actual FIFO: eBay release ticket03:29:09.992609->03:31:15.693421UTC, try1,
admitted before inbox03:29:21.119851 and new Website03:31:08.726262 tickets.
eBay task observed UP_FOR_RESCHEDULE/try1. At03:36:44UTC, Website/eBay/inbox
each have one new scheduled SUCCESS; recovery is still RUNNING (source waiting/
retry), not yet a fresh recovery SUCCESS. Normal cycles continue. Verify recovery
progress/source contention and cadence before admitting another qualification.

`python -m test_support.m08d_measure --report runtime/campaign-83fb057f5a0e48ed96a1d35043139e15/report.json`
exit0/PASS900orders/3801lines/904observed of1941planned versions,zero errors.
This rereads retained warehouse data only; it neither generates orders nor
regrades historical drain/cadence FAILs. No exact commit-clock claim.

Fresh offline checks: python tests/test_s02_live.py PASS30;
test_s02_campaign.py PASS18; test_m08d_measure.py PASS12; compileall PASS.
From fixtures/s01: python verify.py PASS10checks;
python -m unittest -v test_tools.py PASS10tests (fixtures only, not runtime).
git diff --check PASS. No stage/commit/push. Historical900FAILs unchanged.
No full C rerun, new qualification900, burst/soak or remote CI this turn. The
prior full3152-observation/13700-link SQL parity and disposable compile/build/
coordinator probes were not rerun today: source hashes unchanged, real populated
deployment checked instead. No background probe/rollout process remains; main
services intentionally stay live for owner review. Personal configs untouched.

### STOP: final SQL verified, deployment needs NEW exact orphan approval (2026-11-12)

Second guarded startup exited1 at its unchanged600s drain timeout, BEFORE image
recreation. No reset, kill, forced success, relaxed budget or hot patch. Waited
for old-image work to finish naturally. The last Etsy recovery owner
scheduled__2026-11-12T14:29:23.906059+00:00 instead hit its unchanged30min DAG
limit: start14:29:33.554592UTC, FAILED14:59:33.627433UTC. Batch
`1513a865-d10b-536d-a01f-135de14f73f5` remains TESTED, not published. Both cycle
(try5) and failed_workflow are SKIPPED; read-only pg_stat_activity shows no live
transform/publisher SQL. This is a NEW operator-recovery boundary, NOT covered
by owner approval for2b1c970b... . No abort of1513a865...has been performed.

Its retained artifact actually has54passing nodes/zero nonpassing, elapsed
119.039046s; old-image eBay evidence68.932251s, Etsy staging2.872386s and
etsy_constraints6.139895s. TESTED is not published or end-to-end success: prior
source/release waits consumed most of the DAG wall budget. Do not label this a
new load verdict or blame a failed dbt business check.

Final raw-link-first SQL5bd4e013... is ONLY IN WORKSPACE, proven by full retained
parity and disposable dbt/coordinator checks below; running image still has first
SQL7e68c0ea...and verified FIFO. Final rollout/full populated runtime timings for
5bd4e013...NOT RUN. No qualification900, burst/soak, full C or remoteCI this turn.
Historical900FAILs stand. All probe/rollout child processes have ended; no new
background test is pending. Main services healthy; PostgreSQL/SIM/data retained.
Deployment drain marker remains: Website/inbox paused, eBay/recovery unpaused for
old retries, periodic new scheduling suppressed by drain mode. Do not represent
the healthy container as normal automatic polling readiness at this checkpoint.

Next requires owner approval for official abort of ONLY1513a865...after rechecking
terminal owner, no active SQL and unchanged exact batch. Preserve raw/audit/
manifest and last-good, then retry the SAME guarded up at idle, verify hash and
new populated54-node release BEFORE any900rerun. Do not delete owner pointers or
reset attempts. Changes unstaged; no commit/push; personal configs/handoff untouched.

### Raw-link-first full retained parity PASS; guarded second rollout draining (2026-11-12)

Later read-only EXPLAIN captured the FIRST deployed SQL while Etsy batch
9061efab-a873-59a0-816b-a6cbf2457f09 held stable dependency relations:
staging3152rows; observations estimated1, eligible_raw estimated1, detail and
metadata branches Nested Loop. Actual running evidence statement was observed
CPU-active157s, no lock/I/O wait at that snapshot (not its final duration).
This identifies the cardinality/query-shape problem missing from the small
table-only probe. It is EXPLAIN without ANALYZE, not original operator timings.
Raw-link-first retained/ranked-view plans instead resolve raw branches with
Hash/Merge joins before the low-estimate ranked-version match. No planner GUC,
index, persistent DDL or execution-limit change was introduced.

`python tests/ebay_evidence_probe.py --container multi-channel-order-platform-airflow-1 --retained-limit 4000 --samples 2 --report runtime/ebay-evidence-20261112-full.json`
exit0/PASS11listed parity cases plus ranked-view parity. Actual retained sample
is the COMPLETE3152eBay observations in published batchec230b56... (not4000orders),
13700evidence links, exact five-column multiset equality. Statistics refreshed;
version-view rank=1 estimate additionally exercised. Two alternating plan samples:
retained old/new26792.893/1692.083ms; ranked-view29985.4375/3224.0645ms.
Synthetic100584.3615/64.4385ms;3008764.0205/165.3925ms. Shared-machine SQL
diagnostics only; no controlled full-build/load speedup claim. New ranked-view
plan estimates12versions but observes2436; raw links are resolved before that
join, with2116list-page function calls for2116relevant pages. This demonstrates
the tested query shape, not a reconstruction of the first slow live plan.
Final SQL SHA5bd4e0132837179039c0e7f30fb7b915cadcd89d4ee490c67400071ae6dff110.

`python tests/coordinator_probe.py --docker --report runtime/coordinator-ebay-link-first-20261112.json`
exit0/PASS13coordination SQL checks, dbt compile/full empty-input build and SDK
serialization. CLI diagnostic guards with retained-limit0 and samples5 each exit2
BEFORE Docker (expected refusal). compileall and repeated live30unit tests PASS.

Second guarded up (same command/limits) is draining old-image workflows. No
additional source data/faults/900campaign admitted; no additional abort approval
requested or used. New SQL hash is NOT deployed until that rollout finishes;
first deployed version's79.408s remains a genuine unfavorable observation.
Next verify deployed hash, populated54-node release and actual node durations.

### First live FIFO PASS; evidence full-build cost requires follow-up (2026-11-12)

Guarded startup exit0/LIVE_SERVICES_READY; Airflow started14:24:38.386648UTC.
FIFO/coordinator/polling hashes match workspace. First evidence SQL deployed SHA
7e68c0ea911e02c8503777b67ce0b68c0c1eb8495ed0055edc4a55cb64e3f4e8.
Website c0948365-1b90-5be4-8b7d-45dfdb89e05a PUBLISHED14:30:05.193803UTC,
54passing nodes; dbt21.397919s. Its eBay input is empty: do NOT treat its0.399s
evidence node as populated performance. Populated eBay
ec230b56-d8b0-52b9-8934-884061809096 PUBLISHED14:33:09.187923UTC,
54passing nodes, dbt122.448528s, evidence79.407632s. Prior retained old-model
batch5ca9d634...had evidence19.806673s/build90.043205s. Data/load/concurrent
diagnostics differ; not a controlled A/B, but the first rewrite is NOT demonstrated
as a whole-build improvement. Keep this unfavorable observation.

Real FIFO evidence: eBay ticket14:29:07.174779UTC (try1) admitted14:30:43.764739,
frozen14:30:43.834779, ahead of inbox ticket14:29:20.061458 and a new Website
ticket14:30:42.880695. Both actual eBay and recovery cycles observed
UP_FOR_RESCHEDULE/try1. Source/release clocks remain durable; no worker budget
or infrastructure limit increase.

Final-model probes: ebay-evidence-20261112-final.json PASS11cases/600nonempty
observations/2613links; however temp statistics were stale after synthetic input.
Follow-up analyzed.json captured EMPTY shared eBay staging during a Website build;
its old harness printed PASS, but zero retained rows are NOT retained parity or
performance evidence. Fixed the harness: immutable published raw/manifest,
nonempty assertion, refreshed statistics, same timeouts. No pipeline truth access.
`python tests/ebay_evidence_probe.py --container multi-channel-order-platform-airflow-1 --report runtime/ebay-evidence-20261112-manifest.json`
exit0/PASS11cases/600observations/2613links, frozen batch5ca9d634...;
retained SELECT medians old2607.1965/new367.8745ms (shared-machine diagnostic only).
One preceding final probe was interrupted by container recreation (nonzero exit,
no report); rerun after recreation passed. Never equate an interrupted run with PASS.
`python tests/coordinator_probe.py --docker --report runtime/coordinator-ebay-evidence-20261112-final.json`
exit0/PASS13coordination checks, compile, full empty build and SDK serialization.

Workspace follow-up now builds raw links BEFORE joining ranked versions, retaining
all original keys and final DISTINCT. This addresses a query-shape weakness;
the original slow plan was not captured. Read-only EXPLAIN immediately after
publication raced the next dbt rebuild (int_ebay_versions temporarily absent),
so do NOT invent an original-plan root cause. Small600probe link-first.json
PASS11/2613links, medians1897.291/153.919ms; larger4000/ranked-view and disposable
full dbt checks are running. This SECOND SQL revision is NOT deployed yet.
No900rerun, certification, staging/commit/push. Existing FAIL gates remain fixed.

### eBay evidence plans/parity PASS; FIFO + SQL rollout in progress (2026-11-12)

Owner requested continued optimization. Guarded live-up initially exited1,
refusing retained Etsy batch `2b1c970b-dd4c-5679-92dd-bff5463bd0cb` BUILDING
with terminal Airflow owner. Read-only checks: etsy_inbox owner
scheduled__2026-11-12T11:58:45.185887+00:00 FAILED, cycle/failed_workflow skipped,
no active warehouse SQL. Owner explicitly approved this exact abort. Ran official
website_workflow.run_stage(args,'abort') in the existing project venv under the
global release advisory lock, asserting UUID/owner/state and preserving20903
manifest members and all last-good publication pointers. Exit0/PASS; no retry
reset, clear, forced success or deletion. This approval covers no other batch.

Next SQL slice is eBay snapshot evidence, with no schema/identity/output changes.
Original300-order synthetic plan rejected538200 join pairs and expanded list
JSON180000times. Splitting OR alone retained repeated page work; the final query
uses three keyed UNION ALL paths, a once-per-page materialized expansion and
final DISTINCT. Baseline retained in tests/sql/ebay_evidence_before.sql.

`python tests/ebay_evidence_probe.py --container multi-channel-order-platform-airflow-1 --report runtime/ebay-evidence-20261112-v1.json`
exit0/PASS6parity cases (initial split-OR experiment, not final model).
`python tests/ebay_evidence_probe.py --container multi-channel-order-platform-airflow-1 --report runtime/ebay-evidence-20261112-v2.json`
exit0/PASS10cases: complete five-column multiset, empty/repeated acquisitions,
overlapping branches/account/hash scope, manifest membership, response errors,
missing arrays and invalid arrays (same22023). Retained600observations yield2613
evidence links identically. Four alternating ANALYZE/BUFFERS samples: median
old/new milliseconds100orders129.833/21.0745;300orders4156.830/170.5825;
retained6004932.502/248.757. Final300plan JSON function loops300, not180000.
These are rollback-only temp SELECT measurements under shared-machine load,
not full-build/CTAS/capacity ratios; no shared tables/functions were modified.

`python tests/coordinator_probe.py --docker --report runtime/coordinator-ebay-evidence-20261112.json`
exit0/PASS13real coordination SQL checks, full dbt compile/empty-input build and
four-DAG SDK serialization against the new evidence model. Business work remains
test-double in coordination checks; empty build is not populated correctness.
`python tests/test_s02_live.py` PASS30; test_s02_campaign.py PASS18;
test_m08d_measure.py PASS12; compileall and git diff --check PASS.
From fixtures/s01: python verify.py PASS10checks;
python -m unittest -v test_tools.py PASS10tests (offline fixtures only).

Reissued the SAME startup_lock/guarded up command recorded below, after the
approved recovery. Natural drain/rebuild remains in progress; no new900 load
admitted. Full populated release, deployed hash/readiness and actual FIFO runtime
still pending. Source windows/budgets/slots/tests unchanged. RemoteCI, full C,
unchanged900, burst/soak not run this turn. Leave all changes unstaged.

### Cache/reschedule live PASS; FIFO tested, NOT deployed yet (2026-11-12)

Final standard image rebuild after the hook repair exited0/LIVE_SERVICES_READY.
Airflow container started11:25:32.445789523UTC; five deployed files matched host
at that point, including deferred-hook model SHA7d4d82ce... . NONBLOCKING=true,
slots2. New Website batch `d8105f83-9a46-5e2a-8ec0-8561025e1ebb` PUBLISHED;
warm Etsy inbox batch `d17e6ddf-69ab-5e3c-8e54-2afc12d41b25` PUBLISHED
11:30:12.172076UTC:54passing nodes,zero nonpassing,dbt63.708868s,Etsy staging
3.346961s. Cache2567rows/versioncc843455ca31892be50a74473a898309,
max cached_at11:16:30.427479UTC unchanged across rebuild and warm execution.
Cold staging294.955s and warm3.347s have different population/concurrency/plan
conditions; do not claim a controlled end-to-end ratio from these observations.

Real task_instance snapshots show UP_FOR_RESCHEDULE with try_number1. Durable
inbox release wait11:27:45.282719->11:28:45.739935UTC and recovery source wait
11:28:00.063915->11:30:37.241684UTC finish SUCCEEDED with task_try_number1,
not a new clock per poke. Subsequent standard-image runs include SUCCESS for
all four DAGs (latest read:Website3,eBay2,inbox1,recovery2;other runs ongoing).
Current-data reread of retained900report via
`python -m test_support.m08d_measure --report runtime/campaign-83fb057f5a0e48ed96a1d35043139e15/report.json`
exit0/PASS900/3801lines/904observed versions,zero errors. This is NOT a new
900workload/performance run; historical FAIL remains unchanged.

Observed long release waits/new cycles overtaking an older cycle motivate a
small additional FIFO refinement in workspace. `orchestration/release_queue.py`
uses existing durable wait clocks: oldest logical-cycle ticket first, current
active batch recovery bypasses FIFO, expired tickets do not block other sources
or steal source ownership. Nonblocking CLI enforces the shared deployment wait
policy; no extra DDL/timeout increase. FIFO is NOT in the running image yet;
workspace coordinator/polling now intentionally differ from deployed hashes.

`python tests/coordinator_probe.py --docker --report runtime/coordinator-reuse-20261112-fifo-final.json`
exit0/PASS13real coordination SQL checks (business-stage test doubles), compile,
full empty-input dbt build and four-DAG SDK serialization. Includes no-overtaking
and expired-ticket/no-source-steal. Probe finished and cleaned disposable resources;
no new background test/rollout process is pending at this checkpoint.

Next: deploy FIFO via guarded drain/rebuild, verify fresh release/fairness, then
consider unchanged900 qualification separately. No more load admitted, no stage/
commit/push. Changes remain unstaged; owner local configs/handoff untouched.
Burst/soak/full C rerun/remote CI remain unrun. Main stays live for inspection.

### Populated cache build PASS; cold cost retained; rebuild retry at idle (2026-11-12)

After the deferred-hook repair, new Website batch
`acbb9100-c993-5746-a3a1-bdbc63d90f77` PUBLISHED and eBay subsequently TESTED/
released normally. Etsy inbox batch `b4d3e482-bbeb-581d-8fb4-5bf46519c77b`
has54passing nodes,zero nonpassing, dbt elapsed312.126886s, staging294.955443s
(includes cold pre-hook/cache population and CTAS). Cache now contains2567payloads,
max cached_at11:16:30.427479UTC; count observed11:23:42.323848UTC. This is
correctness evidence, NOT an improved cold-build or whole-pipeline speed claim.
Non-ANALYZE EXPLAIN of its compiled staging SELECT shows raw/input hash join
then cache PK index lookup. It does not reconstruct the original runtime plan
or isolate pre-hook versus CTAS CPU/I/O; do not invent that attribution.

Second guarded live-up exited1 at its unchanged600s drain timeout, before image
recreation. No forced task state, reset, abort or increased limit. By final read
task DAG runs were naturally idle; do not reclassify the timeout as PASS. Reissued
the SAME guarded startup command at idle to rebuild the image with the tested
deferred template. Warm-cache/full image runtime results still pending below.

### Runtime hook rendering bug fixed; normal retry/rebuild underway (2026-11-12)

First guarded rollout exited0/LIVE_SERVICES_READY, migrations010/011 applied,
NONBLOCKING=true and slots2. Five deployed code hashes initially matched host.
Actual task_instance snapshots show eBay/inbox/recovery cycle UP_FOR_RESCHEDULE,
try_number1: worker-free waiting is real, not only an SDK mock. Durable owners
for all three sources are present. However the first Website batch
`bb9ccf06-cb98-5be7-b04f-bc459fb57ba7` failed its dbt build gate: eager evaluation
of `config(pre_hook=populate_etsy_cache())` at parse time bound source relations to
the staging placeholder. Actual error: normalization_version missing from
stg_etsy_observations. Compile and manually rendered SQL had not caught this;
no candidate was allowed through the failed test gate. Original attempts/audit
remain retained; no forced success, clear or budget reset.

Changed config to deferred `pre_hook="{{ populate_etsy_cache() }}"`.
Expanded disposable probe to execute full dbt build, not only compile:
`python tests/coordinator_probe.py --docker --report runtime/coordinator-reuse-20261112-hook-runtime.json`
exit0/PASS: real coordination SQL, compile, full empty-input dbt build and SDK
four-DAG serialization. Empty-input build validates hook resolution/materialization,
NOT populated warehouse business correctness or load. Added this gate to the
reproducible probe so future hook regressions cannot hide behind compile PASS.

To unblock legitimate retries without restarting active workers, atomically
replaced ONLY the tested staging SQL file during a verified no-dbt-process gap.
Docker cp staged a unique /tmp file; an in-container guard checked no process with
an executable ending /bin/dbt and expected old target SHAaf4b5993..., then
os.replace moved the file to its exact model path. Exit0,new SHA
`7d4d82cef2378b4f79ff056cc42631ac8dc06bab15e28827ddcd007a0bae7ccd`, matching host.
No SQL/session/task-state mutation. This is a documented deployment repair,
not a frozen load experiment. Started guarded live-up again to naturally drain
and rebuild the image with that same fix; final populated release still pending.

### Final isolated gates PASS; guarded rollout started (2026-11-12)

`python tests/etsy_staging_probe.py --report runtime/etsy-cache-20261112-final.json`
exit0/PASS8parity cases and4negative cases, including numeric1/1.0 representation
mismatch refusal. Warm SELECT medians300raw:old1870.998/new8.434ms. This EXCLUDES
cache population/pre-hook/DDL/full workflow; not an end-to-end performance claim.
`python tests/coordinator_probe.py --docker --report runtime/coordinator-reuse-20261112-rollout.json`
exit0/PASS, including actual legacy claim_slot refusal, completed-cycle idempotency,
durable waiting/restart/official abort checks, full dbt compile and four-DAG SDK
serialization. Limited mounts and private-network cleanup verified by the harness.
These are not a real scheduler run or a new load verdict.

Started guarded rollout with the existing startup_lock and orphan-release guard:
`python -u -c "from tools.s02_data.load import LocalDB; from tools.s02_data.live import up,startup_lock; from tools.s02_data.campaign import require_no_orphaned_release; d=LocalDB(); exec('with startup_lock():\n print(up(d,drain_guard=lambda:require_no_orphaned_release(d)),flush=True)')"`.
Currently draining old live tasks before migrations010/011 and image update.
No new source workload,900rerun or fault admitted. Runtime readiness/full release/
actual scheduler reschedule evidence still pending; record final outcome below.

### Priorities1/2 implemented; isolated checks PASS, rollout pending (2026-11-12)

Owner approved canonical reuse and worker-free coordinator waits. Finalized
fields/constraints in05_TARGET_SCHEMA.md BEFORE migrations010/011. Design,
ownership/recovery and rollout:20_M08D_REUSE_COORDINATION.md. Etsy cache is
append-only, scoped by source/account/byte hash/code version, and rejoins every
raw in the unchanged manifest. Source canonical fingerprint/mapping/history are
unchanged; mismatching parsed representations fail closed. Live-only sensor
reschedules exit75 without holding worker/session locks or consuming a business
retry. Durable source owner and per-phase/actual-try wait clocks survive pokes;
legacy/S01 remain blocking and respect active live owners. Shared build/release
is still serialized. Guard also refuses orphan source ownership before freeze.

Checks so far (no new owner load admitted):
- `python tests/etsy_staging_probe.py --report runtime/etsy-cache-20261112.json`
  exit0:8parity cases,3negative cases, warm SELECT benchmarks only. This does
  not measure cache population, full dbt or capacity. Numeric-scale guard was
  subsequently tightened; final probe still pending below.
- `python tests/coordinator_probe.py --docker --report runtime/coordinator-reuse-20261112.json`
  exit0:11real coordination SQL checks with business-stage test doubles, installed
  SDK sensor/poke checks. Later expanded probes: v2 failed because this Airflow
  uses DagSerialization, not SerializedDAG.from_dict; fixed API and template-field
  serialization. One v3 startup failed at temporary init PG socket; changed
  readiness to final TCP server. v3 and final.json then exit0/PASS, including
  compile of the real complete dbt project and four-DAG serialize/deserialize.
  Each test uses uniquely labeled private PG/worker/network, no main scheduler,
  reset, owner-volume deletion or database credentials. Final harness mounts only
  code/config directories, not .env/runtime; final verification pending below.
- Network-disabled project-venv worker: unittest discovery for
  test_batch_owner.py,test_m06_cycle.py,test_etsy_drain.py,test_marketplace_pagination.py
  exit0/PASS33. `python tests/test_s02_live.py` PASS30;
  `python tests/test_s02_campaign.py` PASS18; test_m08d_measure.py PASS12,
  test_m08d_envelope.py PASS11,test_m06_scheduling.py PASS4.
- From fixtures/s01: `python verify.py` PASS10checks;
  `python -m unittest -v test_tools.py` PASS10tests. Compileall and diff-check PASS.

No new main deployment/runtime reschedule/full release or unchanged900 result
yet. Main still uses the preceding image. Follow the guarded drain/migrate/build
path only after isolated final checks. Do not turn warm SELECT speedups into
M08D certification; previous900FAIL remains. Changes unstaged, no commit/push.

### Same900 drain/cadence FAIL; later reconciliation PASS (2026-11-12)

After the approved exact orphan abort and full54-node deployment gate, ran:

```powershell
python -u -m tools.s02_data campaign --config tools/s02_data/config/campaign_rate_900.json --confirm-local
```

Exit1/FAILED, `runtime/campaign-83fb057f5a0e48ed96a1d35043139e15/report.json`.
STARTUP08:41:26.389013UTC; admission published_at08:55:50.179091UTC,
ADMITTED08:55:54.943355UTC. Dataset `campaign-rate-900-2424e0b7ba6e`, source
campaign `78eebfebc47e`;900orders/1941planned versions/5952844serialized bytes,
300orders per source. Fixed source end09:05:53UTC;900s drain deadline09:20:53UTC.
Failure finished09:21:09.357201UTC (16:21:09 local). No source/gate/worker/budget
changes, fault injection, reset or load escalation during this measurement.

Final gate SQL snapshot09:21:08.289924UTC: Website300/300,Etsy300/300,eBay161/300
final states;761/900current,139eligible eBay orders still pending. Future source
versions0,pending sends0. No complete observed drain within budget; final sample
elapsed915.289924s includes polling overhead beyond900s. Qualifying scheduled
successes Website/eBay/inbox/recovery1/1/1/0 versus2EACH; actual DAG start must
be within the immutable admission/source window. BOTH drain and cadence fail.
Report remains FAILED/measurement INCOMPLETE; missed intermediate history is
not fabricated. Exact source-commit latency/p95 remain NOT_MEASURED.

Independent read-only command AFTER failure:

```powershell
python -m test_support.m08d_measure --report runtime/campaign-83fb057f5a0e48ed96a1d35043139e15/report.json
```

Exit0/PASS900orders/3801lines/904observed versions of1941planned,zero errors.
This reads current warehouse state, NOT deadline state, and cannot repair failed
cadence/drain clocks. A single-statement reread09:22:51.674727UTC confirms300/300
final per source. eBay batch `b4891ec8-681c-52fa-b319-d06872d5c133` has
published_at09:21:30.889211UTC, AFTER the deadline; this field is not exact SQL
commit time. These are late catch-up observations, not an in-budget drain PASS.

All78 frozen code hashes match at campaign end.58resource samples: peak reported
stack memory2307609589bytes (~2.15GiB), peak DB growth91783168bytes (~87.53MiB),
no ceiling failure. Retained baseline6679orders/29023lines/6907history versions/
32319raw. Warmer history/scheduler phase differ from earlier runs: no controlled
whole-pipeline speedup or hardware-capacity claim from the isolated SQL result.
RAM below this ceiling does not prove CPU/I/O/executor resources unconstrained.

Completed stages (start>=admission AND finish<=deadline): Website collect1..4s,
build65..83s,publish23..46s; eBay collect72..77s,build107s; Etsy collect2..297s,
build122..237s,publish19..30s. Max source-slot215s,release-slot111s. One39s eBay
collect attempt FAILED with `ValueError: mutable page total; reconcile window`,
then retried successfully. Raw HTTP error-audit counter0 does NOT imply no
application retries. These timings cover concurrent stack work, not exclusive
campaign CPU attribution; unfinished stages are excluded from duration ranges.

Eight batches frozen>=admission AND published<=deadline each have54dbt nodes,
zero nonpassing. Etsy-source staging88.539/140.600/130.817/70.747s;
Website staging9.544..25.502s across these eight artifacts. Full retained
run_results are under runtime/dbt/<batch_id>/. Stage/process/queue time is not
interchangeable with one SQL duration; no full-build/test failure in these releases.

Final `docker ps --format '{{.Names}} {{.Status}}'`: seven healthchecked services
healthy, observer Up. Leave services/data/schedules for owner inspection. No
post-failure reset, abort, pause or task-state manipulation. `git diff --check`
PASS; changes unstaged, no commit/push. Full C rerun,cold runtime S01,Website600
timeout reproduction,burst/soak and remote CI NOT RUN this turn.

M08D remains incomplete. Stop escalation and blind900 repetition. Next bounded
design/profiling review: repeated normalization of retained raw per batch, full
dbt rebuild cost and coordinator waits occupying the two executor slots. Any
persistent parse cache, changed batch membership, deferred waits or parallel
release needs a reviewed design/parity/recovery plan; never silently weaken
manifests, source interfaces, business tests or atomic publication.

### Etsy SQL deployed/full54 PASS; unchanged900 starting (2026-11-12)

Guarded startup after the approved orphan abort exited0/LIVE_SERVICES_READY.
Normal drain completed before rebuild. Seven healthchecked services healthy,
observer running; all four live DAGs unpaused. Main data retained. Airflow
container started2026-11-12T08:35:28.608870637UTC; host/container Etsy SQL SHA256
both `12b556cbc12afc8b7069d089b5e24cbc3d91d72a2cb233b9b4a9f1501b8d87ab`.
Effective executor slots2, eBay/Etsy list pages50/50; no settings/gate changes.

First post-deployment Etsy batch `24d5d882-4f4c-597d-80ef-b98c9063e154`
PUBLISHED at2026-11-12T08:40:18.136523UTC. Local
`runtime/dbt/24d5d882-4f4c-597d-80ef-b98c9063e154/run_results.json` has54nodes,
zero nonpassing, elapsed71.867917s, Etsy staging54.919993s. This proves full
dbt/release, not load acceptance or a controlled A/B speedup on retained history.
Offline commands this turn: `python tests/test_s02_campaign.py` PASS18;
`python tests/test_m08d_measure.py` PASS12; `python tests/test_m08d_envelope.py`
PASS11 (41total; no DB writes by these regression tests).

Next execution: `python -u -m tools.s02_data campaign --config tools/s02_data/config/campaign_rate_900.json --confirm-local`.
Its own normal startup/drain and preflight remain enabled. No source/gate/budget
changes. Record actual report and final outcomes below; do not infer PASS from
SQL timings or earlier final-data reconciliation.

### Approved exact orphan abort completed; deployment draining (2026-11-12)

Owner approved abort of `e677bf86-946b-5556-be1a-40e09a28aa21`. Reverified owner
FAILED, both tasks SKIPPED and no active transform/publisher SQL sessions.
Invoked official `website_workflow.run_stage(args,'abort')` inside the existing
Airflow project venv, under `pg_try_advisory_lock(hashtext('platform-release'))`,
with the original execution `poll:etsy_sim:scheduled__2026-11-08T05:57:00.091022+00:00:drain`.
Asserted derived batch UUID and retained owner/context before mutation. Exit0:
exact batch FAILED,18781manifest members unchanged and all publication_state
batch pointers unchanged under the release lock. No deletion, task clear,
retry-budget reset or forced success. Raw/audit evidence remains retained.

Started guarded deployment again:
`python -u -c "from tools.s02_data.load import LocalDB; from tools.s02_data.live import up,startup_lock; from tools.s02_data.campaign import require_no_orphaned_release; d=LocalDB(); exec('with startup_lock():\n print(up(d,drain_guard=lambda:require_no_orphaned_release(d)),flush=True)')"`.
Currently draining normally; no new900 source data admitted. Final deployment,
full dbt/release and unchanged900 outcomes must be recorded when they finish.

### Deployment refused at retained orphan after scheduler resume (2026-11-12)

Owner requested continuation: deploy the SQL reuse change, prove full dbt/release,
then retry unchanged900. No new source batch has been prepared/admitted. Docker
initially had no running containers. Started only the retained live dependencies
and resumed the existing stopped live Airflow through the normal drain flag path.
The exact Python entrypoint was:

```powershell
python -u -c "from tools.s02_data.load import LocalDB; from tools.s02_data.live import compose,up,startup_lock; from tools.s02_data.campaign import no_disposable_services,require_no_orphaned_release,resume_retained_airflow; db=LocalDB(); no_disposable_services(); print('Starting retained live dependencies; no reset',flush=True); compose(db,['up','--detach','--wait','--wait-timeout','180','postgres','ebay-sim','etsy-sim','etsy-receiver'],timeout=210); require_no_orphaned_release(db); resume_retained_airflow(db); print('Resume preflight complete',flush=True); exec('with startup_lock():\n print(up(db,drain_guard=lambda:require_no_orphaned_release(db)),flush=True)')"
```

Exit1 at the existing orphan guard, BEFORE image rebuild, migrations or new data
admission. Initial ownership check passed, but normal Airflow resume subsequently
marked the retained owner terminal: batch `e677bf86-946b-5556-be1a-40e09a28aa21`
is still BUILDING; owner `etsy_inbox` /
`scheduled__2026-11-08T05:57:00.091022+00:00` is FAILED, ending
2026-11-12T08:22:02.231413UTC. Read-only task_instance query by dag_id/run_id
confirms both owner tasks SKIPPED (`cycle`, `failed_workflow`); pg_stat_activity
shows no non-idle platform_transform/platform_publisher sessions in data_platform.
An initial diagnostic using task_instance.dag_run_id failed (not a column in this
metadata schema); corrected query above succeeded. No task/budget state changed.

This is an existing terminal-owner release barrier, NOT a dbt test failure of
the new SQL. Retain the guard, last-good, raw/audit/manifest and failure evidence.
No automatic abort, task clear, force-success, reset or volume deletion. Owner
approval is needed for official abort of THIS exact retained batch before retry.
The resume path leaves its parse-time polling-drain flag in place; live-up did
not reach schedule restoration or rebuild. Current services and health were
checked with `docker ps --format '{{.Names}} {{.Status}}'`; no report/observer or
live-source startup was requested by this failed deployment path. Full54-node
dbt gate, deployment hashes and unchanged900 qualification NOT RUN this turn.
Leave source changes unstaged; no commit/push. Next: approve exact orphan abort,
reverify owner/tasks/sessions, invoke official workflow abort (preserving audits),
then retry guarded startup. Do not count this refused startup as a900 load run.

### Etsy staging reuse: disposable SQL PASS, deployment pending (2026-11-12)

Continued from main `af82381`. The latest900 workload still fails scheduled-cycle
cadence, not final data reconciliation. The recorded Etsy staging81..109s/node
is the next bounded target. Current model evaluated recursive source normalization
twice per acquisition: once for order_json and again for its fingerprint. A
statement-local MATERIALIZED CTE now reuses the unchanged canonical JSON. No
source/stable DDL, function/fingerprint, raw audit, manifest filter, worker count,
lock, budget or acceptance-gate change. All output columns remain unchanged.

Checks on this working tree:

- `docker ps --format '{{.Names}} {{.Status}}'`: sandbox initially denied Docker
  config/API access; approved read succeeded with no running containers. Did not
  start/stop the main stack or change its DAGs/config/data.
- `python -c "import psycopg,jinja2; print('dependencies available')"`: failed,
  local psycopg missing. Added a stdlib-only Docker/psql probe instead of installing
  packages or depending on the main Airflow container.
- `python tests/etsy_staging_probe.py --report runtime/etsy-staging-20261112.json`:
  initial exit1 Windows cp1258 UnicodeEncodeError in the Unicode case; disposable
  container cleanup ran. Fixed subprocess encoding explicitly to UTF-8. Same
  command then exit0/PASS; report retained at the stated path. PostgreSQL16,
  network disabled, no host ports/owner volumes, tmpfs data,512MiB/one CPU.
  Complete old/new row multiset parity and independent Python payload/hash checks:
  S01(2), alias/reordered lines/Unicode(1), empty(1), missing(1), repeated raw(4),
  wrong-account excluded(0). Alias conflict and duplicate transaction identity
  retain identical errors. Existing macro functions are exercised unchanged.
  Four alternating EXPLAIN samples per variant:10receipts old63.5615/new42.781ms;
  100receipts old361.7285/new200.291ms;300receipts old1066.304/new696.946ms
  (medians). Synthetic fixture-sized receipts, not retained multi-day history;
  no end-to-end/capacity claim. Probe removes only its label-verified container.
- From `fixtures/s01`: `python verify.py` exit0/PASS10 offline checks;
  `python -m unittest -v test_tools.py` exit0/PASS10 tests.
- `python -m py_compile tests/etsy_staging_probe.py`: exit0.
- `git diff --check`: exit0. Changes left unstaged; no commit/push requested.

NOT RUN: old Website600-order timeout reproduction, full dbt54-node/release
with this Etsy change, unchanged900 qualification, burst/soak, remote CI. Docker
main is currently stopped; this slice deliberately avoids silently restarting
the whole workload. Next deploy through the normal guarded live-up/drain path,
verify complete dbt/release and then rerun the unchanged900 envelope, retaining
all prior failed reports. M08D is still incomplete; SQL speedup alone cannot
turn the cadence failure into PASS.

### Grouped feature checkpoint requested by owner (2026-11-12)

Owner requested one feature-oriented checkpoint for the remaining S02 campaign,
recovery/pagination, transform ownership and Website staging work, without more
test runs or file-version splitting. Previous SIM delivery commit: `87f2df2`.
This checkpoint is NOT M08D completion: the retained 900-order run passed final
data/drain checks but failed the required scheduled-cycle cadence gate below.

The subsequent commit-review Website probe command
`python tests/website_staging_probe.py --container multi-channel-order-platform-airflow-1 --report runtime/website-staging-commit-review.json`
exited 1: PostgreSQL statement timeout (90 seconds) during the 600-order EXPLAIN
sample; no final PASS report was written. Earlier samples completed; this does
not replace the earlier successful runtime/parity evidence or certify a new run.
S01 checks on the exact LF index export passed: `python verify.py` (10 checks)
and `python -m unittest -v test_tools.py` (10 tests). An initial Windows CRLF
snapshot export failed fixture checksums; exporting with
`git -c core.autocrlf=false checkout-index` restored the unchanged Git blob bytes.
No additional integration/load checks were run for this grouped commit, per
owner request. Credentials, runtime evidence, handoff artifacts and personal
local_now/quick_6min configs remain outside the commit. Next: review the retained
timeout and cadence evidence before claiming full M08D acceptance.

<!-- stable-delivery-checkpoint:start -->
### Stable SIM delivery partial checkpoint (2026-11-08)

Owner requested selective commits, not M08D completion. Selected only prepared
Etsy delay/reorder/repeat/omission schedules: schema004, generator/loader,
durable sender, live-worker hook, legacy replay refusal, inspection/runbook/tests.
Logical notifications/source versions stay separate from physical sends; old
profiles are unchanged. See tools/s02_data/DELIVERY.md for fields and boundaries.
Campaign/load tuning, Etsy reconciliation/paging, local configs and runtime
artifacts are intentionally outside this checkpoint.

Verified the INDEX snapshot at runtime/staged-review-sim-1e1cbe48, not the broader
working tree: `python tests/test_s02_delivery.py` PASS9;
`python -m tools.s02_data --help` PASS (no campaign command in this slice);
`python -m compileall -q tools/s02_data simulator tests/test_s02_delivery.py tests/sim_delivery_probe.py`
PASS; `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/check_sim_delivery.ps1`
exit0/PASS, cleanup PASS. Evidence under that snapshot's
runtime/sim-delivery-a486198e7e4c.json:8logical planned messages,2omitted,
10planned sends,12actual sends including500/lost-ACK retries,6logical messages
received,10completed sends. Loader/reapply/legacy/API/signature/RLS/seal/FK and
completed-no-resend checks pass. Only unique disposable test containers/network
removed; no owner data/ports/credentials/scheduler changes. This is NOT full
warehouse/Airflow/load acceptance or certification of the remaining M08C/D work.
<!-- stable-delivery-checkpoint:end -->

### SQL/ownership deployed; unchanged 900 data/drain PASS, cadence FAIL

Second live-up exit0/LIVE_SERVICES_READY, natural drain and image recreation;
no additional orphan abort. Container/host hashes match: batch.py f31c391b...,
website_workflow.py b98b0aba..., Website staging132afb66... . A new BUILDING
batchfe5da49a-30f6-5479-8af6-d3be37c3f443 has real Website DAG/run owner populated.
Unchanged900 command started again: runtime/campaign-262f579dff4943a1bc8b9ef0fb03a5cb/report.json,
STARTUP2026-11-08T04:47:02.280918UTC. Startup completed without false orphan
refusal; admitted campaign0675510a1970/dataset campaign-rate-900-d546999e26f7,
published_at04:57:47.861079UTC, ADMITTED event04:57:51.179833UTC. Plan900orders,
1941source versions/5902654bytes,300orders per source,600s exposure. Fixed source
window end05:07:50UTC; max900s drain to05:22:50UTC, >=2qualifying successes for
each of Website/eBay/inbox/recovery. Same2slots/60s/page50 settings,78code hashes.
Final exit1/FAILED at2026-11-08T05:22:52.844608UTC (12:22:52 local), measurement
INCOMPLETE/load_assessment FAIL. Eligible Website/eBay/inbox/recovery successes
1/1/1/1 versus2 EACH, with DAG start inside the fixed source window. All four
qualifying runs eventually succeed; later-starting successes do not count.
No gate/budget/worker/code changes during measurement and no load escalation.

All900 final versions first observed05:20:21.029038UTC:751.029038s after source
end, within900s. Last sampler05:22:50.861265UTC (900.861265s), pending sends0,
future source versions0, final backlog0. The combined drain/cycle error is due
to cadence, not late drain. Exact source-commit latency/p95 remain unmeasured;
normal monitor.finish is blocked by the cadence gate, so do not invent them.

Independent read-only command:

```powershell
python -m test_support.m08d_measure --report runtime/campaign-262f579dff4943a1bc8b9ef0fb03a5cb/report.json
```

Exit0/PASS900orders/3801lines/907observed versions of1941planned, zero errors.
History validates only observations; do not fabricate skipped intermediate states.
All78final code hashes match current files.63resource samples: peak reported
stack memory2335029852bytes (~2.17GiB), peak total DB growth86900736bytes
(~82.87MiB); no resource-ceiling failure. Warm retained baseline5779orders,
25222lines,6000history versions,28616raw. Retained history/phase differ from
previous900runs: no controlled end-to-end speedup or hardware-ceiling claim.

Completed-stage telemetry with BOTH start>=admission and finish<=deadline:
Website collect1..2s/freeze<1..1s/build56..70s/publish19..26s;
eBay collect71..84s/freeze~1s/build73..85s/publish13..15s;
Etsy collect1..159s/freeze1..3s/build116..162s/publish14..24s.
Max source-slot wait235s, release-slot wait177s. One eBay collect attempt fails
with `ValueError: mutable page total; reconcile window` and retries successfully;
HTTP error-audit counter0 is NOT a claim of no application-level retries.
Telemetry window is not exclusive CPU/HTTP attribution to this dataset.

Ten published batches frozen>=admission/published<=deadline have54dbt nodes EACH,
zero nonpassing. dbt elapsed24.019..125.206s; Website staging5.926..18.899s;
Etsy staging81.541..109.353s in Etsy batches (near-empty in other source batches).
Examples: Website8adc2fa7-6ca8-5176-afd1-0e49f50bf7ea elapsed24.019s;
Etsy4b8f59cf-1d30-52c5-90e6-8aaa372009c9 elapsed125.206s, Etsy staging109.353s;
eBayec83fa01-3442-568c-b109-78cb7587cff0 elapsed54.683s. Full stage times also
include process startup/transition overhead; never equate them to one SQL time.

Final health: seven healthchecked services healthy, observer Up; four polling
DAGs unpaused. Batchbb099fff-93bf-5494-9c4d-11643d768bd5 was BUILDING at the ops
inspection; its eBay owner scheduled__2026-11-08T05:20:15.461442+00:00 was later
confirmed SUCCESS. No abort of this live batch.
45selected regressions, S01 verify10checks/test_tools10tests, compile and
`git -c core.safecrlf=false diff --check` PASS. All task changes unstaged; no
commit/push, main reset, volume deletion or source-contract/fingerprint change.
Remote CI,cold S01 runtime acceptance,full C rerun,burst/soak NOT run.

M08D remains incomplete. Stop escalation. Next bounded review: Etsy staging
repeated parsing/canonicalization and source/release waits occupying executor
slots, using recorded node/queue evidence. Keep atomic release and actual source
observation contracts; design/prove any incremental or orchestration change
before implementation rather than merely increasing workers/budgets.

### SQL deployed/full54 gate PASS; startup ownership race fixed before new load

2026-11-08 live-up exit0/LIVE_SERVICES_READY after natural drain, with no active
batch at recreation. Container SQL hash matches measured132afb66...; settings
remain2slots/60s/page50/50. First new batch0c79d28e-abe0-5b7c-b9ab-183afcd59f4c
PUBLISHED:54nodes,zero nonpassing,dbt elapsed74.587s. Website staging5.348s,
versions0.422s; Etsy staging65.949s is the slowest node in this sample. This
confirms full release of the SQL, not complete load acceptance.

`python -m tools.s02_data campaign --config tools/s02_data/config/campaign_rate_900.json --confirm-local`
first retry exit1 before admission. Retain runtime/campaign-73a90b8c3a2f4a4b99cec8a8d1ed8ffc/report.json:
STARTUP04:31:56.829527UTC, STOPPED04:32:05.376581UTC, no dataset admitted. Guard
reported new Website batchd0e0ab2a-291b-539f-b26e-3220f2ff25c0 as orphan just
after freeze04:32:04.684713UTC. Immediate inspection proved owner RUNNING and
dbt active: DO NOT abort this live batch. The child TRANSFORM INSERT initially
omitted owner fields; finally-time annotation filled them later, exposing a
cross-database inspection race. This is a startup refusal, not a failed900 load.

Existing-column contract finalized in05_TARGET_SCHEMA.md before code: populate
paired actual Airflow DAG/run IDs in the initial TRANSFORM INSERT transaction.
Workflow forwards both IDs for direct-connection and subprocess freeze; manual
CLI without owner remains valid, partial pairs rejected before DB writes. No
DDL, business-SQL change or guard relaxation. Campaign guard additionally
rereads the exact active barrier before declaring a terminal/missing owner an
orphan; already-published/failed batches are not barriers. A newly annotated
owner is revalidated; a true retained orphan still refuses and never auto-aborts.

Four ownership regression tests PASS against newly loaded modules in a separate
container Python test process (mock DB; no worker code overwritten). Campaign
tests now18PASS including resolved-barrier/late-annotation/true-orphan cases;
with12measurement+11envelope tests,45distinct selected tests PASS. S01 offline
verify10checks and test_tools10tests PASS again. Compile/diff-check PASS.
Second `python -m tools.s02_data live-up` is draining before deployment of the
ownership fix. No new900 admission yet; record eventual result below. Previous
load FAILs and first startup refusal remain retained, never relabeled PASS.

### Approved orphan abort completed; safe deployment drain in progress (2026-11-08)

Owner explicitly approved official abort of batch5d030239-d64c-58ae-895b-
6d5804464e5f and continuation. Rechecked exact Airflow owner FAILED/tasks SKIPPED
and zero publisher sessions. `orchestration.polling --source etsy_sim
--collection-mode drain --execution-id scheduled__2026-11-07T15:26:00.468032+00:00:drain
--airflow-run-id scheduled__2026-11-07T15:26:00.468032+00:00 --dag-id etsy_inbox
--reuse-cycle-config --abort --wait-seconds 30` timed out at source_slot (exit1),
because newer cycles held the source slot waiting for this orphan release;
no business attempt consumed. Then called the existing official
website_workflow.run_stage(args,'abort') for the verified original UUID-derived
execution, under pg_try_advisory_lock('platform-release') using the transform
connection. Exit0; exact batch FAILED, raw/audit/manifest retained, no forced
success/reset/deletion. Official abort does not rewrite the old publish attempt
audit: its stale RUNNING row remains historical evidence, not an active process.

Started only existing postgres/ebay-sim/etsy-sim/etsy-receiver through live Compose,
then `python -m tools.s02_data live-up` (currently draining existing DAG runs).
No new900 data admitted yet. Latest new batch773dc8b8-90a8-50c3-a9e1-d52a622ff325
BUILDING; allow natural completion before image replacement. Runtime results
below remain pending until live-up, full dbt gate and unchanged900 finish.

`python tests/test_s02_campaign.py` PASS16; `python tests/test_m08d_measure.py`
PASS12; `python tests/test_m08d_envelope.py` PASS11 (39total). Compile and
`git -c core.safecrlf=false diff --check` PASS; index still empty.

### Deployment/900 continuation stopped at orphan release preflight (2026-11-08)

Owner authorized deploying the Website SQL and rerunning unchanged900. Read-only
preflight found active TESTED batch5d030239-d64c-58ae-895b-6d5804464e5f, owned by
etsy_inbox / scheduled__2026-11-07T15:26:00.468032+00:00. Airflow dag_run is FAILED
(end2026-11-08T03:43:14.359441UTC); its cycle and failed_workflow tasks are SKIPPED.
Durable build/test succeeded, publish attempt1 is stale RUNNING; no
platform_publisher session remains. Last-good Etsy publication is aace2c82-d35d-
5fc8-af58-2c582d8f0afd, not the orphan batch. Other cycles have measured300s
release-slot timeouts. This is an orphan release barrier, not a new load result.

Checks via `docker ps --format "{{.Names}} {{.Status}}"` and read-only psql in
postgres container: five services running (Airflow, receiver, source worker,
PostgreSQL healthy; observer Up); marketplace SIM containers are not running.
Queried active ops.transform_batches with pipeline owner, exact Airflow dag_run
and task_instance by dag_id/run_id, ops.task_attempts, advisory pg_locks and
pg_stat_activity; zero publisher sessions. Initial diagnostic task join used
nonexistent dag_run_id and was corrected to the actual run_id key; no writes.

No image build/recreation, drain/pause, abort, DB update, new generation/admission
or900 test performed. Next requires owner approval for the official workflow
abort of ONLY5d030239-d64c-58ae-895b-6d5804464e5f after another owner/idle recheck.
Retain raw/audit/manifest, last-good and attempt budgets; do not force success.
Then resume safe drain/startup/deployment, full dbt/publication verification and
unchanged900. Prior approval for different orphan batch IDs does not authorize
this one. SQL diagnostic PASS remains valid; M08D remains incomplete.

### M08D Website JSON SQL refinement verified in temporary PostgreSQL objects

Owner authorized the profiling-first proposal. Bounded scope: rewrite only
stg_website_observations child expansion; no DDL/output/type/fingerprint change,
incremental cache, model selection, worker change, parallel release, chunk commit
or stored procedure. main/HEAD4c12bc2 and pre-existing dirty work preserved.
The target output remains raw_record_id/source_system/source_account_id/
acquired_at/byte_sha256/order_json/business_payload/content_fingerprint with the
same types/grain and canonical identity. Group children by raw/order, preserve
array ordinality and duplicate evidence. Distinct shipment membership retains
the original EXISTS semantics, including invalid repeated/cross-order shipment
IDs; materialized shipment-item expansion prevents planner-driven re-expansion.

Exact successful runtime commands from repository root:

```powershell
python tests/website_staging_probe.py --container multi-channel-order-platform-airflow-1 --report runtime/website-staging-20261108-v1.json
python tests/website_staging_probe.py --container multi-channel-order-platform-airflow-1 --report runtime/website-staging-20261108-v2.json
python -m compileall -q tests/website_staging_probe.py
git -c core.safecrlf=false diff --check
```

All exit0. The first report PASSed parity, but its plan still expanded shipment
items600times at600orders. Retained that report, added a materialized statement
CTE, then reran v2. Both probes use current host SQL passed through subprocess
stdin to the existing project venv; only session-temp tables/functions are
written and rolled back. No shared build/core/mart/ops or scheduler mutation.
An earlier ad-hoc PowerShell ConvertTo-Json/pipe attempt produced no evidence and
was interrupted (exit1); replaced by the reproducible Python runner, not counted
as a test PASS. Host Python lacks Jinja2; the runner intentionally uses existing
container dependencies, with no host installation or image replacement.

Final v2 full-row bidirectional EXCEPT ALL parity: S01 4rows, edge cases5,
missing children1, empty orders0, repeated acquisitions10, Unicode1 and retained
raw200acquisitions/2091order observations. Independent Python shaping/canonical
SHA256 checks PASS for synthetic/S01 cases. JSON null/object/string child arrays
still fail with SQLSTATE22023 in BOTH variants (three negative checks). No
unobserved snapshots or source versions were created in shared storage.

Alternating EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON), four samples/variant/size:

| Orders in one synthetic raw | Old median ms | New median ms |
| --- | ---: | ---: |
| 1 | 1.1605 | 1.1565 |
| 10 | 9.304 | 6.7565 |
| 100 | 280.891 | 69.6195 |
| 300 | 2643.8465 | 287.4395 |
| 600 | 9190.573 | 432.450 |

All final new-plan array Function Scan Actual Loops=1 for each single-raw size;
manual report reread/hash assertions exit0. Final model text SHA256
132afb66b917ff8bee4b32e5a556c7131b14c7a020e46ca5a539838eb40a6a07 matches
measured SQL. About21.25x at600 is this SELECT diagnostic ONLY, not a whole-dbt
or pipeline throughput claim; shared services remained active during profiling.
Reports contain execution plans/buffers and remain ignored runtime artifacts.

From fixtures/s01: `python verify.py` exit0/PASS10offline checks;
`python -m unittest -v test_tools.py` exit0/PASS10tests. Compile/diff-check PASS;
index empty. No stage/commit/push, main reset, volume deletion or main pause.
NOT RUN: full54-node dbt build/test/release with the new model, runtime S01 DB
acceptance, SAME900 qualification, remote CI, burst/soak. The Airflow image still
contains the previous SQL: this slice is implemented/SQL-verified, NOT deployed
or certified end-to-end. M08D remains incomplete and previous FAIL reports stand.
Next: deploy only at an idle release boundary, verify the complete dbt/publication
gate, then rerun unchanged900; profile remaining models/publication before any
incremental/parallel architecture change. No next-milestone work.

### M08D page50 verified; 900 data/drain PASS, scheduled cadence FAIL

Final runtime command `python -m tools.s02_data campaign --config tools/s02_data/config/campaign_rate_900.json --confirm-local`
exit1 / FAILED at15:26:25.872751UTC (22:26:25 local). Report
runtime/campaign-a152a820e7324b50a6fda9dfcdf6198c/report.json;
dataset campaign-rate-900-47b3eeb1ab2e. load_assessment FAIL, measurement INCOMPLETE.
Eligible scheduled successes Website/eBay/inbox/recovery1/1/1/1 versus2 EACH
with DAG start inside the fixed window. No count/window/worker/budget changes
mid-run and no higher load admission. All prior FAIL reports remain failed.

All900 final versions observed15:23:51.876699UTC: drain751.876699s versus900s,
before15:26:20 deadline. First post-deadline sampler elapsed905.018461s. Thus
the generic drain/scheduled-cycle error is due to cadence here, not late drain.
Independent read-only `python -m test_support.m08d_measure --report runtime/campaign-a152a820e7324b50a6fda9dfcdf6198c/report.json`
exit0/PASS900orders3801lines914observed of1941planned versions,zero errors.
No final latency assessment/p95 because normal finish was blocked; do not infer
full load PASS from correctness.62samples: peak reported stack memory2397948606
bytes (~2.23GiB), peak total DB growth75227136bytes (~71.74MiB); no ceiling failure.
Independent final hash reread78/78matches. Different warm history/phase prevents
a controlled whole-pipeline speedup claim versus preceding900 reports.

Runtime paging evidence: recovery collection ac9a267f-8176-524a-a668-b75ac686fca6
SUCCEEDED with6list audits/300detail audits, max work attempt1. Earlier39-receipt
collection used1list page. Inbox collection5df8288d-3567-5d67-83e0-b6ffcc8a2bf0
SUCCEEDED459detail audits, max work attempt1; later55detail collection also
SUCCEEDED. No100-claim cutoff. Read-only audit window acquired_at15:01:20..15:24:00
shows10eBay list audits and7Etsy list audits, ALL limit50; this window is not a
claim of exclusive campaign CPU/HTTP attribution. Later empty-source scans can
produce additional audits. eBay first collect attempt retries on mutable-page
total, second succeeds~54s. Observed full builds81/86/111/129/166s, source-slot
waits up to183s and release wait90s: larger list pages alone do not solve cadence.

Final health: seven healthchecked services healthy, observer Up, four live DAGs
unpaused. Active TESTED batch8b10a154-1faf-5adc-b3e9-73bd2665f2c7 has RUNNING
Website owner scheduled__2026-11-07T15:19:04.984725+00:00; no abort. Three latest
dbt artifacts54nodes/zero nonpassing,elapsed35.799/122.696/52.732s. No runtime
implementation edits during measurement. Index empty,diff-check PASS; code/docs
left unstaged. No main data reset, volume deletion, forced success or Git writes.
Remote CI,cold S01 DB acceptance,full C matrix,burst/soak,exact commit latency and
higher rate NOT run. M08D remains incomplete. Next: measured SQL/HTTP-detail and
build/queue profiling (including idle-cycle rebuild cost), then one bounded fix
at a time under the SAME acceptance contract; no speculative worker/RAM increase.

Implementation and pre-deployment evidence below precede the completed verdict.

2026-11-07 owner requested continuation after reviewing HTTP/paging/queue costs.
Selected scope: configurable list pages only; no dbt, worker-count, retry-budget,
business-schema or acceptance-window changes. main/HEAD4c12bc2, all existing dirty
work preserved. Finalized settings.page_size semantics in05_TARGET_SCHEMA.md and
the experiment in19_M08D_MEASUREMENT.md before code; no DDL required.

New pure validator ingestion/pagination.py; direct eBay/Etsy CLI --page-size
defaults1, caps200/100. Live overlay defaults50/50 via LIVE_EBAY_PAGE_SIZE and
LIVE_ETSY_RECOVERY_PAGE_SIZE, documented in.env.example; owner.env NOT edited.
Polling persists the integer per cycle, restores legacy missing=1 and rejects
invalid persisted values. Reuse ignores even an invalid replacement environment;
non-reuse configuration cannot silently change an existing cycle. Direct Etsy
recovery checks retained list URL limits before cache/scan reuse. eBay validates
matching limit/offset/cardinality/next URLs and retains1000-order safety cap;
Etsy preserves count/order/partial-page checks and10k bound. Raw/audit, detail GETs,
source identity/fingerprints, durable budgets and checkpoint barriers unchanged.
Hash coverage now includes eBay collector/helper; measurement captures effective
container page settings. Startup validates limits before pausing schedules.

Actual local regression commands/outcomes:

```powershell
docker compose --env-file .env --file infra/compose.yaml run --rm -T --no-deps --volume "${PWD}:/repo:ro" --env PYTHONPATH=/repo --entrypoint /opt/airflow/project-venv/bin/python airflow -m unittest -v tests.test_marketplace_pagination tests.test_m06_cycle tests.test_etsy_drain tests.test_m08c_http tests.test_m05_http tests.test_m06_unit
docker compose --env-file .env --file infra/compose.yaml run --rm -T --no-deps --volume "${PWD}:/repo:ro" --env PYTHONPATH=/repo --entrypoint /opt/airflow/project-venv/bin/python airflow -m unittest -v tests.test_marketplace_pagination.PaginationTests.test_larger_pages_do_not_accept_changed_order_details
docker compose --env-file .env --file infra/compose.yaml run --rm -T --no-deps --volume "${PWD}:/repo:ro" --env PYTHONPATH=/repo --entrypoint /opt/airflow/project-venv/bin/python airflow /repo/tests/etsy_recovery_probe.py
python tests/test_s02_campaign.py
python tests/test_s02_live.py
python tests/test_etsy_recovery_scan.py
python tests/test_m08d_measure.py
python tests/test_m08d_envelope.py
python -m compileall -q ingestion orchestration tools test_support tests
git -c core.safecrlf=false diff --check
```

48 related HTTP/unit tests PASS, then added changed-detail refusal test1PASS;
campaign16/live29/scan8/measurement12/envelope11PASS =125 distinct selected tests.
Controlled real-HTTP fixture:51 orders with page20 require3 list calls versus51
with page1; eBay retains102 detail/enrichment calls in BOTH variants. Not a
whole-pipeline speedup claim. PostgreSQL/HTTP rollback probe17checks PASS,
259 receipt GETs, including multi-receipt page/checkpoint and refusal to change
direct recovery limit before any new HTTP. Existing250-work drain/cache/budget
checks still PASS. No main SIM controls or durable test data changes.
fixtures/s01 `python verify.py`:10offline checks PASS;
`python -m unittest -v test_tools.py`:10PASS. Compile/diff PASS, index empty.
CI commands added for pagination and cycle policy; remote GitHub CI NOT run.

Read-only resolved live config: EBAY_PAGE_SIZE=50,ETSY_RECOVERY_PAGE_SIZE=50,
AIRFLOW__CORE__PARALLELISM=2. Main had not yet redeployed at this checkpoint; the
subsequent SAME campaign_rate_900.json deployment/result is above. Stop escalation
on failure. Bigger pages may increase list/detail staleness; those guards stay
enabled. Prior FAIL reports remain failed, full M08D acceptance not implied.
Same900 command started 14:47:48.222292 UTC; report
runtime/campaign-a152a820e7324b50a6fda9dfcdf6198c/report.json. Guarded startup is
draining old runs before deployment; admission and verdict pending. Runtime
code/config frozen from this point. No speculative higher-load admission.
Deployment verified: effective container50/50 pages,2slots; host/container hashes
match for both collectors, helper and polling. Healthy/restored schedules at
14:59:44 UTC. Admitted15:01:20.074498UTC, dataset campaign-rate-900-47b3eeb1ab2e;
fixed source end15:11:20UTC, drain deadline15:26:20UTC. Baseline4879current orders,
21421lines,5086history,24948raw. New cycles persist page_size50; physical recovery
list audit also shows limit50. This is warm-history observational qualification,
not controlled A/B against prior runs. Completed verdict above.

### M08D 900 rerun completed: drain fix works, scheduled cadence still FAIL

Final result: campaign exit 1 / FAILED at 14:23:10.994754 UTC (21:23:10 local).
Report runtime/campaign-c9e9f6fab5594f7ca89c0459a9af37ab/report.json;
measurement INCOMPLETE, load_assessment FAIL. Eligible scheduled successes
Website/eBay/inbox/recovery = 2/1/1/1, requiring 2 EACH with DAG start inside the
fixed admission/source window. Later successful runs do not qualify retroactively.
No higher load admitted, no gate/window/attempt reset or runtime code edits.

All 900 final current versions were observed at 14:22:01.240838 UTC, before the
14:22:58 deadline. Observed drain 843.240838s versus 900s: drain itself passes;
the generic runner error mentions drain/scheduled-cycle, but the unmet condition
here is scheduled cadence. First sampler after the deadline saw elapsed
912.054942s. Final latency assessment is absent because normal measurement finish
was not reached; do NOT claim a measured p95 or full load PASS.

Independent read-only command:
`python -m test_support.m08d_measure --report runtime/campaign-c9e9f6fab5594f7ca89c0459a9af37ab/report.json`
exit 0 / correctness PASS: 900 orders, 3801 lines, 910 observed of 1941 planned
versions, zero errors. This does not replace the failed campaign verdict.
62 resource samples: peak reported stack memory 2356708110 bytes (~2.19 GiB),
peak total DB growth 74694656 bytes (~71.23 MiB). 76/76 frozen host-code hashes
still match on independent final reread. No resource ceiling failure recorded;
this alone does not establish CPU/IO headroom or exclusive cause attribution.

Focused runtime proof: inbox collects 390 receipts in one collection/attempt;
recovery collects 300 in one collection/attempt (audit details below). At final
read-only inspection, Etsy inbox collect attempts since admission: 2 SUCCEEDED;
recovery: 3 SUCCEEDED; no FAILED/RETRYABLE collect rows in that scope. These
counts include post-window invocations and are NOT eligible scheduled DAG counts.
The old 100-claim exhaustion was not reproduced. Remaining observed costs include
eBay mutable-page retry, ~97s release-slot wait, ~127s inbox source-slot wait,
~192s inbox receipt collection, ~277s recovery collection and full dbt builds.
Warm retained history differs from the prior run; no causal whole-pipeline A/B
speedup/regression claim. Next is targeted HTTP/paging, queue and build profiling,
not blindly raising RAM/retry budgets or removing release/test guards.

Final checks: seven healthchecked services healthy, observer Up; all four live
DAGs unpaused. Active BUILDING batch 900c641b-9840-548c-9f6e-455d94c8e74a belongs
to a RUNNING etsy_recovery scheduled__2026-11-07T14:16:26.669995+00:00; no orphan
abort. Three latest dbt artifacts each54 nodes/zero nonpassing, elapsed
36.272/50.201/109.662s. In fixtures/s01: `python verify.py` 10 offline checks PASS,
`python -m unittest -v test_tools.py` 10 PASS. `git -c core.safecrlf=false diff --check`
PASS, index empty. Full C matrix, cold S01 DB rebuild, remote CI, burst/soak,
exact source-commit latency and higher-rate runs NOT performed. M08D incomplete.
Services/data retained for owner inspection. No new implementation in this task;
documentation changes unstaged, no commit/push, deletion or reset.

Owner requested the local runtime test on 2026-11-07. Exact command:
`python -m tools.s02_data campaign --config tools/s02_data/config/campaign_rate_900.json --confirm-local`.
Started startup 13:46:47.592425 UTC; report
runtime/campaign-c9e9f6fab5594f7ca89c0459a9af37ab/report.json. Main/HEAD 4c12bc2,
existing unstaged files preserved. Preflight: seven healthchecked services
healthy, observer Up, all four live DAGs unpaused. Guarded startup drains prior
scheduled runs before rebuilding/deploying current code; no reset/abort/forced
task status. Same 900 orders/10min, seeds, page size, two-success gate, two-worker
setting and original resource/delay/drain budgets. No code changes during test.
The startup checkpoint below precedes the final result above; prior failed 900
remains FAILED.
Guarded startup completed drain/rebuild/readiness at 13:56:20 UTC, with all four
periodic schedules restored. Read-only container check confirms etsy.py SHA256
9a770320823d54a176947a54225569758af35868323219ad23a37d2d0d89303d matches host and
contains range(len(only)); this runtime uses the drain fix, not the old image.
Admitted 13:57:58.992208 UTC, dataset campaign-rate-900-89dd726f2873; fixed source
end 14:07:58 UTC, fixed drain deadline 14:22:58 UTC. Same 1941 versions/5927749
generated bytes and 1.5 offered orders/s. Warm baseline 3979 current orders,
17620 lines,4176 observed versions,20816 raw records; 2 CPU/4109398016-byte VM,
2 executor slots and 60-second source schedules. Not a controlled empty-DB A/B.

Live read-only audit proves the focused fix: inbox collection
2f7e3b5f-5e1f-5d34-a5c5-ec83df227eeb SUCCEEDED with 390 receipt works / 390 HTTP
attempts, max work attempt 1; workflow collect attempt 1,14:05:19.128171 to
14:08:30.682313 UTC. Recovery collection f8443a7c-28b1-50f4-a9e7-64258f9e23ad
SUCCEEDED with 300 receipt works /300 HTTP attempts,max work attempt1; workflow
collect attempt1,~277s. No 100-claim cutoff failure observed. End-to-end verdict
is recorded above; these substage successes do NOT waive the scheduled-cycle gate.
Observed release-slot wait eBay ~97s,source-slot wait inbox ~127s; actual builds
include69/100/124/143s. eBay first attempt has mutable-page-total reconciliation;
subsequent collect succeeds in attempt2. No runtime code/limits edited mid-run.

### M08D narrow Etsy drain fix verified; 900 rerun pending

2026-11-07 owner explicitly limited implementation to drain and related checks.
Branch main / HEAD 4c12bc2 unchanged; existing dirty source/docs and owner config
files preserved. Inspected Git, Python 3.12, Docker and current healthy main stack
before editing. No stored procedures, count-style rewrite, projection cleanup,
page-size change, dbt edit, new DDL or operational columns in this task.

Changed only drain's claim-loop budget from 100 to len(initial work-ID list).
It remains finite, excludes arrivals during the invocation, uses the same
claim/process/commit/lease fencing and fails on real HTTP failure or unresolved
work. Five work/HTTP/stage attempts, Retry-After, DAG timeouts and recovery's
checkpoint-after-completion rule are unchanged. Inbox retries still select the
then-outstanding work, as before; this is NOT persisted collection membership
across restarts. No claim that the complete 900 cadence issue is solved.

Actual checks, from repository root unless specified:

```powershell
docker compose --env-file .env --file infra/compose.yaml run --rm -T --no-deps --volume "${PWD}:/repo:ro" --env PYTHONPATH=/repo --entrypoint /opt/airflow/project-venv/bin/python airflow /repo/tests/test_etsy_drain.py
docker compose --env-file .env --file infra/compose.yaml run --rm -T --no-deps --volume "${PWD}:/repo:ro" --env PYTHONPATH=/repo --entrypoint /opt/airflow/project-venv/bin/python airflow /repo/tests/etsy_recovery_probe.py
python tests/test_etsy_recovery_scan.py
python tests/test_m08d_envelope.py
python -m compileall -q ingestion tests
git -c core.safecrlf=false diff --check
```

- Drain unit suite: final 11 tests PASS (250 success, explicit scope, new arrivals,
  interruption after 120 durable completions/resume without refetch, HTTP failure,
  unavailable claim, finite no-progress loop, terminal/completed/empty scope and
  incomplete recovery checkpoint). Initial test run failed because the fake
  claim returned integer 0 rather than a lease tuple; corrected the test double,
  then 10 PASS and final 11 PASS. Production behavior was not weakened to pass it.
- HTTP/PostgreSQL probe: exit 0 / 15 checks PASS, 256 actual receipt GETs total,
  including a 250-work explicit scope completed in ONE drain call, one attempt
  each, 250 eligible raw receipt records with collection lineage; re-entry made
  no additional HTTP calls. Previous scan/cache/budget/checkpoint checks also PASS.
  All probe writes rolled back; independent read-only verification found zero
  surviving reconcile-probe runs and zero work for synthetic IDs 200000000000..249.
- Scan suite: 8 PASS. Unchanged load-envelope suite: 11 PASS. Compile/diff PASS.
  In fixtures/s01: `python verify.py` 10 offline checks PASS and
  `python -m unittest -v test_tools.py` 10 PASS. These are not a cold S01 DB run.
- Added the two container regression commands to daily-live integration CI;
  local commands verified, remote GitHub workflow NOT run. Compose warned that
  live-source belongs to the overlay; no --remove-orphans or cleanup was used.
- Seven healthchecked main services still healthy, observer Up. Only one-off
  Python test containers were started/removed, not a second scheduler; no main
  pause/restart, data reset, orphan abort or volume deletion. Main running image
  was NOT redeployed; one-off tests explicitly mounted current source read-only.

Next: rerun `python -m tools.s02_data campaign --config tools/s02_data/config/campaign_rate_900.json --confirm-local`.
Normal guarded startup rebuilds/deploys source before admission. This new 900
scheduled/load run, full C matrix, sustained/burst/soak and exact commit latency
were NOT run in this task. Prior failed 900 report remains FAILED, M08D incomplete.
Task changes remain unstaged; no commit/push.

### M08D cadence experiment: 144/600 PASS; 900 FAIL, escalation stopped

Final 900 result: exit 1 / FAILED at 10:51:23.765484 UTC. Report
runtime/campaign-5dac64c79dce4008905e7af52b97fcec/report.json; dataset
campaign-rate-900-0ba638b415fc, admitted 10:26:22.679694 UTC. 900 orders,
1941 planned source versions / 5927749 generated bytes, 10-minute source range
(1.5 offered orders/s, NOT measured processed throughput). Fixed source end
10:36:22 UTC. load_assessment FAIL: eligible scheduled successes Website 3,
eBay 1, Etsy inbox 0, recovery 1, against 2 EACH. Recovery's next start was
10:38:28.929103 UTC, outside the fixed window. Etsy inbox attempt 5 FAILED
10:42:54.556 UTC; its cycle log reports 159 receipt work items unresolved.
No retry budget reset, task-success override or source-window relaxation.

All 900 final current versions were observed by 10:48:32.422885 UTC; observed
drain 730.422885s (within 900s). Independent read-only command
`python -m test_support.m08d_measure --report runtime/campaign-5dac64c79dce4008905e7af52b97fcec/report.json`
exit 0 / correctness PASS: 900 orders, 3801 lines, 935 observed of 1941 planned
versions, zero errors. This DOES NOT regrade the failed load report. Its overall
measurement remains INCOMPLETE, final latency assessment absent because the
cycle gate stopped normal finish. Do not manufacture a p95/PASS for this case.
63 samples: peak stack memory 2319255073 bytes (~2.16 GiB), peak total DB growth
67977216 bytes (~64.83 MiB). Independent final SHA256 reread: 76/76 unchanged.

Diagnostics: eBay mutable page totals and Etsy changing recovery count are
present in cycle logs; Etsy inbox also repeatedly reports unresolved receipt
work. Existing drain() handles at most 100 claims per invocation, while each
stage has a finite five-attempt budget. These observations identify acquisition/
workflow cadence as the next profiling target, NOT permission to raise budgets
or skip atomic release/tests. Next slice: design bounded resumable collection
work/chunks and profile paging versus queue/build time; then rerun SAME 900
criteria. No higher rate, burst, sustained/soak, full D acceptance or production
capacity claim in this task. Exact source-commit latency remains NOT_MEASURED.

Final checks: selected campaign/measurement/envelope/live unit suites rerun
16+12+11+29=68 PASS; compileall tools/tests and diff-check PASS. fixtures/s01
`python verify.py` 10 offline checks PASS; `python -m unittest -v test_tools.py`
10 PASS. Three latest actual dbt artifacts: 54 nodes each, zero nonpassing,
elapsed 71.630/30.067/46.529s (not controlled A/B). No cold S01 database rebuild,
full C fault matrix, remote CI, burst or soak run. Seven healthchecked main
services healthy, observer Up; four live DAGs unpaused as before. Normal live
schedules continue, not a claim that every run is idle. No data/volume deletion,
main PostgreSQL stop, abort, staging, commit or push performed this task.
Final owner check: active BUILDING batch 8c059fde-d6cb-59d7-979f-f91f2f8cfe44
belongs to etsy_inbox scheduled__2026-11-07T10:48:10.511361+00:00, whose actual
Airflow DAG run is RUNNING (started 10:48:24.469986 UTC). No orphan conclusion or
abort. Highest PASS in this finite sequence is 600/12min, not a sustained ceiling.

The following entries are a reverse-chronological experiment journal. A pending
note describes that earlier observation, not a replacement for the latest
completed verdict above it. Earlier failed reports are never regraded.

600 step completed 10:17:54.591032 UTC, exit 0 / READY_FOR_REVIEW,
BASELINE_PASS and load_assessment PASS. Admitted 09:58:02.708520 UTC, dataset
campaign-rate-600-feae5d528d6d, report
runtime/campaign-bc8879a3cad646e2a8e11b46dcb8c2ac/report.json. Reconciliation:
600 orders / 2482 lines / 619 observed of 1317 planned versions, zero errors;
independent `python -m test_support.m08d_measure --report runtime/campaign-bc8879a3cad646e2a8e11b46dcb8c2ac/report.json`
also exit 0 / PASS. 600 final observations, zero censored; p50 275.515667s,
p95 636.718783s; observed drain 392.568803s. Qualified scheduled successes:
Website 4, eBay 2, Etsy inbox 3, recovery 2. Same 12-minute source range and
original gates; no mid-run code changes. The fail-fast shell began 900 startup
10:18:04.967926 UTC; its final failed verdict is above. Not full D certification.
52 resource samples: peak stack memory 2198352162 bytes (~2.05 GiB), peak total
DB growth 52740096 bytes (~50.30 MiB); within original budgets. All 76 frozen
code hashes retained; completion verifies them rather than accepting edited code.

Optimized144 completed09:51:50.987778UTC exit0: READY_FOR_REVIEW,
measurement BASELINE_PASS/load_assessment PASS. Reconciliation144orders602lines,
157observed/316planned versions,0errors.144final observations/0censored,
p50=270.238223s,p95=503.221051s versus1200s budget; drain394.223789s versus900s.
Qualified successes Web3/eBay3/inbox3/recovery2.48resource samples, peak reported
stack memory2147638833bytes (~2.00GiB), DB growth32104448bytes (~30.62MiB).
All76hashes match at completion. Independent same report --report inspector
exit0/PASS144/602/157,0errors. This is one finite warm-history envelope, NOT an
overall controlled speedup, soak or full D completion; all earlier FAILs remain.
Fail-fast shell began 600 startup 09:51:58.499294 UTC. Its completed result is
recorded above. No change to any declared limit/SQL/source semantics.

During optimized144 a long Etsy build was observed: stage~160.7s, artifact
c3952682-ce22-5cdb-83de-57b68075cc72 elapsed135.437s/54nodes; top nodes Etsy staging
113.488s,Website staging55.682s,fulfillment test25.401s. The following artifact
25688058... elapsed26.897s/54nodes. Broad timing variability is real; cause not
established, do not call the microbenchmark an end-to-end speedup or blame one SQL
without further profiling. One observation gap~61s is retained, not interpolated.
Recovery first eligible run SUCCESS09:45:05.518789UTC; second actual DAG run
started09:45:07.119793, BEFORE fixed09:45:14UTC end by~7s. Unlike previous FAIL,
there are two eligible candidate starts; acceptance still requires both success
and final source/core reconciliation within unchanged deadlines. No gate changed.

Post-deploy read-only confirmation: build.stg_website_observations and
build.int_website_versions are relkind r (tables),2482176+2105344bytes (~4.38MiB)
at inspection. Three new run artifacts each54nodes/0nonpassing, both config
materializations table, dbt elapsed42.963/20.840/35.747s respectively (different
source/phase; not a controlled wall-time comparison). No test/model pruning.
Optimized144 frozen76hashes, baseline2335current orders/10735lines/2465history/
12337raw; source end09:45:14UTC. See completed verdict above.

Optimized144 admitted09:33:13.957554UTC, dataset campaign-rate-144-748e1b8a0a2d,
report runtime/campaign-4e0d2e5f09be49eb828776a7fd4d4b35/report.json. Container
dbt_project SHA256 ddc30fb810f333f2842a20758d7dd91812a1e8aa097a3cf020d9629afae6f688
matches host. SAME12min/144orders/316versions, original resource/delay/drain/
two-success gates and2executor slots. No runtime code edits after admission.
Its later runtime acceptance is recorded above, independently of SQL parity.

Controlled temporary-graph benchmark exit0/PASS; report
runtime/materialization-a9e9f4b925f34d1cb622b6debb2ae659.json. Same manifest,
same compiled SELECTs,962Website header snapshots/4407line-history rows/1369
evidence links; EXCEPT ALL BOTH directions shows no differing rows. Views total
23.14503662s; tables9.701023699s INCLUDING8.417373528s materialization. This is
one sequential warm diagnostic, not a randomized capacity/CPU attribution claim.
Only TEMP objects, transaction rollback/connection close; last-good publication
signature unchanged; all4original unpaused live DAG states restored. No reset,
forced task status, orphan abort or stable-table writes in this task.

`python tests/test_s02_campaign.py`:16PASS (new transformation-hash coverage);
`python tests/test_m08d_measure.py`:12PASS; envelope11PASS; live29PASS=68selected
unit tests. fixtures/s01:verify10checks PASS,unittest test_tools10PASS. Compileall
tools/tests and diff-check PASS. SQL model files have no Git diff. No full S01 DB
reset/rebuild or remote CI. Started fail-fast144->600->900 command09:25:25UTC;
each exact `python -m tools.s02_data campaign --config tools/s02_data/config/campaign_rate_N.json --confirm-local`,
stop shell on any nonzero exit. Startup drains old runs before admission.
Same2executor slots,60s intervals and original budgets.

2026-11-07 owner requested next steps; main/HEAD4c12bc2 unchanged, existing
unstaged and owner files preserved. Docker main stack already running healthy.
Python3.12/Docker/rg available; project dependencies remain in container venv.
Reviewed actual run_results:54nodes, recent dbt elapsed33.99/46.93s, node-time
sums64.75/91.14s (parallel work, NOT wall time). Repeated Website view consumers
include evidence15.82s,line history12.07s,header7.17s in one retained artifact.
These are observational profiles, not proof of a controlled speedup.

Predeclared in19_M08D_MEASUREMENT.md and05_TARGET_SCHEMA.md: change ONLY Website
staging/intermediate materialization view->table, same SELECTs/columns/identities,
frozen manifest, all54model/test nodes, global barrier and atomic source publish.
No new source/stable DDL or model selection. Extra build storage must be measured.
Implemented two-line dbt_project.yml config; deployment and results above. Campaign
hashes now include dbt project/profile/model/macro/test files and release workflow
code; new hash-coverage regression. `python tests/test_s02_campaign.py`:16PASS;
compileall tools/tests and diff-check PASS. No worker/window/gate/budget changes.

Started `$env:PYTHONPATH=(Get-Location).Path; python runtime/benchmark_materialization.py`:
normal guarded maintenance drain/restore of all4initially unpaused live DAGs;
temporary SQL view/table graphs from one retained published manifest, global lock,
EXCEPT ALL parity for Website header/line history/evidence. No publication or
stable writes in this diagnostic. Completed parity and scheduled qualification
results above. No Git writes.

### M08D recovery verified; unchanged load qualification still FAIL

Final new qualification report runtime/campaign-20d7ee19c7aa47f2bdcd64b543057b59/report.json:
exit1/FAILED at07:55:15.407951UTC (14:55:15 local), measurement INCOMPLETE,
load_assessment FAIL at908.117766s after fixed source end (first sampled clock
beyond900s deadline). Scheduled successes Web4/eBay2/inbox3/recovery1; no600/900
admitted. Data correctness PASS and successful scan1INVALID->scan2VALIDATED do
NOT replace this verdict. Remaining issue is declared cycle cadence under shared
executor/source/release serialization, not the old poisoned-cache retry loop.

71resource samples, peak reported stack memory2156757251bytes (~2.01GiB), peak
DB growth33923072bytes (~32.35MiB); no resource ceiling exception. Descriptive
delays144samples/0censored,p50=291.377897s,p95=536.825852s,max=623.37391s,drain
318.15462s. These are scheduled final eligibility->first matching SQL observation,
NOT source-commit/first-publication measurements. Independent reread PASS:
144orders602lines150observed/316planned versions,0errors. Prior failed reports
retained; warm baseline2191orders10133lines2315history11529raw. All19frozen
hashes matched at campaign completion BEFORE the post-run constraint hardening.

Post-run review tightened009 with a named presence CHECK: SQL CHECK's UNKNOWN
must not allow INVALID/error_code=NULL. Dictionary already required this; no
collector behavior, budgets or business schema change. Applied updated009 twice:
exit0 both, idempotent. Final rollback probe rerun exit0/PASS12checks (adds actual
CheckViolation for NULL error),9list requests/6receipt requests; all DB writes
rolled back. Collector/helper hashes remain exactly the measured versions;
009's file hash is intentionally newer than the frozen run. No second full
campaign after this DDL-only hardening; do not claim every final file hash belongs
to the earlier runtime image. Final scan8unit tests/compileall/diff-check PASS.

Measured workflow-cohort stage p95s (not exclusive campaign CPU attribution):
Web build59.16/release-slot56.24; eBay build66.17/release-slot76.30;
Etsy inbox build79.59/source-slot72.39/release-slot51.84;
recovery build75.21/source-slot76.34seconds. Samples small (1..4builds); not a
production SLA or stable percentile estimate. Shared build/publication still
serializes. NEXT M08D slice: design a bounded cadence/throughput optimization,
measure executor/slot/build costs, preserve S01/identity/audits/global atomic
release, and rerun SAME envelope before larger profiles. Do not lengthen windows,
weaken gates or advertise capacity from offered rate. Full D remains open.
No remote CI, cold bootstrap, full C/S01 DB matrix, burst/soak or higher-load runtime
rerun in this task. No stage/commit/push; owner work retained.

Final post-hardening read-only reread: PASS144/602/150observed/316planned,0errors;
same14+33HTTP list audits and max URL attempt1->2 retained. Owner-release guard
PASS, all7healthchecked main services healthy, scheduler-observer running without
a healthcheck, all4live DAGs unpaused. DB query confirms0admitted300/600/900cohorts.
Final scoped17-file credential-pattern/trailing-whitespace scan0hits; this is not
an exhaustive security audit.18local links checked earlier resolve. Final Git
HEAD main4c12bc2ddb25d201b9fe2613fa00e24402fe17f8/index empty/diff-check PASS.
Chronological progress notes below retain their original pending checkpoints;
the completed verdict and NEXT action above take precedence.

All144 final current timestamps observed07:45:24.880802UTC. Independent command
`python -m test_support.m08d_measure --report runtime/campaign-20d7ee19c7aa47f2bdcd64b543057b59/report.json`
exit0/PASS144orders602lines150observed/316planned versions,0errors. Descriptive
observed delays n144,p50=291.377897s,p95=536.825852s,max=623.37391s;
first observed drain318.15462s after07:40:06UTC fixed source end.
Still not whole-envelope PASS: only ONE eligible Etsy recovery start in window,
run scheduled__2026-11-07T07:32:49.628368+00:00 started07:33:13.299706 and ended
SUCCESS07:40:56.219701UTC. The earlier SUCCESS started07:27:19 before admission;
the following SUCCESS started07:40:57.415353 AFTER window end, ended07:46:40.
Neither can be counted retroactively. Current qualifying successes Web4/eBay2/
inbox3/recovery1. Original900s post-window deadline remains unchanged; no larger
cohort admitted. Fix verified live; cycle-cadence/capacity gate remains open.

Live positive recovery evidence within new qualification: collector
8bbf241f-eb3f-5a16-af62-bd9daa6d17d8 scan1 INVALID07:35:53.170187UTC (14list HTTP
audits,max URL attempt1), then SAME collection scan2 VALIDATED07:39:26.484093UTC
(33list audits,max URL attempt2). All old audit rows remain. This verifies the
fresh-scan path against the actual DB-backed HTTP SIM, beyond the rollback probe.
Whole rate/correctness/scheduled envelope remains pending, not inferred from this
successful scan transition. Earliest scan38e27cf6... also VALIDATED.

New run admitted07:28:05.931741UTC, dataset campaign-rate-144-80116bcdf045,
report runtime/campaign-20d7ee19c7aa47f2bdcd64b543057b59/report.json.
All services healthy before admission; actual container collector/helper SHA256
match host versions de6f8509.../7f60b890....19hashes frozen; no runtime code edits
during admission/measurement. Same144orders/316versions,48per-source,12minutes;
actual scheduled/drain/resource/correctness outcomes pending. Four live schedules
restored, parallelism2/per-DAG1 unchanged. No600/900 admission in this invocation.

Startup attempt runtime/campaign-78a60416373b42bba831f585596ce3b1/report.json
refused before prepare/admission at07:18:39UTC when scheduler marked the retained
owner FAILED/cycle+failure-task SKIPPED. Owner then explicitly authorized abort
ONLY acc3d02c-1d89-5a1e-9d98-7c2d0c094da7 after idle recheck. Command
`$env:PYTHONPATH=(Get-Location).Path; python runtime/abort_etsy_orphan.py`:exit0/PASS,
official polling --abort --reuse-cycle-config with exact Etsy recovery execution,
original bound04:34:04.197897UTC,local-live-v1/m06-v1. Batch now FAILED;
manifest6715/raw6715/last-good3 counts+hashes identical before/after. Ignored
evidence runtime/operator-abort-etsy-4b92b4dbe90e47ad93a51bed354917e4.json.
No other abort/reset/clear or forced success. SAME144 command restarted07:19:42UTC,
currently drains retained active runs before new container build/admission.
M06 unit command using the same one-off container pattern with
`/repo/tests/test_m06_unit.py`:7PASS. S01 `python verify.py`:10offline checks PASS;
`python -m unittest -v test_tools.py`:10PASS. Neither is a full S01 DB rebuild.

2026-11-07 continuation: HEAD4c12bc2 unchanged, preserve all prior unstaged/owner
files. Python3.12 host has no psycopg; dependency-backed probes use the existing
Airflow project venv, not an unrecorded host dependency install. Finalized fields,
constraints, grants and compatibility in05_TARGET_SCHEMA.md BEFORE009 migration.
Added ops.etsy_recovery_scans and nullable HTTP-attempt scan FK. Only count/order
drift invalidates a scan; retries allocate a bounded successor without reusing
invalid pages or resetting the URL's cumulative five-attempt budget. Consistent
pages, interrupted RUNNING scans and VALIDATED processing retries retain cache;
scan1 adopts legacy NULL-linked pages. Partial scans no longer enqueue new work.
No source fields, snapshot fingerprints, business SQL or source interfaces changed.
Full page-set consistency/provider snapshot isolation is NOT promised.

Migration009 applied twice via LocalDB.sql to data_platform: exit0 both, second
schema_migrations insert0. Added bootstrap/migrate/live-up integration; live-up
applies after idle drain before recreating code. Campaign freezes19 code hashes,
including collector/helper/migration; older16-hash reports remain unchanged.

Commands/outcomes so far:
- `python tests/test_etsy_recovery_scan.py`:8PASS.
- `python tests/test_s02_live.py`:29PASS; `python tests/test_s02_campaign.py`:15PASS.
- `python tests/test_m08d_measure.py`:12PASS; envelope11PASS; M06 scheduling4PASS.
- `python -m compileall -q ingestion tools test_support tests`:PASS;
  `git -c core.safecrlf=false diff --check`:PASS, index unchanged.
- Real HTTP/SQL probe command:
  `docker compose --env-file .env --file infra/compose.yaml run --rm -T --no-deps --volume "${PWD}:/repo:ro" --env PYTHONPATH=/repo --entrypoint /opt/airflow/project-venv/bin/python airflow /repo/tests/etsy_recovery_probe.py`.
  Final rerun07:15:57UTC exit0/PASS11checks: count drift; fresh scans with unchanged
  URL budget; no partial enqueue/checkpoint; VALIDATED processing resume; actual
  receipt HTTP/work success; terminal audit fences; scan ceiling; five HTTP
  attempts survive scan/retry; duplicate identity; legacy page reuse; interrupted
  scan resume.9list calls/6receipt reads, every probe DB write rolled back.
  Earlier9-check version also passed. Expanded rerun was first blocked by tool
  approval-service usage failure before execution; subsequent rerun failed DNS
  because ALL main services were stopped. `docker compose --env-file .env --file
  infra/compose.yaml up --detach --wait --wait-timeout 180 postgres`:exit0/healthy,
  existing volume retained; final probe then passed. No remove-orphans action.

New startup preflight finds retained BUILDING batch acc3d02c-1d89-5a1e-9d98-7c2d0c094da7
owned by Etsy recovery scheduled__2026-11-07T04:31:31.227350+00:00, metadata RUNNING.
No authority to abort this batch; normal guarded resume/drain must recheck owner.
Started SAME144 envelope command07:16:55UTC:
`python -m tools.s02_data campaign --config tools/s02_data/config/campaign_rate_144.json --confirm-local`.
No new acceptance/admission claimed while startup/recovery is pending. No600/900
or other milestone/Git action. Earlier failed envelope verdicts stay FAILED.

### Latest verdict: finite escalation stopped at Etsy recovery failure

Qualification144 ended04:12:26.849017 UTC, exit1/FAILED; measurement INCOMPLETE,
load_assessment FAIL at906.646701s after the fixed source-window end (900s budget,
first observation beyond the deadline). Qualifying successes Web4/eBay2/inbox3/
recovery1, minimum2 each. The fail-fast144->600->900 shell stopped; read-only DB
verification confirms0 admitted300/600/900 cohorts. No more window calibration.

Independent correctness command:
`python -m test_support.m08d_measure --report runtime/campaign-de879a18327d4d4f97b494335b1af8b5/report.json`
exit0/PASS144orders602lines148observed/316planned versions,0errors. This reread
does not repair/regrade the failed whole envelope. All144 final observations
exist/0censored; computed nearest-rank p50=248.614436s,p95=470.614436s,
max=578.614436s. These are eligibility->SQL observation, NOT exact source-commit
or first-publication clocks. Since the envelope raised before finish(), computed
statistics are descriptive extraction, not a completed BASELINE_PASS report.
71resource samples: peak stack reported memory2131130051bytes (~1.98GiB), peak
DB growth30490624bytes (~29.08MiB); no resource-ceiling exception. Actual plan
144orders316versions995945serialized bytes,0.2offered orders/s; checksum
168309318b5a3a298aaed403da586310e4ffee25988738cadaf8a20371abc5f5.
Warm retained baseline2047orders9531lines2167history10771raw.16runtime hashes
still match. Local live parallelism remains2, intervals60s. No claim of sustainable
capacity, burst/soak, exact commit latency or completed M08D.

Final read-only health check: all7 healthchecked main services healthy; scheduler-
observer running without a healthcheck. All4 live DAGs unpaused; exact blocked
recovery owner is FAILED. Services/data remain in place, no new resets/aborts.
122selected unit tests and S01 checks passed as logged below; full compileall
passed.14local documentation links resolve; scoped credential-pattern scan16
selected files found0 hits (not an exhaustive security audit). No remote CI,
cold bootstrap, full C matrix rerun,600/900 runtime or long soak run in this slice.
Read-only statistic extraction initially used a wrong delay_seconds key and failed;
corrected to observed_delay_seconds, with no DB/report mutation.

NEXT: fix bounded recovery scan/reconciliation of mutable paged responses,
preserving raw audits, durable attempt limits and approved S01 resume behavior;
add regression/runtime evidence, then rerun the SAME declared144 envelope before
attempting600/900. Do not treat worker4 or a longer window as a proven fix.
No Git stage/commit/push; prior owner changes preserved.

### Qualification failure diagnosis (same retained run)

Qualification144 admitted03:45:19 UTC, dataset campaign-rate-144-af960b23dede,
report runtime/campaign-de879a18327d4d4f97b494335b1af8b5/report.json. Container
verified back to2global/1per-DAG slots. All144 final current versions observed
04:02:08 UTC; observed drain288.978221s after fixed03:57:19 source-window end.
Whole-envelope subsequently FAILED as recorded above: qualifying Etsy recovery run
scheduled__2026-11-07T03:54:13.633356+00:00 repeatedly fails collect. Read-only
raw audit for collector c42bce51-00ca-51a2-85d4-18f781b4ed2f proves HTTP200
offsets0/1/2 returned counts23/23/22 at03:56:58..59 UTC while source changed.
Whitelisted log messages in attempts1/2/3 match
`changing recovery count; retry/reconcile window`. recover() reuses these cached
successful pages on later invocations; retry repeats the inconsistent scan.
This is a recovery correctness/liveness issue, not evidence that more RAM fixes
capacity. No cache/audit/budget mutation, pipeline patch or forced task success
during this frozen run. Preserve its original deadline/verdict; no600/900 unless
the whole gate passes. A safe follow-up needs bounded fresh scan/reconciliation
identity with preserved raw/attempt budgets and approved S01 resume behavior,
not simply disabling count checks or deleting cached responses.

### M08D recovery authorized; escalating finite load — 2026-11-07

Owner approved official abort of ONLY d0b60a58-f9fe-5b0c-8fc5-486f584195b7,
then continuing with more meaningful load. Reverified exact owner DAG FAILED,
no live owner tasks and exact UUID-derived batch/cycle configuration. Ran
`$env:PYTHONPATH=(Get-Location).Path; python runtime/abort_rate_orphan.py`:
exit0/PASS, official orchestration.polling --abort --reuse-cycle-config,
original run/window/mapping/transformation context,300s bounded source-slot wait.
Batch now FAILED. Before/after hashes/counts match for that batch's manifest3949,
referenced raw3949 and last-good publication3. This is scoped preserved evidence,
not a claim no other concurrent workflow wrote anything. No reset/clear/forced
success. Ignored evidence runtime/operator-abort-rate-4bc2e5165be1400fb2fbb95eaf04fe29.json.
Initial diagnostic SQL used nonexistent execution_key/window aliases and failed
read-only; corrected to persisted requested_window_* and separate collector/cycle
lineage before any recovery write. No source/schema/business SQL changes.

Before load admission finalized larger finite envelopes in19_M08D_MEASUREMENT.md:
after Website24/6min and mixed72/6min PASS, run mixed300/6min then900/10min.
Dry plan validation:300orders643versions1980959serialized bytes;
900orders1941versions5952844bytes. Offered rates0.8333/s and1.5/s, NOT measured
source-commit/processed throughput. Larger count ceilings1000orders/3000versions/
1000unfinished planned sends;10MiB payload/RAM/disk/DB-growth/latency budgets stay
fixed. Stop escalation on any failure/ceiling. No burst or soak claim.
Started Website campaign again02:19:58 UTC; currently draining prior retries,
not yet a runtime rate acceptance result. No Git write requested.

Website rate step completed exit0/PASS02:37:12 UTC, report
runtime/campaign-6a5e93898982497cac3da36e101cd123/report.json;
dataset campaign-rate-website-31d2b2c29d4a, admitted02:26:33.627028 UTC (ADMITTED journal
02:26:36.579542), configured shifted source-window end02:32:36 UTC.
Correctness24orders121lines,28observed/63planned versions,0errors;
24final-observation samples/0censored,nearest-rank p50=305.353221s,
p95=383.567686s (scheduled eligibility to SQL observation, NOT exact commit).
Observed drain273.567686s after source-window end;2qualifying actual Website
scheduled successes, load_assessment PASS. Peak reported stack memory2224033886
bytes (~2.07GiB), DB growth7069696bytes (~6.74MiB);16frozen hashes match.
Retained baseline before this step1879current orders/8784lines/1989history/
9961raw; all polling intervals60s, Airflow parallelism2. No limit changed.

Started fail-fast sequential remaining commands02:37:40 UTC:
`python -m tools.s02_data campaign --config tools/s02_data/config/campaign_rate_mixed.json --confirm-local`,
then same with campaign_rate_300.json, then campaign_rate_900.json ONLY if each
preceding exit0. Reports/verdicts for those steps pending. Full D remains open.
Current offline rerun: envelope11/measure12/campaign15/local19/delivery9/live27/
health6/C21=120unit tests PASS (same eight python tests/... commands documented
below); S01 verify10checks + unittest10PASS; full compileall/diff check PASS.
New inspect_campaign.sql supports all campaign-% profiles, scoped source/account/
order identity and source-plan counts; actual read-only query PASS24orders63versions
(31future at that inspection clock). No remote CI/cold/full runtime C rerun.

Mixed72 attempt (parallelism2), report
runtime/campaign-512b34efc0804747a41719095db79497/report.json, dataset
campaign-rate-mixed-00a41974e542: all72final timestamps present02:54:49 UTC,
independent `python -m test_support.m08d_measure --report runtime/campaign-512b34efc0804747a41719095db79497/report.json`
exit0/correctness PASS72orders313lines75observed/161planned versions,0errors.
This is NOT whole-envelope acceptance: fixed admission/source-window candidates
allow only1 each for Etsy inbox/recovery, versus declared minimum2. Website/eBay
each2. Controller still respects original900s cycle/drain deadline; no gate, clock
or verdict changed mid-run. Larger rates not admitted while this gate is unmet.
Read-only AF task queued_dttm→start_date cohort samples: Web2 p95=139.09s,
eBay2 p95=156.23s,Etsy inbox1=139.78s,recovery1=118.66s. Manual30min queue SQL in
inspect_campaign.sql verified separately (whole stack; latest attempt clocks,
missing timestamps stay unknown). This is executor queuing, not guessed DAG lag.
Predeclared next one-knob experiment in19_M08D_MEASUREMENT.md: if final gate FAIL,
stop escalation, retain failure, then same72/6min with LIVE_AIRFLOW_PARALLELISM4,
base/disposable2 and all source/global locks/per-DAG1/resource/SLA gates unchanged.
Configuration not yet applied; higher-worker memory safety must be measured.

That2-slot mixed attempt ended03:05:08 UTC, exit1/FAILED, load_assessment FAIL
at the original900s cycle/drain deadline. Qualifying successes Web2/eBay2/
Etsy inbox1/recovery1. All72final observations had already arrived; observed drain
296.693779s, independent correctness PASS above.56resource samples, peak memory
2269099587bytes, peak DB growth29204480bytes. All16captured hashes matched at
completion BEFORE subsequent tuning. Failure retained, not retroactively green;
the fail-fast shell did NOT run300/900.

Implemented the predeclared one-knob experiment after that verdict:
live overlay reads LIVE_AIRFLOW_PARALLELISM (default2), local ignored .env=4;
.env.example default2; host live-up rejects unsupported values outside2/4 before
drain/DB writes. Per-DAG1, source locks and global release barrier unchanged.
No Docker CPU/RAM increase, SQL/business/schema change or gate relaxation.
`python tests/test_s02_live.py`:29PASS (2new config-boundary tests);
`python tests/test_s02_campaign.py`:15PASS; compileall PASS. Safe selected-field
Compose validation confirms base parallelism2/live4, no expanded environment dump.
Started same mixed72/6min command03:06:29 UTC, then conditional300/900 ONLY on
success. Startup drains idle before applying new container config. New workload
uses fresh source IDs but identical seeds/baskets/rates/gates; retained history is
larger, so this is diagnostic rather than strict controlled before/after capacity.
Runtime improvement/memory safety is pending, not inferred from config4.

Actual4-slot72 attempt: report runtime/campaign-5d55720689d542a1a86958be561a2c86/report.json,
dataset campaign-rate-mixed-ba8de91bc6b5. Runtime container verified4global/1per-DAG;
retained1975orders/9218lines/2092history/10389raw. All72final states reached
03:27:48 UTC; independent report reread exit0/PASS72orders313lines75observed/
161planned,0errors. However original cycle gate again FAIL at03:36:07 UTC,
successes2/2/1/1 (Web/eBay/inbox/recovery). All16hashes matched BEFORE subsequent
config rollback. Final observation samples72, computed nearest-rank p95=603.896189s;
observed drain406.6847s; peak reported memory2276819203bytes, DB growth28180480bytes.
Queue early cohort samples fell to Web0.096059s/eBay0.059062s/inbox0.189156s
(recovery not yet sampled then), but this did NOT improve the whole envelope;
do not advertise config4 as an overall speedup. Warm history/phase differ.
Both short FAIL records retained; no300/900 admitted by either fail-fast loop.

Predeclared ONE exposure calibration before new admission:144orders/720s, SAME
0.2offered/s as72/360s; then600/720s at original300/360s rate0.8333/s; then original
900/600s at1.5/s. Keep minimum2cycles,1200s observation,900s drain,1800s timeout
and RAM/disk/DB-growth budgets unchanged. More exposure/data, not less offered
pressure; no retrospective PASS or repeated window inflation. If this qualification
or a later step fails, stop/report limits. No source/schema/business redesign.
New dry plans:144orders316versions1000081bytes;600orders1317versions3989553bytes.
Extended envelope guards to both profiles:11PASS (same test count, expanded cases).

Rolled ignored local .env LIVE_AIRFLOW_PARALLELISM back to default2 after4-slot
verdict; next normal startup drains before recreating Airflow. Base/disposable
remain2. Began fail-fast144→600→900 loop03:37:13 UTC, exact campaign CLI with
config campaign_rate_144.json, then600, then900 only on preceding exit0.
Runtime outcomes pending. All8selected unit suites rerun after tuning:
envelope11/measure12/campaign15/local19/delivery9/live29/health6/C21=122PASS;
full compileall PASS. No Git action or remote certification.

### M08D rate tools implemented; runtime refused orphan release — 2026-11-07

Owner authorized next step after finite baseline. Main/HEAD4c12bc2 unchanged;
preserve prior unstaged SIM/C/campaign/health/baseline changes and owner local
configs. Docker29.9.2,2CPU,4109402112bytes RAM; all8main containers initially
stopped (~10h), no active disposable stack. Normal guarded startup/resume/drain
will retain old runs/retries/data. No automatic orphan release abort is authorized.
Predeclared contract in19_M08D_MEASUREMENT.md before implementation: Website-only
24orders/360s, then mixed72orders/360s; same100order/500version/10MiB and RAM/disk/
DB-growth budgets,900s observed-drain limit and2 actual scheduled successes per
active source's required DAG(s), started during the fixed admission/source window.
Old profiles omit optional campaign.load and keep prior behavior. No new DDL,
business SQL, source interface or fingerprint changes. Actual commit/publication
latency stays NOT_MEASURED. Short low-rate steps are NOT soak/capacity certification.

Added planned minute buckets, actual final-version backlog/oldest age, shifted
source-window-end hold, deadline/cycle/drain gates, whitelisted scheduler settings
and test-only envelope module. Unit commands so far:
`python tests/test_m08d_envelope.py`:10PASS;
`python tests/test_m08d_measure.py`:12PASS;
`python tests/test_s02_campaign.py`:13PASS.
Started `python -m tools.s02_data campaign --config tools/s02_data/config/campaign_rate_website.json --confirm-local`
at01:56:33 UTC. Mixed step will run only after first PASS. Results pending;
no larger rates, burst/soak, Git write or remote CI in this slice yet.

Actual startup exposed a retained main release, NOT a load-induced failure:
batch d0b60a58-f9fe-5b0c-8fc5-486f584195b7 remains BUILDING for eBay run
scheduled__2026-11-06T15:39:09.006704+00:00. After restart its DAG run became FAILED
(end01:58:01.939748 UTC); cycle/failed_workflow tasks both SKIPPED, no owner task
running. Current retries own later15:42+ runs and wait for this older release;
no platform-release advisory lock holder was observed (two source-cycle locks).
No authority to abort THIS batch: no automatic abort, reset or forced success.

Interrupted host campaign5db8471bcae4425581f4208c86e16e7c before prepare/admission.
Tool Ctrl-C exit1 did not execute Python finally; original report remains stale
RUNNING/PREFLIGHT and is preserved, with explicit operator-stop.json sidecar
(NOT_RUN acceptance). Escalated Win32 process inspection found no matching host
Python campaign process; sandbox process inspection had access denied. Source DB
query confirms0 local_datasets with campaign-rate-% prefix. No new test data.

Fixed safety prerequisite: optional drain_guard callback rechecks orphan ownership
after resume AND each drain iteration. Previously initial preflight could see an
old owner RUNNING before scheduler recovery turned it FAILED. Default live/C
drain behavior unchanged when callback omitted; no automatic recovery added.
Two additional unit guards PASS; campaign suite now15PASS, live27PASS and C21PASS
rerun after this change. All eight selected suites:119 unit tests PASS total:
envelope10,measure12,campaign15,local19,delivery9,live27,health6,C21.
Exact commands: `python tests/test_m08d_envelope.py`, `python tests/test_m08d_measure.py`,
`python tests/test_s02_campaign.py`, `python tests/test_s02_local.py`,
`python tests/test_s02_delivery.py`, `python tests/test_s02_live.py`,
`python tests/test_airflow_health.py`, `python tests/test_m08c.py`.
In fixtures/s01 `python verify.py`:10checks PASS;
`python -m unittest -v test_tools.py`:10PASS.
Full application/tools/test compileall PASS. Local links/fences3guides12links PASS;
new rate file whitespace7files PASS. Runtime rate acceptance remains NOT_RUN.
Final9task-file exact credential/whitespace scan PASS (values suppressed);
git diff --check PASS, index empty; ignored operator evidence verified ignored.
No stage/commit/push. Remote CI/cold bootstrap/full C runtime matrix, exact
commit/publication clocks and burst/soak not run in this task.

Repeated exact Website campaign command02:05:27-02:05:29 UTC: exit1, expected
operator-recovery refusal before admission, report
runtime/campaign-1e1f970d54094648a297fe8297de9f97/report.json (FAILED/INCOMPLETE,
not a load PASS). Five resumed services PG/Airflow/eBay/Etsy/receiver healthy;
live-source/report/scheduler-observer remain stopped. Existing drain marker
prevents new schedules; already-active retries stay runnable. No host test process
left running. Do not present this partial startup as full live-stack readiness.

Next required owner decision: permission to reverify idle ownership and officially
abort ONLY d0b60a58-f9fe-5b0c-8fc5-486f584195b7 while retaining raw/audit/manifest/
last-good; then allow existing retries to finish/drain and rerun Website before
mixed. Until authorized, no rate/burst/soak acceptance claim. Prior baseline PASS
remains historical evidence, not proof for these changed tools/new profiles.

### M08D bounded baseline PASS; full load/soak gates pending — 2026-11-06

Owner reviewed normal/recovery demos and authorized the next step. Current main
HEAD4c12bc2 and all existing unstaged SIM/campaign/health work preserved. Docker
read-only preflight:29.9.2,2 CPU,4109402112 bytes RAM; existing main services running,
all healthchecked services healthy. No Git action requested. First slice is the
finite warm-history correctness/resource baseline, not all load/soak certification.
Finalized JSON measurement fields/clock meanings and safety budgets before code:
19_M08D_MEASUREMENT.md. No new DDL or business SQL semantics. Exact commit-to-first-
publication latency remains NOT_MEASURED rather than reusing an incorrect clock.

Implemented optional campaign.measurement, strict finite/resource ceilings,
test-only source oracle and current/history/line/money/mapping/raw-manifest
reconciliation. Existing review-only profiles remain unchanged. Measurement
artifacts stay under ignored runtime/. No new table, simulator source interface,
fingerprint or business transformation semantics. Independent reread commands:

- `python -m test_support.m08d_measure --report runtime/campaign-f715cc1473ac4119a9947a9cb63c4c49/report.json`: exit0/PASS,6orders20lines,6observed/11planned versions.
- Same command with `runtime/campaign-0af724fbbf2c4bb49f8a961f59e050fe/report.json`: exit0/PASS,8orders34lines,8observed/16planned versions.
- `python -m test_support.m08d_measure --preflight-config tools/s02_data/config/campaign_baseline.json`: exit0/PASS, read-only, NOT runtime acceptance. Sample14:55:49-14:55:53 UTC: scoped memory2361661585bytes, workspace free105150648320bytes, PG-volume free234887569408bytes. Retained1867orders/8735lines/1976observed versions/9861raw records. No preparation/admission.

Baseline profile fixes before admission: the initial draft's partial-shipment
branch correctly refused missing minimum basket lines/quantity; made eBay basket
explicit (2..5lines,1..5units). No data was admitted by those failed validations.
Final profile12orders/30versions,3-minute source range, explicit safety budgets.
Runtime command:
`python -m tools.s02_data campaign --config tools/s02_data/config/campaign_baseline.json --confirm-local`.
Exit0/BASELINE_PASS,14:59:24-15:15:54 UTC. Report:
`runtime/campaign-551964eda899400d9a4a3276373990a4/report.json`.
Dataset campaign-baseline-d05c55aa6ddc/source ID0481cfb69ceb. Old live work drained
normally, services healthy before restoring schedules. Admitted15:07:31.643917 UTC;
preparation/admission19.313s; final coverage observed15:15:52 UTC. No clear, forced
success, manual publication or budget reset. Correctness PASS12orders/49lines,
13actually observed history versions of30planned;0errors. Scheduled-final-
eligibility to first SQL observation:12samples,0censored,p50=265.1138s,
nearest-rank p95=372.424403s, declared budget1200s PASS. This is NOT exact
source-commit-to-first-publication latency.30source versions/87387serialized bytes;
source-plan SHA256 eee4f86d2fcd3f9050e0359d917e78b1dca9a79207db109d8eda7f3221421479.
24resource samples: peak reported stack memory2390046537bytes (~2.23GiB), peak
DB growth17432576bytes (16.625MiB), peak pending sends8. No safety ceiling reached.
Docker CLI memory is cache-adjusted, not complete host/VM memory accounting.
15frozen runtime code hashes still match after completion.

Stage summary is whole-stack since admission, not exclusive12-order work:
completed build_and_test p95 Web53.818s(n1),eBay68.119s(n2),Etsy84.479s(n3);
release_slot p95 Web81.988s(n2),eBay54.290s(n1),Etsy67.765s(n3).
This identifies build/release contention as a candidate to investigate, not a
capacity conclusion from such small samples. In-flight durations remain null.
Raw-window counters are physical audit payload bytes, not deduplicated wire
traffic/unique business versions; retain per-resource grain rather than calling
their sum network throughput. No faults applied; main services left running.
Final Docker ps: all7healthchecked main services healthy, scheduler-observer
running; Airflow metadata confirms website_polling/ebay_polling/etsy_inbox/
etsy_recovery all unpaused. Branch main/HEAD unchanged, index empty.

Independent post-run reread:
`python -m test_support.m08d_measure --report runtime/campaign-551964eda899400d9a4a3276373990a4/report.json`:
exit0/PASS12orders49lines13observed/30planned,0errors.
The documented read-only30-minute stage SQL executed successfully (20groups at
inspection); it does not claim every concurrent task has already finished.

Local regression commands/results (2026-11-06):

- `python tests/test_m08d_measure.py`:12PASS.
- `python tests/test_s02_campaign.py`:13PASS, including opt-in monitor wiring, failed verdict propagation and finite-plan refusal before Docker/preparation.
- `python tests/test_airflow_health.py`:6PASS.
- `python tests/test_m08c.py`:21PASS (offline guards, not a fresh C runtime matrix).
- `python tests/test_s02_local.py`:19PASS; `python tests/test_s02_delivery.py`:9PASS; `python tests/test_s02_live.py`:27PASS. Total107unit tests.
- In fixtures/s01: `python verify.py`:10offline checks PASS; `python -m unittest -v test_tools.py`:10PASS.
- `python -m compileall -q tools ingestion simulator transformation orchestration reports test_support tests`:PASS.
- `git diff --check`:PASS; index empty. Remote CI, fresh cold setup, sustained/burst/soak and exact commit/publication latency NOT run in this slice. Full M08D remains incomplete.
- Local links/fences:4guides/46links PASS;9baseline-file trailing whitespace checks PASS; exact local credential scan7task files PASS (values suppressed). Mermaid/browser screenshot rendering not run. No Git write action.

Next scoped task: freeze sustained single/mixed-source step envelopes, burst/drain
and genuine soak budgets before larger runs; separately finalize durable source-
commit/first-publication clocks before related DDL. Investigate build/release-slot
contention using identical measured work, without silently weakening atomic
publication/history/tests. Baseline PASS is not full M08D or release certification.

### C repeatability fixed; normal/recovery demos ready for owner review — 2026-11-06

Owner authorized, in order: repair C catch-up, normal campaign, then one observable
eBay outage. Load measurements/SLA scoring are explicitly deferred until owner
reviews those demos. Existing SIM changes and owner-local configs are preserved;
no Git action requested. First fix removes both retained disposable drain markers
before parsing, with owner/DB/path guards. Runtime rerun7f503052c91f4402bdc7fa0e72d6b800
then exposed a startup race: retained unpaused DAG published before the pause
assertion. Cleanup PASS. Next attempt7b2097ae8e6e4f98a060ea5888b32aaf correctly refused
an active retained test run; cleanup PASS, no forced task state/budget reset.

Added real one-shot Airflow CLI pause BEFORE scheduler startup, and scoped shared
drain for cleanup; fresh-success count is scoped to newly created run IDs rather
than historical successes. Guarded operator helper runtime/recover_c_schedule.py
allowed the interrupted test run to finish naturally under a test drain flag.
Evidence operator-drain-5f911df3b1a249149f8924afaeba16c5.json records the old run
terminal FAILED and cleanup PASS: recovery, not case acceptance. Two subsequent
clean runs of `python -m test_support.m08c run --id 563f55c17bab --case
scheduled_pause_resume --confirm-disposable` both exit0/PASS,58 recorded steps
and cleanup PASS each. Evidence suffixes0a5f5effe9a54ef2a92191513cc27fdd and
4c9a10f5998e452f954591e7f0fc7aca in that scope's evidence directory. Each requires
two NEW scheduled successes, final catch-up and observed-only history.
`python -m test_support.m08c report --id 563f55c17bab`: latest18 cases PASS.
Owner Airflow stayed stopped during disposable runtime (4GB VM); owner
PG/SIM/receiver remained running. Disposable services stopped before main startup.

Owner explicitly authorized official abort of the orphan main eBay batch
ae808a96-e053-528f-b833-66b77dec48e3. Immediately rechecked: main Airflow stopped,
its exact scheduled DAG run FAILED, no granted data_platform advisory locks, this
was the only active release batch (BUILDING). Invoked official orchestration.polling
with original execution/DAG/run/bounds plus --abort --reuse-cycle-config in a
one-shot main Airflow CLI; exact batch is now FAILED. Full before/after count/hash
signatures match for raw_records9485, batch_inputs1223850, publication_state3,
webhook_delivery_attempts1157, webhook_inbox1112 and task_attempts4858. No deletion,
budget reset, forced task success or last-good change. Ignored evidence:
runtime/operator-abort-0e9932ec536449c5b2bbc314cc67d717.json (PASS).
Exact guarded host invocation: `$env:PYTHONPATH=(Get-Location).Path; python runtime/abort_owner_orphan.py`.
Its one-shot workflow arguments were `-m orchestration.polling --source ebay_sim --execution-id scheduled__2026-11-01T15:59:11.516435+00:00 --dag-id ebay_polling --airflow-run-id scheduled__2026-11-01T15:59:11.516435+00:00 --window-end 2026-11-01T16:02:32.892036+00:00 --mapping-version local-live-v1 --transformation-version m05b-v1 --abort --reuse-cycle-config --wait-seconds 30`.
The helper is private one-off evidence, not a new automatic recovery API.

Campaign review slice implemented: optional config.campaign, normal/recovery
profiles, explicit local/fault consent, same-stack startup, actual event journal,
per-admission final-version coverage and fault restoration of the exact eBay
container. No throughput/latency score, no negative-data extension. Read-only SQL
smoke of the existing cf5ea36bbe65 demo:8 expected orders,0 future source versions,
0 pending sends,0 core rows (owner scheduler stopped); snapshot reports NOT ready
instead of a false PASS.

`python -m tools.s02_data campaign --config tools/s02_data/config/campaign_normal.json --confirm-local`:
exit0, READY_FOR_REVIEW. Dataset campaign-normal-93b6b7a06a0c; report
runtime/campaign-f715cc1473ac4119a9947a9cb63c4c49/report.json. Admission09:45:14 UTC,
final observation09:53:02 UTC: each channel expected2/found2/current2, future
versions0, pending sends0, eBay error audits0. Sources used normal scheduled
ingestion/dbt/publication, not manual stage invocations. UI endpoints8080/8501
respond HTTP200; existing PG remains5433. Existing stopped runs drained naturally
before startup/admission. These observed clocks are NOT a performance grade.

Recovery example adjusted BEFORE execution to a four-minute source interval and
an180-second pause starting within180..210 seconds (seed42 chooses200). Current
serialized builds can postpone eBay collection beyond the earlier75-second draft
window. Wider timing supports observation, not a guaranteed failure overlap or
SLA result. `python -m tools.s02_data campaign --config tools/s02_data/config/campaign_recovery.json --confirm-local --allow-faults`
first attempt FAILED before admission/fault at10:00:12 UTC during live-up Compose
build/start, after old work drained successfully. Private report
runtime/campaign-518f07028f4d4a7db24c9bfe0e46110d/report.json; fault NOT_APPLIED.
The existing Compose wrapper suppresses stderr for credentials; initial precise
cause is not established. All existing services remained running/healthy.
Diagnostic explicit Compose build for the same seven buildable services then
exit0 (cached layers); direct Compose up --detach --wait --wait-timeout420 for
postgres/ebay-sim/etsy-sim/etsy-receiver/live-source/airflow/report/scheduler-observer
also exit0, all healthy; no data reset. The failed startup is not recovery evidence.

The SAME recovery campaign command reran exit0, READY_FOR_REVIEW, fault RESTORED.
Dataset campaign-recovery-7aa6db75e989 / b756e9eb786c; report
runtime/campaign-0af724fbbf2c4bb49f8a961f59e050fe/report.json. ADMITTED10:04:36 UTC;
eBay ff0afff4ac93 actually paused10:08:08.921 UTC and restored10:11:23.133 UTC,
same container ID confirmed running/unpaused. Actual pause was about194s rather
than pretending the planned180s was exact (poll/command overhead). PG/SIM worker/
receiver/Airflow stayed running. Five real failed eBay HTTP requests retained
response_status NULL (no HTTP response), physical metadata.fetched_at10:09:08.878
through10:10:04.557 UTC. Airflow cycle observed up_for_retry; durable collect
attempt1 RETRYABLE, attempt2 SUCCEEDED10:12:08 UTC, no reset/forced task success.
Etsy omitted receipt1201533700000 has two omitted logical messages, zero child
sends, and its final timestamp10:05:21 UTC nevertheless reached core via recovery.
Final observation10:15:11 UTC: eBay2/2, Etsy4/4, Website2/2 final timestamps;
future versions0, pending sends0, retained eBay error audits5. No manual collect,
dbt, publish, task clear or source-selector changes were used to achieve this.

READY_FOR_REVIEW is only final timestamp/send coverage, not all business/money/
line/history correctness or a throughput/latency grade. Sources/contracts and
warehouse schema are unchanged by the controller. Documentation/runbook:
tools/s02_data/CAMPAIGN.md, inspect_campaign.sql and temporary Vietnamese review.
Main live services intentionally remain running for owner UI/DB inspection.
Final post-demo inspection found Docker Airflow unhealthy:24 consecutive old
CLI probes exceeded15s, sometimes AFTER reporting an alive SchedulerJob. Direct
monitor API still reported healthy database/scheduler/DAG processor/triggerer and
new workflow publications continued. Added a live-only stdlib HTTP probe checking
the three required health statuses (not just HTTP200),8s request timeout within
the existing15s Docker budget; no repeated heavy Airflow CLI import. Base Compose
and disposable C health contracts are unchanged. `python tests/test_airflow_health.py`:
6 PASS; piping the exact new script to docker exec python - on the busy live
Airflow:exit0. `python -m tools.s02_data live-up`:exit0, LIVE_SERVICES_READY after
safe drain and deployment; new Airflow container298030975bd4, same state/log/DB
volumes. Startup correctly refused readiness until the API became available;
one8s HTTP timeout at10:33:37 UTC was retained, followed by successful probes.
Final inspect at10:36 UTC: healthy/streak0 and last FIVE probes exit0
(10:35:13 through10:36:17 UTC), while four live schedules were enabled. Explicit
docker exec python -m orchestration.airflow_health also exit0. All seven
healthchecked services healthy; scheduler-observer running. Replay/manual DAGs
remain paused. Read-only post-deploy campaign snapshots still6/6 and8/8 final
timestamps, no future/pending source work; retained error audits5 (global coarse
counter can include later campaigns, not exclusive per-dataset attribution).
This is a bounded readiness check, not a long-duration stability/soak guarantee.
Next: owner reviews normal/outage demos; only then authorize load/burst/soak,
measurement, reconciliation/scoring and bottleneck work. Full M08D NOT complete.
No remote CI, fresh-machine certification or new load acceptance was run.

Regression commands after the fix:

- `python tests/test_s02_campaign.py`:11 PASS (mocked control/restore, not runtime).
- `python tests/test_airflow_health.py`:6 PASS. The delivery9/campaign11/health6
  commands are now wired into offline-smoke.yml; remote Actions NOT run.
- `python tests/test_m08c.py`:21 PASS; `python tests/test_s02_local.py`:19 PASS;
  `python tests/test_s02_delivery.py`:9 PASS.
- `python tests/test_s02_temporal.py`:10 PASS; `python tests/test_m08a_guards.py`:18 PASS;
  `python tests/test_m08b_sources.py`:12 PASS; `python tests/test_m08b_window.py`:3 PASS;
  `python tests/test_m07_operations.py`:9 PASS.
- `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/check_m08c_offline.ps1`:
  exit0,90 PASS, runtime/m08c-offline-08cb07ffda93491bbce2df019abe38c5.json.
- From fixtures/s01: `python verify.py`:10 checks PASS;
  `python -m unittest -v test_tools.py`:10 PASS.
- `python -m compileall -q tools/s02_data test_support/m08c_lifecycle.py tests/test_s02_campaign.py`:
  PASS; interim `git diff --check`:PASS.
- CLI --help, campaign --help and campaign-restore --help:exit0. New
  inspect_campaign.sql sections executed read-only via docker exec psql -X with
  ON_ERROR_STOP in their named DBs:exit0 (initial no campaign rows, real stage/
  pointer results). Interim PowerShell scan:32 task files contain no local
  password values;64 local Markdown link targets resolve. Values never printed.
- Final `python -m compileall -q tools/s02_data test_support/m08c_lifecycle.py orchestration/airflow_health.py tests/test_s02_campaign.py tests/test_airflow_health.py` and
  `git diff --check`:PASS. Recovery campaign-restore command on its already-restored
  report:exit0/NO_ACTIVE_FAULT, no action. Controller source hashes still match
  its runtime report. Final Git main/4c12bc2ddb25d201b9fe2613fa00e24402fe17f8;
  index empty. Owner configs/HANDOFF_SHA256SUMS.txt untouched; no Git write/push.
  Final PowerShell password scan36 task files PASS (values suppressed);65 local
  Markdown targets resolve. Extra files are the live health module/test/override
  and offline CI wiring. No credential/runtime artifacts staged.

### Owner live SIM demo verified read-only — 2026-11-06

Owner ran demo generation; agent inspected logs/health and executed the versioned
tools/s02_data/inspect_delivery.sql through docker exec psql -X with ON_ERROR_STOP.
Latest batch sim-delivery-demo-fa1b8d0bad4a / cf5ea36bbe65 is READY/admitted;
counts8 logical notifications,2 omitted,10 planned,10 completed,10 actual sends.
All child ACKs202 with no pending retry/error. Read-only data_platform query by
webhook ID prefix confirms6 logical inbox and10 physical delivery audits. The two
reordered orders include1359017900003 (shipped ACK08:11:28 UTC before paid08:11:34)
and1359017900001; the duplicate order's paid/shipped IDs each have three planned
sends. Omitted order1359017900000 has two messages with no child sends.

FeatureNotSupported at08:11:02 UTC was traced via filtered PostgreSQL logs to
`cached plan must not change result type` at the same timestamp: a cached SELECT
row shape was invalidated by the delivery-table schema extension. Worker caught
it/reconnected and later ticks/sends succeeded; current health healthy/streak0,
no new lines in --since2m log. This one-time schema-transition failure is retained,
not dismissed as a successful tick; the current demo fully delivered afterward.
No code change, restart or SQL write performed in this diagnosis. Source-to-core,
omitted-receipt acquisition and full M08D acceptance are not established by these
SIM/receiver counts. Recorded times above are UTC (add7h for Asia/Bangkok).

### Live-source unhealthy diagnosis — 2026-11-06

Recovery verification after owner started dependencies: read-only inspect at
08:07 UTC (15:07 Asia/Bangkok) shows healthy, FailingStreak0, last five probes
exit0; heartbeat age0.9s. `docker logs --since 3m --timestamps ...live-source-1`
returns no new lines. Earlier OperationalError lines in --tail output are
historical; worker logs successful ticks only when it emits source changes or
notifications, so idle healthy ticks need not produce console lines. No restart
needed or performed in this verification. This confirms worker liveness, not
new source-to-core acceptance; owner output has no running Airflow scheduler.

Owner reported unhealthy live-source after local startup. Read-only checks:
`docker inspect ... --format '{{json .State.Health}}'` shows missing heartbeat;
`docker logs --tail 65 ...live-source-1` repeatedly reports OperationalError.
SELECT1 connection probes from that container fail before SQL; sanitized exception
and socket lookup confirm temporary DNS resolution failure for hostname postgres.
Owner PostgreSQL is stopped: exit0, OOMKilled=false, finished2026-11-05T17:12:15Z
(Nov6 00:12:15 Asia/Bangkok), logs show fast shutdown and clean shutdown checkpoint.
The other source APIs/receiver/Airflow/report/observer are stopped too; only the
newly started live-source runs. No evidence here of delivery-schema failure.

Cause: worker was started without its stopped dependencies. Earlier --no-deps
worker-update instructions assume an already-running live stack. Recommend live
overlay up --detach --wait for postgres, ebay-sim, etsy-sim, etsy-receiver and
live-source together (not --no-deps); use normal migration prerequisites if absent.
This diagnosis cannot establish who stopped PostgreSQL. No restart/start, SQL
write, heartbeat fabrication, volume deletion, code fix or Git action performed;
healthy recovery has NOT yet been verified. Commands only inspect/SELECT1, with
credentials redacted. An initial PowerShell nested-quote probe had SyntaxError;
stdin-fed Python diagnostic rerun succeeded and supplied the findings above.

## SIM-first implementation checkpoint — 2026-11-05

Owner authorized implementing the SIM slice before M08D campaign work. Added
marketplace_sim/004_delivery_schedule.sql: additive source/account/version
provenance on logical deliveries, one child send-plan table, FK/index/immutable
identity and sealed-plan/progress checks, validation at seal. No source/warehouse
schema or fingerprint changes. Wired fresh bootstrap, PowerShell migration runner
and local generator migration loader. No existing migration file rewritten.

Opt-in channels.etsy_sim.delivery_plan generates seeded delay/reorder/repeats,
retains omit/duplicate **order** quota semantics, validates eligible source pairs
before writes and records planned send count, selected order keys, checksum/tail.
Source generation unchanged. Selection holds order keys, not all payloads; per-
order plans and inserts remain bounded. Generation does an extra preflight pass
for plan checksum before writing; no claim of faster generation or throughput.
Live sender signs at actual delivery time, records retry/ACK progress, retries
per row without dropping a failed send and skips completed children. Legacy
datasets/configs stay on their existing path. New v1 plans are live-only: legacy
playback refuses activation before mutation. generate requires an updated running
live-source module before admitting new planned data; prepare remains inspection-
only. This scoped compatibility limitation is explicit in guides, not silent.

Added sim_delivery_demo.json, config reference, DELIVERY.md and tested read-only
inspect_delivery.sql. Temporary Vietnamese doc has exact manual update/build/
generate/DBeaver steps, expected counts and scope limits at its top. Owner-local
local_now.json/quick_6min.json and unrelated HANDOFF were untouched.

### Actual checks and results

- `python tests/test_s02_delivery.py`:9 PASS (planning, strict config, source
  unchanged, infeasible preflight, legacy SQL, old-worker refusal and replay guard).
- `python tests/test_s02_local.py`:19 PASS; `python tests/test_s02_temporal.py`:
  10 PASS. Initial local regression failed on a mock legacy config with no
  channels; changed capability guard to tolerate legacy missing metadata and
  reran the entire19-test file PASS.
- `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/check_sim_delivery.ps1`:
  exit0, probe PASS, cleanup PASS. Evidence `runtime/sim-delivery-301606dbb4e9.json`
  records input hashes. Real disposable PG16.15: full generator loader and
  website/catalog/mapping preparation, reapplying migration004 twice, legacy
  coexistence, planned8 messages/2 omitted/10 sends. Actual SIM receipt HTTP API
  with RLS and signed sender HTTP:12 network sends after injected500 and lost ACK,
  six distinct non-omitted message IDs,10 completed sends and no completed resend.
  Pending/sealed/identity/version-FK/visibility/contiguous-sequence/reader-denial
  guards checked, DBeaver SQL executed successfully. Receiver is a test HTTP
  endpoint, not the production warehouse receiver; no claim of full ingestion.
- Test setup failures before final PASS: psql meta-command handling in the DB
  adapter, missing disposable DB owner setup, missing synthetic API auth header,
  then an overbroad assertion accidentally selecting an unsealed fixture. All
  fixed in harness, cleanup succeeded; no owner schema reset or hidden PASS.
  Intermediate clean run also passed before final evidence-producing wrapper.
- `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/check_m08c_offline.ps1`:
  exit0,88 component tests PASS; `runtime/m08c-offline-b6b459c22349453b926986f9bbb12751.json`.
- From fixtures/s01: `python verify.py`10 checks PASS;
  `python -m unittest -v test_tools.py`10 tests PASS.
- `python -m compileall -q simulator tools/s02_data tests/sim_delivery_probe.py tests/test_s02_delivery.py`:
  PASS. PowerShell AST parsing of check_sim_delivery.ps1/migrate.ps1 PASS;
  `git diff --check` PASS. Final local-link scan PASS54 targets across seven
  edited guides; task-file scan against local password/secret values PASS (values
  not printed). Final SIM evidence input hashes match the current eight recorded
  files. Diff reviewed, including new untracked task files; Git index empty.

### Protected scope / not run / next

Read-only initial Docker inspection found eight owner services already running
(unlike the earlier C checkpoint). They remain running; no owner migration,
image build/recreation, service stop, DAG change, generator admission or SQL
signature comparison was performed by this task. Disposable checks used private
internal networks, no host ports/owner .env/scheduler; exact random test containers
and networks removed, verified none remain. Only disposable test data was removed.

Not run: fresh full-cluster bootstrap end-to-end, Docker build/deployment of the
owner image, manual DBeaver/browser inspection, new live warehouse/Airflow run,
negative business-data generation, campaign controller/load/soak or remote CI.
The retained C scheduled catch-up failure remains unresolved (latest17 PASS/1
FAIL); this SIM slice does not certify C or D. Next owner action: follow DELIVERY.md
to update the worker and inspect the small live SIM demo. No stage/commit/push.

Owner-requested concrete SIM schema review2026-11-05: documented target SQL for
adding source/account/source_sequence provenance to existing s02.deliveries and
one new s02.delivery_schedule table, with planned-attempt PK, version/message
FKs, pending index, nullable legacy provenance and retry/ACK progress rules.
Source/Website version tables remain unchanged; no payload copy per send. Added
actual-table ER diagram, generation/dispatch algorithm and all18-case coverage
matrix separating prepared delivery faults from required runtime hooks/boundary
regressions. This is a proposal awaiting review, not implemented DDL or verified
campaign behavior. Existing001–003 migrations were read, not edited/executed.
No SIM/config/service/Git changes; latest runtime17 PASS/1 FAIL remains unchanged.
Design-document checks: `git diff --check` PASS; PowerShell local-link scan PASS37
targets across the four edited docs. Proposed SQL was reviewed as a specification,
not executed or claimed migration-tested. Index remains empty.

Further owner design clarification2026-11-05 (documentation only): shared config
means a common schema/directory tools/s02_data/config/, not one hardcoded filename.
Reviewed actual PostgresStore/LivePostgresStore latest-visible queries, Website
worker progress/update guards, source-version constraints and compiled-quality
probe. Expanded temporary Vietnamese doc with why copied rows/different visible_at
do not guarantee repeated observations or notification reorder; proposed one
minimal child physical-send schedule under existing logical s02.deliveries.
Field/identity/progress semantics are review proposals, not new DDL or runtime
support. Added opt-in negative-data recommendations: UNMAPPED source SKU first,
unknown status/gate-block in a separate profile; respect source constraints and
normal generator validation. No config/code/DB/service/Git mutation in this task;
latest runtime17 PASS/1 FAIL remains unchanged. Documentation diff/link checks
are recorded below, not mistaken for campaign acceptance.

Documentation review after checkpoint4c12bc2 (2026-11-05): inspected
test_support/m08c_webhook_probe.py, tools/s02_data/{config,generate,load}.py,
test_support/s02_plan.py, simulator/live_worker.py and temporal delivery DDL.
Current late/reorder probe sends real signed shipped/paid/duplicate-paid requests
against fixture-current receipts and independently recovers an unnotified receipt;
it is not a PG-generated delayed-delivery campaign or full publication assertion.
Existing generator already supports omitted/duplicate Etsy order quotas, but not
separately configurable delay/reorder or spaced physical attempt schedules.

Owner requested pre-D review, not implementation. Expanded the temporary
Vietnamese explanation with exact existing mechanics, dual timelines, data-plan
vs runtime-fault matrix, defaults/questions and sequenced next steps. Synchronized
plan/strategy. Proposed extensions must preserve source-current HTTP semantics,
signed-delivery wall clock, immutable sealed plans, quota compatibility and
generate-only behavior; finalize storage fields before DDL. Config parser currently
rejects the proposed new keys. No owner config/code/DB/container mutation or fault
rerun; no new PASS claim, Git stage/commit/push. Latest runtime17 PASS/1 FAIL stands.
Documentation checks: `git diff --check` PASS; PowerShell local-link scan across
the four edited docs PASS34 targets. Only those four documentation files changed;
owner-local configs and unrelated HANDOFF remain untouched.

**Commit-review update2026-11-05:** owner authorized a local M08C commit and
wants an observable M08D campaign next. A newer owner-side rerun supersedes the
earlier all-green matrix: scheduled_pause_resume/d6dc5866662a4db38d588943b4a48cf3
FAIL at `M08C deadline: scheduled current-state catch-up` (12:57:27–13:15:45 UTC),
cleanup PASS. Latest report is therefore17 PASS/1 FAIL, not18/18 current PASS.
postgres_restart/add3bd6d7a21416aa1fe525d6f5641dd is a newer PASS. The earlier
18-case evidence below remains historical and is not erased. This commit is a
reviewed recovery checkpoint, NOT fresh all-green certification. No fault rerun
or owner-service mutation during this commit review; catch-up failure needs
diagnosis and affected rerun before a renewed complete-C claim.

Next: M08D campaign design uses the existing M08B config (including owner-local
`tools/s02_data/config/local_now.json`) with optional campaign settings, a stable
observable local stack, prepared source data and seeded bounded fault timeline.
Keep generate-only semantics unchanged; controller owns faults, SIM owns source
behavior. Print UI/DB access, record actual fault/recovery events, allow inspection
afterward and report correctness/recovery/performance separately. Existing C
regressions stay separate. This is accepted direction, not implemented support.
Resolve the latest scheduled catch-up failure as a prerequisite; do not silently
carry it into a claimed passing campaign. Owner config files remain unmodified.

Pre-commit checks this task: `python tests/test_m08c.py`19 PASS;
`python tests/test_m08a_guards.py`18 PASS; from fixtures/s01 `python verify.py`
10 checks PASS and `python -m unittest -v test_tools.py`10 tests PASS;
`python -m compileall -q test_support tools tests/test_m08c.py tests/test_m08c_probes.py`
PASS. `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/check_m08c_offline.ps1`
exit0,88 tests PASS, evidence runtime/m08c-offline-b8778e9c88044deebde8c0526670cb5e.json.
`python -m test_support.m08c report --id 563f55c17bab` reads17 PASS/1 FAIL
(report CLI exit0 only means it rendered successfully). No runtime suite or
post-recovery report SQL/UI rerun merely to commit. Existing14 report/UI results
remain historical. Diff reviewed; whitespace/credential-scope checks required
before explicit task-file staging; exclude owner configs, runtime and HANDOFF.

Read-only diagnosis candidate: the retained test airflow-state contains
`polling-drain`; the test DAG disables scheduling when that marker exists, while
scheduled_pause_resume removes only `m08c-drain`. Earlier maintenance_drain creates
the shared marker. This suggests retained-state repeatability, not proof of a
production acquisition bug. No marker removed or fix declared verified here;
confirm with scoped regression/runtime rerun as the next prerequisite.

Owner resumed M08C on2026-11-05. Current branch main, HEAD21075d3 (M09).
**M08C local acceptance PASS:** all18 declared runtime cases have passing evidence,
including clean reruns of task clear, lease fencing, receiver audit and stage
resume. Post-recovery read-only S01/report regressions PASS14; final offline
component suite PASS88. Full per-case evidence and limits appear in the final
M08C acceptance section below. M08D has NOT started; owner review is next.
Initial read-only Docker check: Engine29.9.2, total4109402112 bytes, no running
containers. Owner stack remains stopped; do not start/stop it merely for tests.
Retained disposable baseline563f55c17bab was validated and reused. No Git
stage/commit/push was authorized during that execution task; owner configs/unrelated files remained
untouched. The execution notes below are historical progress, not current health.

## Historical execution notes (before final M08C acceptance)

Owner-requested explanation update2026-11-05: expanded
`TAM_THOI_M08_GIAI_TRINH_VI.md` in Vietnamese with current M08C scope, implementation
map, all18 case expectations, practical failure semantics, safe local commands,
evidence interpretation and acceptance limits. Historical sections are retained
and explicitly superseded. Documentation-only task: no runtime faults/services
rerun, no Git staging/commit/push. Diff whitespace and local document links checked.

Resumed execution evidence (disposable563f55c17bab only): failed_gate PASS
`m08c-failed_gate-4b6b86f9f4c2445aaa8ac3d69e85d851.json`; data_quality PASS
`m08c-data_quality-caa24d5cf01f47f591b1ca0c0edb892a.json`; api_failures PASS
`m08c-api_failures-bf35941dec204b1bb6262f1d0e27a737.json`; late_reordered_webhooks
PASS `m08c-late_reordered_webhooks-36dfc3e4974d485896d7956200400e81.json`.
Files live under runtime/isolated/m08a-563f55c17bab/evidence. The first validates
the exact injected dbt failure, explicit abort and unchanged full core/mart/pointer
signature. Quality uses actual compiled SQL with literal bad inputs, not a full
source-to-publication bad-data campaign. HTTP/webhook cases assert real API/raw/
work/checkpoints within their declared scopes; they are not load certification.
Further abrupt/lifecycle cases are executing; do not treat the whole matrix as PASS.

Lifecycle setup failures retained: scheduled_pause_resume/e56f5ff3... exceeded
the180s discovery bound after copying its DAG into already-running Airflow;
read-only config confirmed dag_processor.refresh_interval=300, with no import
errors. Fixed install order to create stopped test container, copy DAG, then
start scheduler. Intermediate70a4d693... failed on unsupported Compose create
--no-deps; local create --help confirmed --no-recreate, now used. Both cleanups
PASS; no owner service started/stopped. A new lifecycle attempt is running.

The maintenance prototype's dummy wait(False) timeout has been replaced by the
actual live drain algorithm against the test DAG. Public drain defaults remain
unchanged. Added signature/readonly tests, selected-DAG drain/timeout/foreign-run
guards and install-before-start regression. Offline wrapper PASS80 tests in
runtime/m08c-offline-d408a1accf284303a59bd3535e31c91a.json (before install-order
guard addition); current host C guards PASS14. Shared-algorithm/source hashes are
included in subsequent case reports. Full updated regression will be rerun.

Owner paused further M08C campaigns on 2026-11-01 and requested a reviewed local
checkpoint commit followed by M09 CV/demo packaging. M08C remains INCOMPLETE;
M08D is deferred, not implicitly passed. M09 packaging may proceed with explicit
limitations; the full release-certification gate is not waived.

No M08C host process or isolated container remained running at the pause check.
The current test loop had already exited after failed_gate, with cleanup PASS;
subsequent cases did not start. Main services/data were not stopped or reset.
Main Airflow is running but currently unhealthy; this availability issue is OPEN.

Fresh disposable baseline `563f55c17bab` passed61 steps. The authorized owner
maintenance window restored the exact owner Airflow container healthy, restored
the original DAG pause states, and verified unchanged protected data signature
and PostgreSQL system identity. The overall window FAILED its first C probe;
restoration PASS is not a complete campaign PASS. Evidence:
`runtime/isolated/c-window-69859f6f01af4c7f9c11a3d19856e819`.

- Branch `main`, checkpoint HEAD `63c36c986d42fa5812ac73bc2afdbac78ed50b91`:
  `feat: checkpoint live S02 workflow and partial recovery verification`.
  Local commit explicitly requested by owner; no push. Previous M07 HEAD was
  `7f459aba8ac2b545ac14b82259a6579bcd25f91b`. Preserve unrelated HANDOFF_SHA256SUMS.txt
  and owner-customized local_now.json/quick_6min.json, excluded from the commit.
- M01-M07 accepted previously; M08A baseline/guards passed locally. M08B daily
  live finite correctness passed; owner requested cleanup and M08C implementation.
- M08C **paused, NOT accepted**. M08D deferred; M09 packaging requested. Component checks
  and a selected runtime case cannot certify the complete required matrix.
- Previous detailed results, failures and intermediate checkpoints are retained
  unchanged in [the historical log](history/STATUS_2026-11-01.md). Older PASS
  evidence is not proof of current health or a new code revision.

## Primary workflow / documentation cleanup

Only one daily operator path: `python -m tools.s02_data live-up`, then manual
`generate --config PATH` any number of times. One existing PostgreSQL/Airflow
stack, retained data and ordinary `.env` ports/credentials. No dataset/campaign
selection, source reset or per-cycle shell trigger. See
[operator guide](../tools/s02_data/README.md), [config](../tools/s02_data/CONFIG.md)
and [current architecture](16_M08_LIVE_LOCAL.md).

The documentation map now separates current live guidance from historical
RAM/temporal/replay regression references. The replay section of the operator
guide is collapsed. Historical implementations/tests are retained because they
are regression dependencies, not removed based solely on file count. The owner's
temporary Vietnamese audit is retained. No application DDL, source contract,
fingerprint, mapping selection or business SQL change in this cleanup.

## M08B review

Retained strict evidence: `runtime/m08b-live-check-20261101T050453Z.json`, exit0:
`python -m test_support.m08b_live_check --wait-seconds 1200
--verify-reread-seconds 600 --require-observed-changes`.
Four batches/72 new orders plus3 retained S01; three source paths reconcile;
observed changed orders Website5/eBay6/Etsy10; history105 raw-linked; omitted1
notification recovered; duplicate2 IDs preserve audits; extra scheduled cycles
raw950->954 with stable logical signatures. Current-checker follow-up051153Z PASS.
These are finite correctness results, not load/latency or M08C certification.

Fresh read-only review during this task:

- Docker Compose/Engine and Python3.12.7 available; host lacks `psycopg`.
- PostgreSQL, both APIs, receiver, live-source and report healthy; observer running.
  Airflow running but healthcheck reported **unhealthy**; scheduler/processor/
  triggerer have recent heartbeats. Four periodic DAGs unpaused, three manual/
  replay DAGs paused. Last2h contained an Etsy recovery failure and successes
  across all four paths. No automatic restart/pause/reset performed.
- Earlier owner query investigation: Website order `12-398751100019-10001`
  has three prepared transitions13:17:31/13:17:59/13:18:15 +07, but only one raw
  observation13:33:27.874 +07 (CANCELED), so history correctly contains one
  observed snapshot. Collect gap13:03..13:33 needs availability investigation;
  missing history must not be fabricated. `source_order_id` collisions across
  source/account scopes are valid; identity is the source/account/order triple.
- Prior measured eBay convergence19m37s and current build/slot delays are known
  performance limits. M08D must measure/fix bottlenecks, not claim capacity from
  generated order counts. Current availability failure is not declared resolved.

## M08C implementation and verification

Contract/runbook: [17_M08C_RECOVERY.md](17_M08C_RECOVERY.md).
Machine-readable required inventory: `test_support/m08c_cases.json`.
Host CLI: `python -m test_support.m08c plan|offline|run`.

Implemented selected-case runner: accepted disposable M08A/S01 target only;
checks marker/config/resources/DB identity and no active test schedules/batches;
memory preflight before starting PostgreSQL/APIs/receiver; CLI-only one-shot tests,
not a second scheduler. Per-case latch, hashes, private logs, JSON outcome and
finally stop of only services it started; volume/evidence retained. Main is never
a fault target. The owner authorized temporary owner-Airflow stop/restore only
when idle; that is not permission to stop producers or PostgreSQL.

Implemented probes: durable raw/freeze hook interruption with same-manifest retry,
actual dbt failure retaining last-good publication, existing real SQL/HTTP lease
fencing/budget replay, receiver security/duplicate audit and graceful test-PG
persistence. New offline HTTP tests exercise transient429/500, five-attempt
exhaustion, mid-page retained audits/replay and malformed200 byte retention.
Mock audit connections are explicitly NOT PostgreSQL checkpoint proof.

Earlier checks (continuation/pause results below supersede outdated progress):

- `python -m test_support.m08c offline`: FAIL, host missing psycopg for five
  suites; three stdlib suites passed. One script also lacked PYTHONPATH; runner
  now explicitly supplies repository root. Evidence
  `runtime/m08c-offline-adeb50dc7e7945db9ed59dbced793498.json` retained.
- Same offline command in a network-disabled256MiB CLI container: initial FAIL
  due to omitted read-only migration mounts in test_s02_live (3 errors), while
  the other7 suites passed. Corrected full-input rerun is recorded below; no
  pipeline DB writes, second scheduler or main-service changes for either run.

NOT RUN: full M08C fault matrix, abrupt process-loss/commit-ACK/pause-resume and
service-outage campaigns, remote CI, fresh full S01 runtime rebuild. Missing
required cases remain visible as NOT_RUN; they are not silently moved to M08D.
Next: validate the available probes, establish a current safe disposable baseline
and execute the remaining deterministic lifecycle cases before M08C sign-off.

### Final checks for cleanup / initial M08C code

- `powershell -NoProfile -ExecutionPolicy Bypass -File
  infra/scripts/check_m08c_offline.ps1`: PASS, exit0, final evidence
  `runtime/m08c-offline-f24b362754034a11bf28942bbc603c64.json`.
  Eight suites/69 tests: live27, C guards11, C HTTP4, M05 HTTP7, M06 unit7,
  draining5, cycle4, scheduling4. Container image
  `sha256:579a2c4a4f1cbd4d895e3af15cf2f93d43f7296b1628515baafe5f6e55338d5f`;
  no warehouse network, `.env`, second scheduler or Docker socket. Inputs RO,
  ignored evidence directory RW, memory256MiB/CPU0.5. Earlier corrected
  bac9fe7ace704a25b824c886ddc773c4 and fdd6c561b0b04044bd45832eade6f452
  offline results also PASS; the latter preceded the fixed test config change.
- Eight additional host suites, each `python tests/NAME.py`: PASS77 tests:
  test_s02_diverse4, test_s02_temporal10, test_s02_local19, test_s02_clock3,
  test_s02_local_scheduled8, test_m08a_guards18, test_m08b_sources12,
  test_m08b_window3. Combined146 component/unit tests, not runtime certification.
- First additional-host regression loop FAIL: test_s02_local expected18 orders
  but read the owner's edited quick config (76). Fixed TEST dependency, not
  generator behavior: new `tests/fixtures/s02_quick.json` is deterministic and
  used by local/live tests. Owner quick/local_now/observe configs left untouched.
- From fixtures/s01: `python verify.py` PASS10 checks;
  `python -m unittest -v test_tools.py` PASS10 tests. One attempted C guard command
  accidentally used this cwd and failed to find tests/test_m08c.py; root rerun
  PASS11 tests. No command failure counted as acceptance.
- `python -m test_support.m08c plan`: exit0,18 required entries, five selected-case
  runners available,13 required entries without a runtime runner still explicit.
- `python -m test_support.m08c run --id 49a6b80472b1 --case lease_fencing
  --confirm-disposable`: expected refusal, exit1 (`Config/env/base hash mismatch`)
  BEFORE service/case mutation. All retained accepted A IDs inspected use an
  older base hash. They are not adopted by editing their marker; fresh current
  A baseline is needed. This is a negative safety check, not lease runtime PASS.
- Conditional owner stop permission received, but not exercised: subsequent
  read-only check still found four running owner DAGs and unhealthy Airflow
  (failing streak46). Docker total3.827GiB, Airflow1.553GiB at sample. No producer,
  receiver, PostgreSQL or owner Airflow stop/restart/pause, no dataset reset.
- `python -m compileall -q tools ingestion simulator transformation orchestration
  reports test_support tests`: PASS. `git diff --check`: PASS; explicit21-file
  task whitespace scan and current documentation local-link scan PASS. Index
  empty. No stage/commit/push, no M08D work.

### Continuation results and owner pause (2026-11-01)

The following runtime commands used `python -m test_support.m08c run
--id 563f55c17bab --case CASE --confirm-disposable`. Evidence filenames below
are under `runtime/isolated/m08a-563f55c17bab/evidence/` (ignored/private).

| Case | Actual result | Evidence JSON |
| --- | --- | --- |
| lease_fencing | PASS, rollback-only SQL/HTTP fencing/budget test; not killed-worker proof | m08c-lease_fencing-e46e20ab6dea4d3b9776173372d6ecba.json |
| receiver_audit | PASS, actual signed HTTP and physical duplicate audits | m08c-receiver_audit-d14e54fbc29046b999fec8058ffcbf3b.json |
| stage_resume | PASS, durable raw/freeze hooks, retry, dbt/publication; not process kill | m08c-stage_resume-a8c79c209c7a4c498d1aa6e13dad0c78.json |
| failed_gate | FAIL before injected dbt test: probe read uses a role lacking SELECT on core.orders_current | m08c-failed_gate-0992d03b40964011b6e8d60abf8025c2.json |

Initial failed attempts are retained: nested RO/RW mount (790511...), missing
private controller signing key (4cc72d...), controller mount ordering (95f005...).
Those harness issues were corrected before the three selected PASS results.
The failed_gate privilege problem is NOT fixed or waived. Do not widen production
roles merely to make an assertion pass; a future probe must use an appropriate
read-only report connection. Cleanup PASS retained volumes/audits, stopped only
the started test services, and prevented later cases from starting.

All18 inventory entries now have runner code, but the remaining15 do NOT have
passing continuation runtime evidence. Abrupt process/commit-ACK, source-worker,
task-clear, lifecycle/outage and real scheduled C tests remain unverified code.
No test-only C DAG was installed in the owner Airflow. No M08D load/soak campaign
or remote CI ran. No fresh runtime campaign is authorized by this pause request.

Review checks after pause: `python -m compileall -q tools ingestion simulator
transformation orchestration reports test_support tests` PASS;
`python tests/test_m08c.py` PASS12 tests; `git diff --check` PASS.
Only offline review checks may run during packaging; no new fault campaigns.

- `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/check_m08c_offline.ps1`:
  PASS, exit0, eight suites/72 tests (27+12+6+7+7+5+4+4). Evidence:
  `runtime/m08c-offline-db3eaac38cdb4df49eeaab43570b4e72.json`.
- Additional host loop `python tests/NAME.py` for test_s02_diverse,
  test_s02_temporal, test_s02_local, test_s02_clock, test_s02_local_scheduled,
  test_m08a_guards, test_m08b_sources, test_m08b_window: PASS77 tests.
  Combined149 component tests, not a runtime certification; the standalone
 12 guard rerun overlaps that total and is not added again.
- From fixtures/s01: `python verify.py` PASS10 checks and
  `python -m unittest -v test_tools.py` PASS10 tests.
- Candidate-file scan found no local `.env` password values or private-key/token
  patterns. Git identity is configured. Runtime, `.env`, caches and unrelated
  HANDOFF_SHA256SUMS.txt are excluded from the checkpoint commit.

## M09 documentation packaging (owner-prioritized partial handoff)

Implemented [18_PORTFOLIO.md](18_PORTFOLIO.md): English CV bullets, project pitch,
architecture/ownership diagram, offline S01 and changing-source demo routes,
fresh bootstrap prerequisites, code-review route, sanitized evidence index and
explicit operational/scale limits. README and documentation map now link to one
portfolio entrypoint. No application/schema/source semantics changed by M09.

The owner requested documentation/CV work before completing C/D. This changes
delivery priority, NOT the evidence rules. Packaging is not full M09 release
acceptance: independent-machine reproduction, complete C/D, remote CI and browser
visual checks remain pending. No extra runtime campaign or service mutation ran
while packaging. M09 changes remain unstaged for owner review; the requested
checkpoint commit covers the preceding M08 work only.

Packaging checks actually run (all exit0):

- `python -m tools.s02_data --help` and `python -m test_support.m08c --help`:
  PASS, parser/help only, no source generation or Docker calls.
- `python -c "import json; from pathlib import Path; from tools.s02_data.config import validate; validate(json.loads(Path('tools/s02_data/config/observe_6min.json').read_text()))"`:
  PASS, versioned demo config validates without preparing data.
- PowerShell local Markdown-link validation across README.md, docs/README.md and
  docs/18_PORTFOLIO.md: PASS64 existing local targets; external URLs not fetched.
  New portfolio document trailing-whitespace scan PASS.
- `git diff --check`: PASS; final diff inspected; index empty after checkpoint.
  No M09 application deployment, fresh bootstrap, new scheduled runtime, remote
  CI or browser screenshots performed. Full M09 runtime release remains pending.

Handoff: review the unstaged M09 package/CV wording. Resume health investigation
and incomplete C/D only when the owner requests it; do not auto-start campaigns.

### Recruiter-facing README presentation (2026-11-01)

Owner requested a polished English project introduction for the GitHub link on
their CV. README now leads with the business problem, actual dashboard output,
source-to-report architecture, engineering decisions, stack and a code-review map.
Milestone backlog/unfinished work stays in STATUS/plan instead of the landing-page
narrative. This is presentation separation, not removal or completion of those
requirements. The README still identifies synthetic local source interfaces and
does not claim real seller integration, performance certification or full event
history. No application, migration, source contract or environment change.

Added actual local-browser PNG captures:
`docs/assets/dashboard-overview.png` (126708 bytes) and
`docs/assets/dashboard-operations.png` (132667 bytes). A dedicated hidden Chrome
profile opened localhost:8501, switched read-only report workspaces and captured
the rendered pages through CDP; no mock data or image edits. Both images were
visually inspected: synthetic channel/account IDs and charts, no credentials or
customer details. Existing availability warnings remain visible, unmodified.
The dedicated browser closed after capture; the helper/profile remain ignored
under runtime/readme-capture, not source assets. Services were not restarted,
source data was not generated, and recovery/load tests remain paused.

Actual checks:

- `Invoke-WebRequest http://localhost:8501/_stcore/health`: HTTP200.
- Initial sandbox browser/CDP attempt: FAIL (`fetch failed`); separate authorized
  hidden-browser launch and `node runtime/readme-capture/capture.cjs`: PASS, exit0,
  both rendered screenshots captured. No dependency install/download required.
- PowerShell README/portfolio local-link and heading-anchor scan: PASS32 targets,
  including both PNGs; GitHub-hosted Mermaid rendering not directly tested.
- From fixtures/s01: `python verify.py` PASS10 checks;
  `python -m unittest -v test_tools.py` PASS10 tests.
- `git diff --check`: PASS. Diff inspected; all current task changes remain
  unstaged. No stage, commit or push requested/performed for this README revision.

Next: owner reviews README in Markdown/GitHub preview and the actual screenshots;
continuing runtime stabilization remains a separate explicit request.

### Owner-requested operations dashboard layout revision (2026-11-01)

Scope: presentation refinement during M09, not resumed C/D campaigns. Removed
the exact canonical-product text input from the UI (backend product filtering
unchanged), removed the channel metric selector and technical version KPI/chart.
Overview now has operational counts, a separate two-column money row, and fixed
orders/units channel charts with short direct titles. Supporting read metadata,
publications and version evidence moved to the business-page footer; availability
warnings are retained immediately above it. Warehouse/money/history semantics,
filters, bounded detail/search, roles and source contracts are unchanged.
The current reporting contract09 and reports README are synchronized.

Actual commands/results:

- `python tests/test_m07_operations.py`: PASS9 tests.
- Common container prefix: `docker compose --env-file .env --file infra/compose.yaml
  --file infra/compose.live.yaml --profile live run --rm --no-deps
  --volume D:/hocTap/git/multi-channel-order-platform/tests:/app/tests:ro
  --entrypoint python report`.
  With `/app/tests/test_m07_layout.py`: PASS4 offline AppTests using explicit
  mocked UI data, no DB acquisition. Initial FAIL1: test used nonexistent
  Expander.expanded API; corrected assertion to Expander.proto.expanded, rerun PASS.
  First development run additionally mounted reports read-only before rebuilding.
- Same prefix with `/app/tests/test_m07_report.py`: PASS10 tests on real retained
  read-only report-role SQL and UI, including money grain, scope, bounded queries,
 120-rule parity, history and role security. Initial FAIL1: UI test compared all
  available live dates (1115 orders) to S01-only3. Added an explicit S01 date
  selection to the TEST; rerun10/10 PASS, no source/warehouse mutation or reset.
- Deployment: `docker compose --env-file .env --file infra/compose.yaml
  --file infra/compose.live.yaml --profile live up --detach --build --no-deps
  --wait --wait-timeout 120 report`: PASS, only report recreated, healthy.
  Image sha256:43ab48f3eac1d29aa224106bec308f58329c21995c7c00f244632050e0eac21c.
  No Airflow/PG/SIM restart, pause-state modification or data generation.
- `node runtime/readme-capture/capture.cjs`: PASS, actual rendered app captured
  in a dedicated hidden local browser, then closed. Visually inspected both PNGs:
  full currency amounts visible at1600px; no product input/version selector;
  actual business charts, no credentials/customer details. Replaced task-owned
  README images: overview117718 bytes, operations121179 bytes. No image edits.
  README overview description/alt text updated for operational KPI labels.
- `python -m compileall -q reports tests/test_m07_layout.py tests/test_m07_report.py`:
  PASS. From fixtures/s01, `python verify.py` PASS10 checks and
  `python -m unittest -v test_tools.py` PASS10 tests.
- README/report-guide local link scan PASS20; `git diff --check` PASS.
  Git diff reviewed; changes left unstaged. No commit or push this task.

Handoff: owner refreshes localhost:8501 and reviews updated README screenshots.
No new C/D runtime-acceptance or capacity claim follows from this UI change.

### M09 reviewed local commit request

The owner reviewed the portfolio README and dashboard presentation, then explicitly
requested a local commit of M09-related changes. Commit scope: README, portfolio
guide, plan/documentation links, reporting presentation contract, dashboard UI,
updated real screenshots, UI regressions and this evidence log. No M08 recovery
implementation, local secrets, runtime or owner data/configuration is added.

Pre-commit reruns: `python tests/test_m07_operations.py` PASS9;
`python -m compileall -q reports tests/test_m07_layout.py tests/test_m07_report.py`
PASS; from fixtures/s01, `python verify.py` PASS10 checks and
`python -m unittest -v test_tools.py` PASS10 tests; `git diff --check` PASS.
The unchanged dashboard revision retains its previously recorded PASS4 layout
and PASS10 SQL/UI checks; these container/runtime tests were not rerun merely
to commit. No service/data mutation, new recovery/load run or push in this task.

Excluded owner/unrelated files: HANDOFF_SHA256SUMS.txt,
tools/s02_data/config/local_now.json and tools/s02_data/config/quick_6min.json.
Full release-certification gates remain as recorded; this commit packages M09
presentation/demo scope, not completion of the paused C/D work. Read Git log for
the resulting SHA; a commit's own SHA is not embedded in its files.

## Final M08C local acceptance — 2026-11-05

Result: **18/18 declared runtime cases PASS**, final component suite88 PASS and
post-recovery report/layout14 PASS. This supersedes the historical in-progress
and paused C notes above. M08D is not started. Changes remain unstaged for owner
review; no commit or push. HEAD remains21075d35d997872b504ab7784715e2aec9adce17.

### Scope, decisions and protected state

Reused accepted disposable M08A S01 scope563f55c17bab after config, ownership,
mount, baseline and PostgreSQL identity guards. Its PG system identifier is
7703125723137740838. The retained61-step baseline was not freshly bootstrapped.
Docker Engine29.9.2 reported4109402112 bytes RAM; cases ran sequentially with
resource preflight before service creation, including the stricter scheduled
topology gate. Test services stopped after each case; evidence/data retained.

Owner containers were already stopped at task start and remained stopped with
their original identities. No owner service restart, DAG pause-state write,
database reset, volume deletion or source-profile switch was performed. Owner
SQL signatures/current service health were not rechecked by starting its DB.
No source contract, target schema, fingerprint or business transformation change.

Corrections: business signatures use existing publisher read permissions inside
a repeatable-read, read-only transaction, not new grants. The real maintenance
drain algorithm is shared with the scoped test; public default DAGs are unchanged.
Test DAG installation precedes scheduler startup; discovery checks the latest
serialized version. Real task clear is constrained to one verified failed test
run, with durable budgets unchanged. Signal tests await actual worker heartbeat.
Offline containers override inherited owner labels; resource guards are not
weakened. See recovery runbook for the installed Airflow CLI selection quirk.

### Runtime commands and retained evidence

For every row below, executed from repository root, exit0 and cleanup PASS:

```powershell
python -m test_support.m08c run --id 563f55c17bab --case CASE --confirm-disposable
python -m test_support.m08c report --id 563f55c17bab
```

Replace CASE with the first column. Report returned
`all_required_cases_passed: true`; its generic `milestone_complete: false` is
deliberately not an automatic human sign-off. Evidence directory:
`runtime/isolated/m08a-563f55c17bab/evidence/` (private ignored local artifacts).

| Case | Latest passing evidence filename |
| --- | --- |
| api_failures | m08c-api_failures-bf35941dec204b1bb6262f1d0e27a737.json |
| receiver_audit | m08c-receiver_audit-3041d13e79b1415d96aaa7e2c37515d4.json |
| late_reordered_webhooks | m08c-late_reordered_webhooks-36dfc3e4974d485896d7956200400e81.json |
| stage_resume | m08c-stage_resume-65e4e1152e1a4e97b9dabac840d8f95c.json |
| abrupt_raw_inbox | m08c-abrupt_raw_inbox-51df28ef31b74a938d2f515de7793936.json |
| lease_fencing | m08c-lease_fencing-23644b7611f34a379665778f8197a9d8.json |
| abrupt_lease_owner | m08c-abrupt_lease_owner-ea045c4fff8748b69705146dd69156a8.json |
| failed_gate | m08c-failed_gate-4b6b86f9f4c2445aaa8ac3d69e85d851.json |
| data_quality | m08c-data_quality-caa24d5cf01f47f591b1ca0c0edb892a.json |
| abrupt_freeze_dbt | m08c-abrupt_freeze_dbt-2beba48d036747ddaabbefbcf61bd7e4.json |
| publish_atomicity | m08c-publish_atomicity-2519135e96d44e23af3b625ad4210c4b.json |
| task_clear_budget | m08c-task_clear_budget-bd0698e98b4c4a97af4c51538705f067.json |
| postgres_restart | m08c-postgres_restart-13126ee38458469abd4566bfb743bf13.json |
| other_service_restarts | m08c-other_service_restarts-367d159b29ce41058dd7bfc4761f64b3.json |
| abrupt_service_loss | m08c-abrupt_service_loss-6794446a94d249bbb434f6a670cad6eb.json |
| scheduled_pause_resume | m08c-scheduled_pause_resume-36ad921736244ecd8bcd44ce01c4c368.json |
| maintenance_drain | m08c-maintenance_drain-2bd67e8066f44d85b8cea1a5696158b1.json |
| outage_visibility | m08c-outage_visibility-28523e1d971445b78f6ae3774e059757.json |

Boundaries: HTTP failures exercise actual collector raw/checkpoint behavior;
late/reordered notifications assert inbox/work/raw, not every published transition.
Lease fencing is rollback-only SQL/HTTP; abrupt owner loss has a separate case.
Quality uses compiled SQL with literal invalid inputs, not a full bad-source E2E
campaign. Idle service persistence is separate from busy raw/dbt/publisher kills.
Publisher checks full core/marts/pointer rollback and commit-before-ACK recovery.
Scheduled pause/resume has two real scheduled successes and one newly observed
history version, never reconstructed missed transitions. Task-clear's expected
failed DAG preserves five durable attempts despite Airflow try six. Outage checks
waited actual91-second sample age and121-second heartbeat expiry; no timestamp
rewrites. Source-worker coverage includes PG-backed HTTP/RLS/faults and signals.

### Regression commands and results

- `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/check_m08c_offline.ps1`:
  exit0,88 tests PASS. `runtime/m08c-offline-402e015534ff4d859b5dc2ff85a93ec8.json`.
  Network-isolated CLI container, no scheduler, env file or Docker socket.
- `python tests/test_m08c.py`:19 PASS, also included in the88 above.
- `python tests/test_s02_temporal.py`:10 PASS;
  `python tests/test_m08a_guards.py`:18 PASS;
  `python tests/test_m08b_sources.py`:12 PASS;
  `python tests/test_m08b_window.py`:3 PASS;
  `python tests/test_m07_operations.py`:9 PASS (52 additional host tests).
- From `fixtures/s01/`: `python verify.py`:10 checks PASS;
  `python -m unittest -v test_tools.py`:10 tests PASS.
- `$env:PYTHONPATH=(Get-Location).Path; python runtime/m08c_report_regression.py`:
  exit0, ten actual SQL/report UI tests plus four mocked layout tests PASS.
  Ignored guarded local helper used only disposable PG and a one-shot report CLI,
  checked PG identity and stopped PG in finally; no seeding/reset/warehouse writes.
  Evidence `m08c-report-regression-79dfa78d1d0f4929a1f1aba4ec0abb7c.json` in the
  same case evidence directory. Retained S01 Oct17 cohort:3 orders,4 lines,6 units,
  USD124 original merchandise and6 observed versions; Nov5 test orders excluded.
- `python -m compileall -q test_support tools tests/test_m08c.py tests/test_m08c_probes.py`:
  PASS; `git diff --check`: PASS. Final PowerShell checks:71 local documentation
  links resolve; latest runtime JSON per case18 PASS; offline JSON totals88 PASS;
  task-file scan against local credential values PASS (no values printed).
  `docker ps` empty; `docker ps -a --filter label=com.docker.compose.project=multi-channel-order-platform`
  confirms the same eight original owner container IDs, all stopped from before
  this task. Diff reviewed; `git diff --cached --name-only` empty. Owner configs
  and unrelated HANDOFF_SHA256SUMS.txt remain untouched.

### Failed attempts retained and repaired

- scheduled_pause_resume/e56f5ff3231948f680df4b3e21a9ef87:180s discovery deadline
  missed the actual300s directory refresh; install before startup fixes it.
  Intermediate70a4d693ad3c4962b5ad938a99bd46d2 used unsupported Compose
  `create --no-deps`; local help confirmed `--no-recreate`. Both cleanup PASS.
- maintenance_drain/45df9a7ce9cb454d8d5c89e811124b6c: assertion wrongly required
  exactly one serialized DAG row; latest-version query preserves metadata history.
- task_clear_budget/7b9164399e7240a0af057eeae1098f4b passed with explicit scoped
  operator clear, companion operator-task-clear-5fadcab7167440d9be5af075416cb8ff.json,
  after regex selection silently cleared nothing. The latest bd0698 clean run
  above is fully automatic and supersedes this operator-assisted evidence.
- other_service_restarts/eea74cc9a593494db9ea56eba2b5fea7: SIGTERM raced handler
  installation in the test child. Actual-tick readiness barrier fixed the harness;
  the full case reran PASS, without relaxing expected signal outcomes.
- Scheduled preflight correctly refused a topology while an offline CLI inherited
  owner Compose labels. No case services were created. Explicit CLI labels fixed
  classification; RAM thresholds unchanged and subsequent full preflight PASS.
- Report helper initially refused an old A marker without an explicit profile;
  corrected to the existing guard's legacy `m08a` default before any service start.
  A fixture verification first invoked in the wrong directory could not find its
  script; correct fixture-directory checks above PASS. Diagnostic import/SQL/rg
  errors were read-only and are not acceptance evidence.

### Not run / next task

No M08D load/burst/soak or throughput claim, remote GitHub Actions run, fresh
independent-machine reproduction, fresh A bootstrap, owner-stack health check or
new owner SQL signature comparison. This is bounded local recovery acceptance,
not production certification. Review this diff and the case boundaries; only
after owner approval proceed to M08D. No Git action is authorized in this task.

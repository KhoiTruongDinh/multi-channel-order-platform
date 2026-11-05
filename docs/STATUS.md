# Actual project status

Updated: 2026-11-05 (Asia/Bangkok).

## Current checkpoint

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

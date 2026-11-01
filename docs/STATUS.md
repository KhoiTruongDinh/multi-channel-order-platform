# Actual project status

Updated: 2026-11-01 (Asia/Bangkok).

## Current checkpoint

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

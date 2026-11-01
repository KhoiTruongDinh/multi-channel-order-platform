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

- Branch `main`, HEAD `7f459aba8ac2b545ac14b82259a6579bcd25f91b` (M07).
  This is the pre-checkpoint HEAD. The owner now explicitly authorizes a local
  checkpoint commit, not a remote push. Preserve unrelated `HANDOFF_SHA256SUMS.txt`.
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

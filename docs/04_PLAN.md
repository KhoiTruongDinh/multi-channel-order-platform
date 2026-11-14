# D. Delivery plan and AI coding workflow

Current M08B daily-live revision (2026-11-01): start-once/manual-append workflow
and whole-M08 fault review are in16_M08_LIVE_LOCAL.md. Its current acceptance
status is in STATUS. Older completion statements below describe prior isolated/
replay revisions, not automatic sign-off of changed operator workflows.

## D1. Milestones and completion evidence

Work one milestone at a time. Each milestone has a bounded output, acceptance checks, an evidence record and a proposed Git checkpoint. Codex implements and verifies the milestone, leaves changes unstaged, and stops for owner review. After review, the owner stages, commits, and pushes when ready. Codex performs a Git write action only when the owner explicitly requests that action in the current task. Do not claim that generated code has run.

M00 — Repository handoff: version business/source specifications, the proposed architecture/report contract, AGENTS.md, the milestone plan, STATUS and existing fixed fixtures. Acceptance: reference links resolve locally and fixture checks/tests pass. This is a historical completed checkpoint; inspect Git for current repository/remote state. Suggested owner commit: docs: establish S01 project contract and milestones.

M01 — Foundation and schema: inspect local tools; choose/pin compatible dependencies; add minimal PostgreSQL Compose, roles, migrations and the target field dictionary. Finalize required types/nullability, PK/FK/unique keys, evidence links and report-read views before dependent models. Acceptance: clean DB bootstrap, migration rerun policy, role boundaries and restart persistence; review the schema diff. Suggested owner commit: feat: bootstrap storage and schema contracts.

M02 — Website acquisition: implement fixed source-state playback and consistent read-only extraction into raw plus run/checkpoint audit. Acceptance: all three scheduled observations saved; interruption cannot falsely complete a window; acquisition replay is auditable and does not bypass source boundaries. Suggested owner commit: feat: ingest website S01 with durable checkpoints.

M03 — Website dbt and release: add source staging, mapping, observed history/current, marts, tests and atomic publication. Acceptance: website one current order/line, three observed order versions, original two units/USD40; replay does not inflate versions; failed tests leave previous publication intact. Verify report SQL before building elaborate visuals. Suggested owner commit: feat: transform and publish website orders with dbt.

M04 — Airflow website workflow: wrap the tested CLI/dbt/release commands in a bounded DAG with run IDs, attempt budgets and failure handling. Acceptance: website path runs through Airflow and can retry/restart safely; CLI and DAG results agree. Delivered as an explicit-window, manually triggered S01 DAG; periodic polling was not verified by M04. Keep its approved acceptance as historical evidence. Suggested owner commit: feat: orchestrate website pipeline with Airflow.

M05 — eBay acquisition and scheduled orchestration, in two reviewable parts:

- M05A — Fixed source/adapter/dbt/release (implemented, runtime checks passed):
  HTTP list/detail/fulfillment acquisition, two observed eBay order versions, two
  current lines, three units/USD62, correct FUL001 allocation/PARTIALLY_SHIPPED,
  paging/replay and failed-release protection. The existing
  `infra/scripts/run_m05_s01.ps1` verifies this part only.
- M05B — Automatic polling (implemented; runtime evidence in STATUS): add a bounded
  eBay Airflow DAG invoking reusable acquisition/release commands. Add an opt-in
  periodic website polling mode while preserving the existing manual S01 DAG.
  Separate runtime data-quality tests from fixed S01 golden assertions; keep both
  suites. Use checkpoint-driven windows with an explicit first-run start,
  120-second overlap, and persisted window/execution identity reused on retries.
  Add global serialization covering the whole freeze-to-publish lifecycle across
  all source DAGs/CLI runs. Per-DAG concurrency alone is insufficient.
  Acceptance: a real scheduler starts at least two consecutive local polling
  cycles without manual triggers, with fixed per-run upper bounds, justified
  checkpoints and auditable empty responses; CLI/DAG business results agree;
  restart/retry/clear cannot reset durable attempt budgets or corrupt a good
  publication. Exercise overlapping website/eBay runs without shared-build
  interleaving. Retain HTTP-only eBay and read-only website boundaries. Document
  enable/pause/bootstrap/replay commands and verify S01 regression still passes.

M05 is complete under the revised plan only when A and B pass. Existing A results
remain valid and must not be relabeled as scheduler evidence. A local five-minute
polling interval is the implemented configurable default, disabled until explicitly
enabled; it is not a vendor frequency guarantee. Suggested owner commits may
split the parts: `feat: integrate eBay simulator and fulfillment evidence`, then
`feat: schedule local polling with durable workflow recovery`.

M05 technical resolution (2026-10-28): retain existing target columns/constraints;
use a fixed standard-library HTTP simulator with a separate test-control listener,
the existing Python/Psycopg locks, source-specific eBay candidates/publication,
and a reproducible CLI acceptance runner. Freeze includes retained website inputs
for regression tests; publishing copies only the selected source. The M04 website
DAG is preserved. M05B adds scheduling without changing the approved source
semantics; its operational fields/constraints were finalized in the target
dictionary before migration 004. General stale-worker recovery, live vendor authentication and broader
mutable-page reconciliation remain later scope.

M06 — Etsy source, durable webhook handling and automatic processing: implement
receipt/list APIs, signed sender and an always-on receiver outside Airflow. Add
bounded Airflow jobs that drain durable inbox/receipt work, scan recovery windows,
and invoke dbt/test/publication using the M05B scheduling/serialization contract.
No manual command should be required for each accepted webhook after startup.
Acceptance: three deliveries, two logical messages and one observed receipt
version; both notification orders and restart after inbox persistence pass; real
scheduled work drains accepted notifications, and a scheduled recovery scan
acquires an omitted-notification case through HTTP. Attempts stay bounded and
failed processing preserves the good release. No invented paid-only snapshot.
Suggested owner commit: feat: integrate and orchestrate Etsy webhook recovery.

Implementation readiness and ordered gates:
[07_M06_READINESS.md](07_M06_READINESS.md). Finalize operational lease/work-cycle
fields before DDL, then simulator/sender, durable receiver, worker/recovery,
source-specific dbt/release and scheduled acceptance. Existing M05 controllers
require explicit Etsy extension; adding a DAG alone is insufficient.

M07 — Dashboard and report validation: implement the selected tool (Streamlit
proposed), read-only DB access, filters, operations/data-health pages and explicit
refresh controls. Finalize/add secret-free read-only live health views so failed
new runs/work/tests are visible even when the stable release is unchanged.
Acceptance: combined S01 SQL/cards match three orders/four lines/six units/USD124;
all business queries share one consistent read transaction and show publication
IDs/times per source (there is no single global release ID today). Distinguish
last successful acquisition, last good publication and latest failed attempt;
show UNKNOWN coverage and live-health read time honestly. Background publication
does not imply browser refresh; document manual or explicit UI auto-refresh.
Suggested owner commit: feat: add operations and data-health dashboard.

M07 technical resolution (2026-10-29): Streamlit 1.66.1 in a separate pinned
runtime; report-role-only read-only REPEATABLE READ per render, no result cache
or auto-refresh. Currency isolation and product-only line filtering prevent grain
errors. Restricted live-view fields precede migration 006; see
[08_M07_REPORTING.md](08_M07_REPORTING.md). Batch failure is not a parsed dbt test
result. Leave M07 unstaged after M06's authorized local commit; stop before M08.

Owner-approved M07 revision: Operations Manager-first English **Order Operations**
page with attention cards, useful reason/fulfillment charts, one-row-per-order
review worklist and observed order detail. Technical health is separate. Finalize
review precedence and safe detail fields before migration 007 in the M07 contract.
S01 operational review is eBay only; canceled website is never a fulfillment task,
Etsy cancellation UNKNOWN alone is not a task. No invented SLA or write-back.

Owner-approved scale/monitoring redo (2026-10-29): English **Multi-channel
Overview**, **Order Operations**, **Pipeline Monitoring** supersede the earlier
two-screen layout. SQL-filtered aggregates, exact order search, indexed keyset
pages (50/default, 100/max), publication-bound cursors and capped selected-order
detail replace unbounded Python filtering/all-ID selectors. Add real stage/slot
telemetry and an isolated sanitized scheduler observer; collect independently by
source before the shared freeze/build/publish barrier. Finalized fields and
acceptance precede migration 008 in [09_M07_SCALE_MONITORING.md](09_M07_SCALE_MONITORING.md).
Acceptance adds three-screen interactions, SQL/Python rule parity, cursor resets,
real measured CLI/observer evidence, coordinator/failed-release regressions and a
rollback-only 100k target-query EXPLAIN benchmark. This is NOT million-order
ingestion certification: retained-history dbt rebuild/source-snapshot publication
remain explicit limits. No source contract changes, reset or M08 generator.

M08 — S02 verification and stabilization, split by owner direction on 2026-10-30.
The earlier combined recovery/portfolio milestone is superseded by the gates below.
Read [10_S02_TEST_STRATEGY.md](10_S02_TEST_STRATEGY.md) before implementation.
These are gated deliverables; M08A local acceptance is recorded in STATUS.
Current M08B operation is the single-stack daily live path in
[16_M08_LIVE_LOCAL.md](16_M08_LIVE_LOCAL.md): start once, append manual batches.
Its finite correctness gates passed locally; retained failures and current health
remain visible in STATUS. Older RAM/temporal/replay revisions are regression
references, not additional daily setup or empty-owner-dataset requirements.
Owner authorized M08C on 2026-11-01, then explicitly paused further campaigns and
requested a checkpoint commit and M09 CV/demo packaging. Recovery inventory:
[17_M08C_RECOVERY.md](17_M08C_RECOVERY.md). Owner resumed C on2026-11-05; its18
declared runtime cases and affected local regressions now PASS (see STATUS for
exact evidence and scope). Owner authorized the first bounded M08D baseline on
2026-11-06 after reviewing both observable demos; full D certification is pending.
M09 packaging is implemented; full release certification still requires the
remaining D/reproducibility gates. Generated code alone is not runtime evidence.

- **M08A — Isolated test environment and safety harness.** Separate Compose project,
  named volumes, ports, credentials, Airflow/dbt/log/artifact bind paths and explicit
  disposable-environment verification. Cold bootstrap/rerun existing S01 checks in
  test storage, compare protected owner-environment signatures before/after, and
  reject wrong/missing targets before any fault/reset operation. Add basic offline
  CI now; finalize reproducible baseline and evidence formats. Acceptance: clean
  isolated bootstrap + rerun/persistence + guard-negative tests PASS, no owner
  dataset/final runtime drift. A temporary owner-Airflow stop/restore requires
  separate explicit authorization and verified restoration. No generator, load
  or crash campaign yet.
  Finalized harness policy: [11_M08A_ISOLATION.md](11_M08A_ISOLATION.md); local
  baseline/guard acceptance passed; owner confirmed completion, Git checkpoint pending. Exact evidence
  and small-VM test-window limits are in STATUS; no B-D acceptance is implied.
- **M08B — S02 generator and continuous correctness.** Daily workflow revised
    on2026-11-01: start DB-backed SIMs/source worker/pipelines once, then append
    manual batches without campaign selection or checkpoint reset. Acceptance
    must exercise user-facing live-up/generate and at least two batches through
    actual schedules; old isolated PASS does not certify this path. Design and
    M08 fault boundaries: [16_M08_LIVE_LOCAL.md](16_M08_LIVE_LOCAL.md).
    External seeded driver
  changes website source transactions and marketplace simulator state; Etsy emits
  signed notifications. Pipeline access remains website read-only/marketplace HTTP.
  Baseline/continuous profiles, bounded generation and independent test-only ledger;
  actual observation evidence, not all generated transitions, defines history.
  Acceptance: source/account/money/state/lineage checks PASS; all three paths publish
  current source changes through at least two real scheduled successes per path
  after one documented enable step; eventual final-state reconciliation and replay
  dedupe PASS. Add bounded integration CI; retain unchanged S01 suite separately.
  Finalized finite profiles, control/ledger/oracle boundaries and small-VM settings:
  [12_M08B_CONTINUOUS.md](12_M08B_CONTINUOUS.md). Current runtime evidence in STATUS.
  Owner requested richer S02 inputs on2026-10-31: 30 mapped products,100 synthetic
  customers and variable line/quantity counts. Offline reference/payload helpers
  are implemented, including runtime bootstrap and immutable dataset/version wiring.
  Storage, fresh CLI reconciliation and final-code scheduled/replay checks have
  separate PASS evidence in STATUS. Owner authorized C on2026-11-01; current
  health and incomplete recovery gates remain explicitly recorded in STATUS.
  See [13_S02_GENERATION.md](13_S02_GENERATION.md); previous v1 PASS is not diversity
  runtime acceptance. Do not silently replace v1 totals or S01 mappings.
  Revised source-storage implementation: prepare immutable source versions/components
  in isolated `marketplace_sim`, serve as-of source state via unchanged HTTP,
  with no runtime marketplace business-status UPDATE required. Website keeps its
  approved SQL/writer interface. Finalize physical schema/clock/source branch
  matrix before DDL; [14_S02_TEMPORAL_SOURCE.md](14_S02_TEMPORAL_SOURCE.md) documents
  the implemented opt-in backend. STATUS distinguishes storage/CLI/scheduled
  evidence and remaining gates; this is not a certified load profile.
- **M08C — Recovery, restart and pause/resume.** Execute the fault/lifecycle matrix:
  Resumed by owner2026-11-05 after M09 presentation checkpoint21075d3. Work only
  in validated disposable storage; preserve the owner's currently stopped stack.
  Runtime evidence, not runner availability, determines completion.
  Local acceptance2026-11-05: all18 runtime cases PASS, final offline88 tests
  and post-recovery read-only S01/report14 tests PASS; no owner-stack changes,
  no load/remote-CI/independent-machine certification. Review and stop before D.
  API/page failures, duplicate/out-of-order/omitted webhooks, interrupted raw/work,
  lease fencing, frozen batch/dbt/publish faults, bounded retry exhaustion, service
  restart and abrupt process loss. Pause while sources advance, resume and verify
  supported catch-up without inventing missed history. Acceptance: each required
  case has reproducible evidence and the documented automatic OR explicit operator
  recovery outcome; failed gates retain last-good publication and all audits.
  Fix discovered correctness bugs and rerun affected regression before advancing.
- **M08D — Load, burst, soak and bottleneck stabilization.** Opt-in bounded tests.
  Owner reviewed both live demos2026-11-06 and authorized the next step. Begin
  bounded warm-history correctness/resource baseline per19_M08D_MEASUREMENT.md;
  preserve one local stack and old profiles. Exact first-publication latency,
  sustained/burst/soak and final D certification remain explicit separate gates.
  Next authorized slice2026-11-07: finite Website24/6min then mixed72/6min,
  fixed900s observed-drain budget and at least2 scheduled successes per required
  active-source DAG; report minute-plan buckets and actual final backlog/age.
  No source/schema/business redesign, no burst/soak certification from these steps.
    Owner then authorized official orphan recovery and higher finite steps:
    after low gates PASS, mixed300/6min then900/10min. Predeclared count ceilings
    grow only for those profiles; resource/delay/drain budgets stay fixed. Stop
    escalation at any failure; exact actual outcomes remain in STATUS.
    After observed executor queue/cycle contention, one live-only4-slot experiment
    is predeclared (base2/per-DAG1/global publication lock unchanged). If the short
    mixed gate still fails, retain it and calibrate exposure ONCE:144/12min at
    the same0.2 offered/s, then600/12min at the300/6min offered rate, then900/10min.
    Identical latency/resource/drain/cycle gates; no indefinite window relaxation
    or retroactive green verdict. These remain finite, not full D certification.
    Actual qualification144 FAILED the scheduled-cycle gate; independent data
    correctness passed.600/900 were not admitted. Next prerequisite is bounded
    reconciliation of Etsy mutable/cached recovery pages, retaining raw evidence,
    durable budgets and approved S01 resume behavior. No further exposure
    calibration; rerun the same qualification only after a verified fix.
    Reconciliation fix now verified by rollback HTTP/SQL probes and a live
    INVALID->VALIDATED successor scan. The unchanged144 rerun still FAILS cadence
    (one qualifying recovery start), while independent data correctness passes.
    Next prerequisite is measured workflow/build cadence optimization; keep the
    same gates and source/atomic-release contracts. Subsequent measured change:
    materialize existing Website staging/intermediate SELECTs as tables, with
    full multiset parity and the complete 54-node dbt release gate retained.
    Unchanged 144 and 600 finite envelopes now PASS; 900 FAILS scheduled cadence
    although independent final-data reconciliation passes. Stop escalation.
    Narrow follow-up: replace the 100-claim drain cap with an invocation work-set
    bound; no DDL or fixed-membership-across-restart claim. Verify >100 work and
    unchanged failure/resume/checkpoint behavior. SAME900 rerun still FAILS
    cadence2/1/1/1, although inbox390/recovery300 work complete per collection
    without the100 cutoff and final-data reconciliation passes. Drain843.241s
    stays within900s. Next: paging and broader workflow profiling;
    Bounded page50 refinement now verified: base/S01default1, immutable cycle
    policy and legacy1 restored on retry.125selected tests plus17HTTP/SQL checks
    PASS. Same900 rerun still FAILS cadence1/1/1/1; final900 data correctness and
    drain751.877s PASS separately. Next profile detail/operational SQL and build/
    queue (including idle-cycle work); do not equate fewer list calls with full
    M08D acceptance. No worker/model-selection changes in this experiment;
    do not inflate budgets or source exposure. This is not completed
    D acceptance. Exact evidence is in STATUS.
    Next authorized slice2026-11-08: profile/rewrite Website staging repeated
    child-array expansion only, with complete multiset/fingerprint parity and
    session-temp SQL plans per19_M08D_MEASUREMENT.md. No incremental storage,
    model selection, parallel release or acceptance-gate changes in this slice.
    Deployment exposed a missing-owner annotation race: resolve it with atomic
    owner metadata in the existing freeze transaction and an exact-barrier
    guard reread, not automatic orphan abort or relaxed gates. After45selected
    regressions and full54-node release, unchanged900 still FAILS cadence1/1/1/1.
    Independent900data reconciliation and751.029s observed drain PASS separately;
    no escalation. Review measured Etsy staging and executor/coordinator waits
    next; complete D acceptance remains pending (exact evidence in STATUS).
    Follow-up2026-11-12: reuse Etsy canonical payload via a statement-local
    materialized CTE, preserving output/filter/error/hash contracts. First prove
    disposable SQL multiset/hash parity and bounded profiles; full dbt/release
    and unchanged900 cadence qualification remain separate gates. No worker,
    source-window, DDL, incremental-cache or budget changes in this slice.
    Deployed2026-11-12 with full54-node release PASS. Unchanged900 still FAILS:
    cadence1/1/1/0 and139eBay orders pending at drain deadline. Later independent
    reconciliation PASS900 does not override late catch-up. Stop escalation;
    design/profile retained-raw rebuild cost and executor/coordinator occupancy
    before further changes (exact evidence and limitations in STATUS).
    Owner approved priorities1/2: versioned Etsy canonical cache joined to the
    unchanged frozen manifest, and worker-free reschedule coordination with
    durable source ownership. Final dictionary before migrations010/011 and
    design/recovery gates:20_M08D_REUSE_COORDINATION.md. No model/test reduction,
    parallel shared build or relaxed load limits; base/S01 remain regression paths.
    Next approved optimization slice: deploy the tested FIFO refinement and use
    bounded execution plans for eBay snapshot evidence. Separate the three OR
    evidence paths into equijoins and expand each relevant list page once; retain
    final DISTINCT, source/account/version joins, frozen manifest and all output
    columns/types. Prove complete multiset/error parity before deployment; no
    stable DDL, parallel publication or changed workload/gates. Full release and
    unchanged900 qualification remain separate runtime checks.
    Owner-approved revision2026-11-13: target healthy warm collect-to-visible
    publication<=10s. Replace per-cycle full rebuild with affected-order processing,
    source-private compiled dbt plans, applicable invariant gates and atomic delta
    publication; full dbt/S01 regression remains separate. First dictionary before
    migration012 and design/clock/workload limits:21_M08D_DELTA_RUNTIME.md.
    Do not claim this target from one SQL timing or enable an unverified fast path.
    Private coordinator integration now retains the existing durable stage
    attempts, source ownership, actual Airflow IDs and atomic publication audit.
    Real SQL/HTTP 1/10/100-order probes and full dbt parity are separate from
    main retained-data/scheduler rollout and the unchanged900 acceptance.
    Subsequent isolated four-DAG scheduler/source-contention gate PASS (STATUS):
    actual Website/eBay/Etsy inbox/recovery scheduling and worker-free reschedule.
    Standalone shutdown/API-readiness race diagnosed, not yet hardened on main;
    mapping bootstrap, retained-owner rollout and unchanged900 remain separate.
    Strict API-ready restart plus mapping/full-dbt gate now PASS privately
    (2026-11-13): three Website cycles exactly try2 with one intentional fault,
    mapping rebootstrap preserves source identity/raw audit and all8outputs match
    full54-node dbt. Retained rollout now PASS: additive012, all3source cold
    bootstrap parity, Airflow health/unchanged pause flags, two actual scheduled
    successes per live DAG. Unchanged900 finite envelope now PASS: independent
    900order/3801line reconciliation, cadence10/5/9/7(Web/eBay/inbox/recovery),
    observed drain96.438s within900s. MAX<=10s NOT achieved; actual collection
    and mutable eBay pagination retries dominate. Review list-crawl/detail work
    separation next. No further burst/soak/escalation or fullD PASS is implied.
    Owner-selected acquisition enhancement2026-11-14 (DESIGN ONLY):
    [22_M08D_EBAY_ACQUISITION.md](22_M08D_EBAY_ACQUISITION.md), revised after
    owner review: up to TWO DETAIL/ENRICHMENT workers per source/account where
    needed, NOT two page workers. Keep sequential discovery; reuse complete eBay
    page Orders and Etsy recovery receipts rather than refetching every entity.
    Optional eBay grouped lookup remains at most50 IDs, not mandatory enrichment.
    Retain required cancellation/shipping/webhook/fallback detail reads. Website
    keeps its existing set-based consistent snapshot, not forced concurrency.
    Preserve actual raw audit, page-element/cache identity, work leases, shared
    retry/rate budgets, mutable-window reconciliation and one completion barrier.
    Etsy SIM scope clarification: leave it unchanged; receipt-list payload support
    already exists. Remove redundant collect GETs first, with necessary dbt/cache/
    eligibility/evidence input adaptations. Retain webhook/fallback receipt GETs;
    only report a demonstrated SIM blocker before proposing extra SIM changes.
    A later detail-pool limit from SIM serialization is not authority to rewrite it.
    Update dbt/cache/evidence inputs,
    version compiled plans and requalify parity/bootstrap before live activation
    and unchanged900. Transform/publish remain multi-order set-based SQL with
    atomic publication. Base/S01 is unchanged; no runtime enhancement is claimed.
    Build/test review2026-11-14: [23_M08D_BUILD_TIMING.md](23_M08D_BUILD_TIMING.md).
    Historical900 node evidence shows Etsy mean3.653s unitemized and an empty
    6.607s cycle; Website product activity max5.061s. Next profiling priorities:
    subphase timers (validation/hooks/drops/CTAS/ANALYZE/commit), effective-current
    product aggregation execution plans, then a correctly audited no-business-change
    tick. Do not drop quality gates, blame network without evidence or silently
    equate elapsed stage time with pure SQL CPU. Publish tuning deferred by owner.
    Owner-requested SQL conventions2026-11-14: explicit needed projections,
    COUNT(1), INNER JOIN spelling, grouped deduplication and PostgreSQL SELECT1
    existence checks. Preserve required MATERIALIZED JSON reuse and correct
    affected/retained predicates; no blanket CTE removal or speculative indexes.
    Review/rules: transformations/SQL_STYLE.md. These SQL edits require a new
    verified compiled release/bootstrap; existing main plans must not be activated
    against a changed source hash. Performance conclusions still require timing.
    Owner report/time correction2026-11-14: per-report clocks, not a global
    date switch. Retain source-created order/product cohort meaning; monitoring
    counts actual pipeline attempts, not received/new orders. Bound normal daily
    aggregation and publication by explicit old/new touched-day scope, preserving
    untouched days and handling emptied buckets/late data. Dictionary in05 before
    helper models and limited SELECT grant013. Add staging CTAS/ANALYZE and hook
    timers; qualify multiday/currency changes, empty/replay/late ticks and full-dbt
    parity. No blind parallel transaction rewrite. Review:24_ACTIVITY_TIME_REVIEW.md;
    actual results STATUS.
  Owner sequencing revision2026-11-06: finish C repeatability prerequisite, then
  observable normal campaign and one eBay outage/recovery demo. Implement/review
  these before load measurements or any performance verdict; the latter are
  explicitly deferred until owner checks the demos. New commands/profile docs:
  tools/s02_data/CAMPAIGN.md. Final D acceptance is NOT implied by READY_FOR_REVIEW.
  Owner requested SIM-first implementation/review before the campaign controller.
  Implemented subset: additive delivery provenance/schedule migration, opt-in
  generated live delivery plans, durable sender retry/ACK progress and inspection
  demo. Legacy profiles unchanged; new schedule v1 intentionally live-only,
  legacy replay refuses it. SIM checks do not satisfy D load/campaign acceptance.
  Owner-approved observable campaign direction2026-11-05: reuse the M08B data
  config with an optional campaign section and a dedicated campaign entrypoint;
  generate-only commands never inject faults. Support a stable explicitly opted-in
  synthetic local stack, seeded bounded fault timing, visible UI/DB access and
  retained inspection after recovery. Prepare data before measurement; separate
  correctness, recovery and performance verdicts. C regressions remain separate.
  Pre-implementation review: precompute delayed/reordered/duplicate/omitted
  notification delivery plans independently of immutable source versions. Receipt
  HTTP reads remain current-as-visible, not historical notification replay.
  Reuse runtime hooks/controller for transport/service failures; do not model
  HTTP500 or process loss merely by adding order rows. Preserve existing quota
  semantics and generate-only compatibility; finalize attempt fields/constraints
  before any supporting DDL. Historical pre-implementation proposal below is now
  superseded by the implemented SIM slice and bounded review campaign above.
  Config paths are arbitrary profiles under tools/s02_data/config/, not a
  hardcoded local_now.json. Review proposal: retain logical s02.deliveries and
  add a minimal child send schedule keyed by campaign/message/attempt, distinct
  from source-version visible_at. Current latest-visible selection may coalesce
  versions; changing visibility alone does not prove repeated acquisitions or
  notification reorder. Negative data stays opt-in; prioritize UNMAPPED coverage
  separately from an unknown-status gate-blocking profile. No DDL approved yet.
  Concrete schema proposal in the temporary review: leave source tables unchanged,
  add source/account/source_sequence provenance to deliveries (nullable sequence
  only for legacy), plus one delivery_schedule child keyed by campaign/message/
  planned attempt. Store due time and minimal retry/ACK progress without payload
  copies. Parent-version FK, seal guards and sender-only progress writes are
  required; no migration/schema execution in the design-review task.
  Prerequisite repaired2026-11-06: C scheduled catch-up passed two clean sequential
  reruns after scoped marker/CLI-pause/drain fixes; exact evidence is in STATUS.
  with declared source mix, initial history/line cardinality, offered rate, bounded
  duration, resource ceilings and stop conditions. Measure actual generation vs
  logical processing, publication latency, backlog/drain, errors/retries and laptop
  resources. First measure baseline, then make evidence-driven bounded fixes and
  rerun the same workload plus regressions. Acceptance: a declared normal-load
  envelope meets predeclared correctness/latency/drain limits; burst/soak and any
  optional stress ceiling have honest results, not fabricated capacity claims.
  Saturation is not a correctness failure by itself; silent loss/corruption is.

Review and stop after EACH part. Physical changes need finalized fields/constraints
before DDL. Major incremental/release redesign requires its own scoped acceptance,
not a silent widening of M08D. Leave changes unstaged unless currently authorized.

M09 — Portfolio and reproducibility packaging. Owner priority revision (2026-11-01):
prepare evidence-backed CV text, architecture/review map and separate demo paths
now; label C/D incomplete/deferred and known availability/performance limits.
Do not run more fault/load campaigns during the pause. Documentation packaging
does not certify the runtime as production-ready. The original full release
acceptance below remains pending until M08D acceptance and outstanding checks.

Packaging deliverable: [18_PORTFOLIO.md](18_PORTFOLIO.md), linked from README and
the documentation map. Packaging checks: local links and documented CLI help
resolve, versioned demo config validates, evidence/claims match STATUS, no private
runtime/credentials included. These document checks are separate from the full
runtime acceptance below and do not reclassify failed/unrun cases as PASS.

Full release scope:
Publish tested fresh-setup/restart/recovery instructions and two distinct demos:
unchanged deterministic S01 and opt-in continuous S02. Expand CI around the already
working smoke/integration suites; document measured hardware/workload/limits,
known unsupported cases and a sanitized evidence index. Acceptance: another setup
can follow README from fresh isolated storage without the owner's retained raw;
demo, reproducibility and selected CI checks PASS. Do not defer operational runbooks
or minimal regression CI needed by M08A-C until M09. No live-vendor certification
or general million-order claim. Suggested owner commit: docs: package verified
multi-channel demos and recovery evidence.

Release dependencies: M00 → M01 → M02 → M03 → M04 → M05 → M06 → M07 → M08A → M08B → M08C → M08D → M09 certification. Owner-approved exception: M09 documentation/CV packaging may proceed from the current partial checkpoint; it does not satisfy deferred runtime gates. Validate report queries in M03 and extend them with each source. M07 adds the complete presentation, not the first discussion of report requirements. Scope and status can evolve in Git with explicit evidence.

### Completion rules for automatic operation

Use [06_AUTOMATION.md](06_AUTOMATION.md) for clock modes, polling windows,
cross-source release serialization, attempt budgets and scheduler evidence.
M05B delivers automatic local website/eBay polling; M06 delivers scheduled Etsy
work/recovery around its always-on receiver; M08A proves isolated clean setup,
M08B adds unattended changing-source correctness, M08C verifies recovery/lifecycle,
M08D measures load and M09 packages reproducibility. A frozen fixture can return valid empty windows forever;
a running scheduler alone is not evidence of new source data or complete history.

## D2. Repository instructions and continuity

Use small Markdown files by responsibility: AGENTS.md for coding rules; docs/01_BUSINESS.md for purpose/metrics; docs/02_SOURCE_CONTRACTS.md plus exported source-field/rule files for S01 interfaces; docs/03_ARCHITECTURE.md for proposed design; docs/04_PLAN.md for milestones; docs/STATUS.md for actual progress; docs/CODEX_VSCODE.md for setup and prompts. Executable migrations, dbt contracts/tests and fixtures become the precise implementation reference.

Google Doc and Sheet remain the collaborative review references. A dated Git snapshot makes the coding contract available locally without a Google session. No automatic two-way synchronization is implied. When an accepted decision changes, update affected Markdown/contracts and the review documents together, record the source revision and commit. Do not allow two independent rule sets to drift.

At the start of a Codex task, read AGENTS.md, STATUS and the selected milestone, then only its relevant contracts. Work on that milestone, run the required checks, inspect the diff, and update STATUS with actual commands/results and unresolved work. A failed required check keeps the milestone incomplete. Leave changes unstaged for owner review unless the owner explicitly requests a Git action in the current task.

Use a milestone branch if desired. After review, the owner stages the intended files, creates the milestone commit, and pushes when ready. Codex may suggest a commit message and review commands, but must not stage, commit, amend, squash, rebase, or push without an explicit current-task request. When explicitly asked to commit, obtain the SHA from Git instead of embedding a commit's own hash in its files.

## D3. VS Code and Codex handoff

Install the official OpenAI Codex extension in VS Code, open the repository folder, open the Codex sidebar and sign in through the supported flow. Do not assume this chat's history or Google Docs contents are automatically available in the IDE; provide local Markdown and fixtures. Official reference: https://learn.chatgpt.com/docs/codex/ide .

Native Windows is supported. For this Linux/container-oriented DE stack, WSL2 plus VS Code's WSL workflow is a project recommendation when available, not a Codex requirement. Check existing Git, Python, Docker/Compose and WSL installations before adding dependencies. Do not reinstall working tools without need. See https://learn.chatgpt.com/docs/windows/wsl and https://learn.chatgpt.com/docs/windows/windows-sandbox .

AGENTS.md provides repository instructions; the plan and status files are this project's conventions, not magic filenames that Codex necessarily reads automatically. The root instructions explicitly direct Codex to them. Do not ask one prompt to generate the whole project. Prompt for one named milestone and require acceptance evidence.

Example task: Read AGENTS.md and docs/STATUS.md. Implement M01 from docs/04_PLAN.md only. Use the relevant approved source contracts and label new technical choices. Run its acceptance checks, update STATUS honestly, inspect the diff, and leave changes unstaged for my review. Report what changed, commands/results, suggested commit message, and remaining risks; stop before M02. Do not commit or push.

## D4. Decision provenance and actual status

Approved: S01, source contract v0.1, website schema/rules, eBay/Etsy selected
schemas/rules, F01–F05 solution direction and the practical DE scope. Required:
dbt and Airflow. M01-M07 routine implementation choices and acceptance are recorded
in STATUS. Owner requested the M08A-D/M09 roadmap split on 2026-10-30; this approves
the planning direction, not unimplemented runtime behavior or unspecified physical
schemas. New material semantic/architecture choices still require review, and
each planned part must pass its own acceptance before the next begins.

Existing progress (2026-10-30): M01-M07 are committed locally; M07 is
`7f459aba8ac2b545ac14b82259a6579bcd25f91b`. M05A eBay HTTP
acquisition/dbt/allocation/publication and M05B scheduling/restart/budget checks
passed and the owner approved the result. M06 owner sign-off, final checks and
commit are recorded in STATUS. M07 local report/SQL/AppTest acceptance passed and
the owner approved its local commit. M08A is locally implemented/verified and
owner confirmed completion; M08B passed local case-based acceptance and awaits review.
M08C declared local recovery matrix passed2026-11-05; owner review pending.
M08D bounded baseline is authorized/in progress; sustained/burst/soak and final
certification remain pending.
M09 documentation packaging is authorized; full release certification is pending.
The fixed fixture pack
passes 10 offline checks and 10 utility unit tests. M05 additionally passes 7 HTTP
tests, SQL fingerprint/evidence tests, and shared M03 command regression. M06 adds
Etsy security/lease/fingerprint/SQL tests and real scheduled/fault checks. The
dashboard adds report/live-health/role/filter/UI checks. Combined changing-source/
cold recovery/load stabilization remain M08A-D work; portfolio release is M09. Exact commands,
run/batch IDs, intermediate failures and limits are recorded in STATUS.md.

Accepted limits: no fabricated unobserved snapshots; no general Etsy shipment-to-transaction allocation; no confirmed refunds/delivery/revenue recognition without evidence; no live vendor certification or scale claim. Keep optional AI investigation outside the first delivery.



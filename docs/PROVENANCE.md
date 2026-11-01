# Specification provenance and synchronization

## Daily local live source revision:2026-11-01

Owner requested start-once sources/pipelines, then manual append generation,
without per-batch campaign selection. Contract16_M08_LIVE_LOCAL.md precedes
additive003_live_batches DDL. Existing S01 bytes/contracts remain regression
inputs; runtime S01 data is not an activation blocker. Mapping local-live-v1 is
an explicit composite of s01-v1/s02-catalog-v1, not a source identity change.
M08A isolation, M08C boundary faults and M08D measured-load gates remain distinct.
Actual current-code runtime results, failures and unrun gates are only in STATUS;
prior isolated PASS is not automatically reused for this source-worker path.

## Local temporal implementation:2026-10-31

Owner approved coding document14. Physical fields/constraints and per-source
branch boundaries preceded opt-in PG migration/readers, prepare/seal/as-of HTTP,
catalog-aware oracle and isolated temporal runners. Existing S01/source/fingerprint
semantics and v1 RAM mode preserved. DAGs accept explicit polling mapping version
with default s01-v1 unchanged. New offline/CI gates and runtime storage/CLI evidence
are recorded in STATUS; do not infer scheduled/fault/load acceptance. No owner DB
schema changes, Git writes, remote Actions or Google synchronization performed.

## Local S02 temporal-source proposal:2026-10-31

Owner requested pre-generated time-indexed source changes and component joins.
[Document14](14_S02_TEMPORAL_SOURCE.md) proposes immutable PostgreSQL source
versions selected as of time behind unchanged marketplace HTTP, instead of a
runtime current-state materializer. Documentation only; physical fields, schema,
clock and lifecycle branch implementation/acceptance remain pending. S01/CSV/
fingerprint/business contracts unchanged. Google exports were not synchronized.

Snapshot date: 2026-10-24 (Asia/Bangkok).

- Google Doc: https://docs.google.com/document/d/13HWKCL8ZnG7ILXDkbBxpQvIyLuVcHpqPGnoPXsVCaJE
- Read document revision: `AHj4eMSGLvcmavZW9D61MnxqHyQCgfMkUlNY7PmLU7Qusq8cF7aqcr2qTRo9uUP0Uz0GZxZJ1myoFRT_TskDSLXowoMh75KJrQWdqjys_N8`.
- Workbook: https://docs.google.com/spreadsheets/d/1KSrluLRO0NMzu7_kLbUNsNXz9O_xgMvzQ9y3ReLTf54/edit
- Bounded source exports: tabs 13–18, headers at row 3 and all defined schema/rule rows beneath them. No later workbook revision is implied.

## Authority

Approved business/source semantics are labeled in the specification. dbt and Airflow are user requirements. Architecture/publication, report/tool details and M00–M08 are proposed for review, not silently approved by export. The original six source field/rule tables are preserved as CSV under `docs/contracts/`; complete synthetic payloads and golden outputs remain in `fixtures/s01/`.

The Google Doc is organized as A Business, B Source contracts/S01, C Architecture/pipeline and D Delivery. Its dated local counterparts are `01_BUSINESS.md` through `04_PLAN.md`. The three source diagrams are copied unchanged into `docs/assets/`. This handoff supersedes the earlier Retail & Finance/UCI context for this project; that unrelated old context is intentionally omitted.

## Change workflow

Current local delivery roadmap extends through M09; see the 2026-10-30 revision
below. Earlier M00-M08 references describe the dated export/planning baseline.

1. Review a material change and record whether it is approved or a draft.
2. Update the relevant Markdown and executable contract/tests in the same change.
3. Synchronize accepted design changes to the Google review references, or explicitly record a pending synchronization task if access is unavailable.
4. Update STATUS and leave the verified diff unstaged for owner review. The owner stages, commits, and pushes when ready. Keep source revision/date when refreshing an export.

There is no automatic two-way synchronization. Do not blindly overwrite newer local implementation decisions with an older Google export or treat a historical status cell as current runtime evidence. If the sources disagree, identify the conflict instead of guessing.

## Local stabilization planning revision: 2026-10-30

M08B follow-up: owner reports A complete and authorized B only. Finalized source/
control/ledger/oracle/profile constraints in `12_M08B_CONTINUOUS.md`; no warehouse
DDL/business/fingerprint/S01 change. Added opt-in stores/source writer, host-only
driver, bounded profiles and integration CI. Local data baseline/continuous and
supplemental final-code in-flight drain/narrow-mount regression passed; initial
runner inbox-drain omission was recorded/fixed with regression, not hidden. Small-
VM owner-Airflow stop/restore explicitly authorized again and restored healthy,
with original data/system identity/pause states unchanged. No C/D/M09 or remote
Actions/Google sync implied; STATUS is the current evidence record.

Subsequent M08A implementation: finalized host marker/model/resource/evidence
definitions in `11_M08A_ISOLATION.md` before coding. Added host-only guarded test
harness, finite existing-command S01 baseline, offline safety tests and SHA-pinned
offline CI. No warehouse DDL, source/S01/fingerprint or production pipeline change.
Initial local runs exposed a bootstrap health race and Airflow/Engine failure.
After test-only health/resource/guard refinements and an explicitly authorized
owner-Airflow stop/restore window, fresh M08A acceptance passed61 steps; owner
Airflow restored healthy, protected data/pause states unchanged. A logging-only
preservation fix was checked separately after the full run; exact commands/hashes/
limits are in STATUS. Owner review, B-D/M09 and external Google sync remain pending;
no remote CI or load/recovery campaign is implied.

Owner requested updating the proposal into repository docs: split the combined
M08 into A isolated environment/safety, B S02 generation/correctness, C recovery/
lifecycle, D measured load/stability; move portfolio packaging to M09. Add basic
CI in A and bounded integration CI in B, not only at final packaging. Contract
`10_S02_TEST_STRATEGY.md` defines profile/oracle boundaries, isolation, fault matrix,
measurement limits, evidence and review gates. This is documentation only: no
generator, fault/load runner, physical schema, runtime or resource changes.
Approved source v0.1/CSV/S01/fixture bytes and canonical semantics unchanged.
Local plan/automation/architecture/source-overview/map/README/STATUS synchronized;
Google review surfaces and dated exports NOT updated. Their synchronization
remains pending; no external revision or new runtime PASS is implied.

## Local planning revision: 2026-10-28

The owner requested a plan/documentation review to close the missing scheduled
eBay workflow. Local Markdown now distinguishes completed M05A CLI/source work
from pending M05B automatic website/eBay polling, assigns scheduled Etsy processing
to M06, live failure/report publication labels to M07, and changing-source/cold
setup evidence to M08. `06_AUTOMATION.md` defines the planned clock/window/retry/
serialization and acceptance requirements. This is not implementation evidence.

Approved S01/business/source meanings and the original CSV/fixture exports are
unchanged. Google Doc/Sheet were not modified or re-exported in this review;
synchronizing the local planning/reporting delta to those review surfaces remains
pending. Preserve the original export revision above until an actual refresh.

## Local implementation delta: M05B, 2026-10-28

The owner subsequently authorized code changes. The target dictionary now records
the finalized immutable polling-cycle fields and batch validation mode, implemented
by migration 004. Local plan/architecture/guides are synchronized with the actual
website/eBay scheduled, restart and budget evidence in STATUS. S01 exports and
fixture bytes remain unchanged. Google review surfaces were not modified;
synchronizing these operational/schema additions remains pending.

## M06 readiness review: 2026-10-28

After M05 owner sign-off/local commit, local planning adds `07_M06_READINESS.md`
with ordered implementation gates and acceptance details derived from the
approved Etsy CSVs, fixtures and actual M05 extension points. No approved source
fields, fixture bytes, business states, Google review surfaces or dated exports
were changed. Lease/work-cycle fields must be finalized before M06 DDL; the
checklist is not a physical-schema or runtime delivery. Google synchronization
of these local operational proposals remains pending.

## M06 implementation delta: 2026-10-28

The owner authorized M06 implementation. Operational schema additions were
finalized before migration 005. The previously proposed FastAPI choice resolved
to pinned standard-library HTTP/Psycopg for the bounded local receiver. Added
explicit lease/collection provenance, source-specific Etsy release, scheduled
inbox/recovery, retained-data-safe acceptance scopes and clock-safe lifecycle
audit. Business SQL stays in dbt, callbacks outside DAGs; approved S01/CSV/fixture
bytes and business/source meanings are unchanged. Actual runtime evidence and
intermediate failures are in STATUS. Google Doc/Sheet/exports were not updated;
synchronization of these local implementation/operating decisions remains pending.

## M07 reporting / scale revision: 2026-10-29

Owner approved the English operations-first dashboard and subsequent multi-channel/
bounded-query/monitoring redo. Finalized local contracts 08/09 precede migrations
006–008. Three screens, read-only projections, real-clock stage/slot telemetry and
isolated scheduler sampling do not alter approved CSV/source/S01/fixture bytes,
canonical states or fingerprint behavior. M05/M06 test adjustments fix a NULL
no-op mutation probe and supply explicit validation mode to a mocked stage.
Independent collection retains guarded freeze/build/test/publication; full-history
rebuild and snapshot publication remain declared scale limits. Benchmark rows
are rolled back, not a new source truth dataset. STATUS records exact evidence,
failures and not-run scopes. Google exports/documents were not synchronized.


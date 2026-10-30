# Specification provenance and synchronization

Snapshot date: 2026-10-24 (Asia/Bangkok).

- Google Doc: https://docs.google.com/document/d/13HWKCL8ZnG7ILXDkbBxpQvIyLuVcHpqPGnoPXsVCaJE
- Read document revision: `AHj4eMSGLvcmavZW9D61MnxqHyQCgfMkUlNY7PmLU7Qusq8cF7aqcr2qTRo9uUP0Uz0GZxZJ1myoFRT_TskDSLXowoMh75KJrQWdqjys_N8`.
- Workbook: https://docs.google.com/spreadsheets/d/1KSrluLRO0NMzu7_kLbUNsNXz9O_xgMvzQ9y3ReLTf54/edit
- Bounded source exports: tabs 13–18, headers at row 3 and all defined schema/rule rows beneath them. No later workbook revision is implied.

## Authority

Approved business/source semantics are labeled in the specification. dbt and Airflow are user requirements. Architecture/publication, report/tool details and M00–M08 are proposed for review, not silently approved by export. The original six source field/rule tables are preserved as CSV under `docs/contracts/`; complete synthetic payloads and golden outputs remain in `fixtures/s01/`.

The Google Doc is organized as A Business, B Source contracts/S01, C Architecture/pipeline and D Delivery. Its dated local counterparts are `01_BUSINESS.md` through `04_PLAN.md`. The three source diagrams are copied unchanged into `docs/assets/`. This handoff supersedes the earlier Retail & Finance/UCI context for this project; that unrelated old context is intentionally omitted.

## Change workflow

1. Review a material change and record whether it is approved or a draft.
2. Update the relevant Markdown and executable contract/tests in the same change.
3. Synchronize accepted design changes to the Google review references, or explicitly record a pending synchronization task if access is unavailable.
4. Update STATUS and leave the verified diff unstaged for owner review. The owner stages, commits, and pushes when ready. Keep source revision/date when refreshing an export.

There is no automatic two-way synchronization. Do not blindly overwrite newer local implementation decisions with an older Google export or treat a historical status cell as current runtime evidence. If the sources disagree, identify the conflict instead of guessing.

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


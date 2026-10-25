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


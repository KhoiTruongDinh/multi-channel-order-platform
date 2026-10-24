# D. Delivery plan and AI coding workflow — DRAFT

## D1. Milestones and completion evidence

Work one milestone at a time. Each milestone has a bounded output, acceptance checks, an evidence record and a Git checkpoint. A milestone may contain several small commits; make a clear completion commit when its checks pass. Stop at that boundary for the owner's review before beginning another milestone. Do not claim that generated code has run.

M00 — Repository handoff: version business/source specifications, the proposed architecture/report contract, AGENTS.md, the milestone plan, STATUS and existing fixed fixtures. Acceptance: reference links resolve locally and fixture checks/tests pass. Git initialization and a remote push are still pending. Suggested commit: docs: establish S01 project contract and milestones.

M01 — Foundation and schema: inspect local tools; choose/pin compatible dependencies; add minimal PostgreSQL Compose, roles, migrations and the target field dictionary. Finalize required types/nullability, PK/FK/unique keys, evidence links and report-read views before dependent models. Acceptance: clean DB bootstrap, migration rerun policy, role boundaries and restart persistence; review the schema diff. Commit: feat: bootstrap storage and schema contracts.

M02 — Website acquisition: implement fixed source-state playback and consistent read-only extraction into raw plus run/checkpoint audit. Acceptance: all three scheduled observations saved; interruption cannot falsely complete a window; acquisition replay is auditable and does not bypass source boundaries. Commit: feat: ingest website S01 with durable checkpoints.

M03 — Website dbt and release: add source staging, mapping, observed history/current, marts, tests and atomic publication. Acceptance: website one current order/line, three observed order versions, original two units/USD40; replay does not inflate versions; failed tests leave previous publication intact. Verify report SQL before building elaborate visuals. Commit: feat: transform and publish website orders with dbt.

M04 — Airflow website workflow: wrap the tested CLI/dbt/release commands in a bounded DAG with run IDs, attempt budgets and failure handling. Acceptance: website path runs through Airflow and can retry/restart safely; CLI and DAG results agree. Commit: feat: orchestrate website pipeline with Airflow.

M05 — eBay source and adapter: implement fixed list/detail/fulfillment interfaces and acquire through HTTP; extend dbt models. Acceptance: two eBay observed order versions, two current lines, correct FUL001 allocation and PARTIALLY_SHIPPED state; paging/replay assertions pass. Commit: feat: integrate eBay simulator and fulfillment evidence.

M06 — Etsy source and adapter: implement receipt/list APIs, signed sender, durable always-on receiver and receipt/recovery work. Acceptance: three deliveries, two logical messages and one observed Etsy receipt version; test both notification orders and restart after inbox persistence. No invented paid-only receipt snapshot. Commit: feat: integrate Etsy webhook acquisition and recovery.

M07 — Dashboard and report validation: implement the selected tool (Streamlit proposed), read-only DB access, filters, operations/data-health pages and manual refresh/batch labels. Acceptance: combined S01 SQL and cards match three orders/four lines/six units/USD124; show current states and known limitations; failed new runs are visible without corrupting business figures. Commit: feat: add operations and data-health dashboard.

M08 — Recovery and portfolio release: exercise old/repeated versions, 429/500/timeouts, interrupted work, missing mapping and failed publication; add smoke CI and a reproducible demo. Acceptance: combined golden-output checks plus recovery tests pass, another setup follows README, known limits are recorded. Record measured laptop resource use; do not claim a large-scale benchmark from three orders. Commit: test: verify recovery and package reproducible demo.

Dependencies: M00 → M01 → M02 → M03 → M04 → M05 → M06 → M07 → M08. Validate report queries in M03 and extend them with each source. M07 adds the complete presentation, not the first discussion of report requirements. Scope and status can evolve in Git with explicit evidence.

## D2. Repository instructions and continuity

Use small Markdown files by responsibility: AGENTS.md for coding rules; docs/01_BUSINESS.md for purpose/metrics; docs/02_SOURCE_CONTRACTS.md plus exported source-field/rule files for S01 interfaces; docs/03_ARCHITECTURE.md for proposed design; docs/04_PLAN.md for milestones; docs/STATUS.md for actual progress; docs/CODEX_VSCODE.md for setup and prompts. Executable migrations, dbt contracts/tests and fixtures become the precise implementation reference.

Google Doc and Sheet remain the collaborative review references. A dated Git snapshot makes the coding contract available locally without a Google session. No automatic two-way synchronization is implied. When an accepted decision changes, update affected Markdown/contracts and the review documents together, record the source revision and commit. Do not allow two independent rule sets to drift.

At the start of a Codex task, read AGENTS.md, STATUS and the selected milestone, then only its relevant contracts. Work on that milestone, run the required checks, inspect the diff, update STATUS with actual commands/results and unresolved work, and commit only task-owned files when Git identity/branch are configured. A failed required check keeps the milestone incomplete. Do not stage unrelated user changes.

Use a milestone branch if desired. The standing workflow allows local milestone commits after checks pass. Record the completion commit in the chat summary; obtain its SHA from git log instead of trying to embed a commit's own hash in its files. A remote push requires a configured remote and explicit instruction to push; no repository has been created or pushed by this documentation task.

## D3. VS Code and Codex handoff

Install the official OpenAI Codex extension in VS Code, open the repository folder, open the Codex sidebar and sign in through the supported flow. Do not assume this chat's history or Google Docs contents are automatically available in the IDE; provide local Markdown and fixtures. Official reference: https://learn.chatgpt.com/docs/codex/ide .

Native Windows is supported. For this Linux/container-oriented DE stack, WSL2 plus VS Code's WSL workflow is a project recommendation when available, not a Codex requirement. Check existing Git, Python, Docker/Compose and WSL installations before adding dependencies. Do not reinstall working tools without need. See https://learn.chatgpt.com/docs/windows/wsl and https://learn.chatgpt.com/docs/windows/windows-sandbox .

AGENTS.md provides repository instructions; the plan and status files are this project's conventions, not magic filenames that Codex necessarily reads automatically. The root instructions explicitly direct Codex to them. Do not ask one prompt to generate the whole project. Prompt for one named milestone and require acceptance evidence.

Example task: Read AGENTS.md and docs/STATUS.md. Implement M01 from docs/04_PLAN.md only. Use the relevant approved source contracts and label new technical choices. Run its acceptance checks, update STATUS honestly, inspect the diff and create the milestone commit if checks pass. Report what changed, commands/results, commit and remaining risks; stop before M02.

## D4. Decision provenance and actual status

Approved: S01, source contract v0.1, website schema/rules, eBay/Etsy selected schemas/rules, F01–F05 solution direction and the practical DE scope. Required: dbt and Airflow. New reporting/tool details, physical schema/release strategy and this milestone plan remain DRAFT for review.

Existing progress: the 59-file fixed fixture pack passed 10 offline checks and 10 utility unit tests; the user reports a successful local run. F01 fixed payloads and F03 independent mapping seed are implemented at S01 scope. F02 operational schema, F04 runtime acceptance and F05 DB materialization remain partial/pending. No source DB/HTTP services, pipeline, DAG or dashboard have run yet.

Accepted limits: no fabricated unobserved snapshots; no general Etsy shipment-to-transaction allocation; no confirmed refunds/delivery/revenue recognition without evidence; no live vendor certification or scale claim. Keep optional AI investigation outside the first delivery.



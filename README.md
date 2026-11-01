# Multi-channel Order Data Platform & Operations Reporting

Daily live local sources: start once with `python -m tools.s02_data live-up`,
then manually append with `python -m tools.s02_data generate --config tools/s02_data/config/observe_6min.json`.
No campaign selection or per-batch DAG trigger. See [full setup](tools/s02_data/README.md),
[live design](docs/16_M08_LIVE_LOCAL.md) and STATUS for actual verification.
Existing runtime data is not reset; fixed S01 regression fixtures are retained.

Local DE portfolio project: internal website database + eBay-style polling API + Etsy-style webhook/receipt API → immutable raw → dbt → PostgreSQL published data → operations/data-health dashboard. Airflow orchestrates the bounded pipeline.

**Current state:** M05A adds a local eBay HTTP simulator/collector, observed
history and fulfillment allocation models, and source-specific tested releases.
The M04 website DAG remains manual. M05B adds opt-in periodic website/eBay DAGs,
durable windows and serialized tested releases; real scheduled/restart checks
passed. M06 adds the local Etsy signed-webhook receiver, durable receipt work,
independent scheduled recovery and tested source-specific release. M07 provides
the multi-channel operations dashboard and measured pipeline monitoring; it is
committed locally. M08A isolation and M08B finite seeded-source/scheduled correctness
passed local checks. M08C is paused/incomplete, M08D is deferred, and M09 CV/demo
packaging is requested. Known Airflow health/availability and latency limits are
open; this is a local portfolio, not a certified production release.
See the [M08B guide](test_support/M08B.md),
[M08A guide](test_support/README.md),
[polling guide](orchestration/POLLING.md),
[Etsy guide](orchestration/ETSY.md) and exact evidence/limits in STATUS.

## Start here

- [Documentation map](docs/README.md)
- [Actual status](docs/STATUS.md)
- [Milestones](docs/04_PLAN.md)
- [S02 test environment, recovery and load plan](docs/10_S02_TEST_STRATEGY.md)
- [M08A isolated test harness and safety prerequisites](test_support/README.md)
- [Automatic operation: current gaps and acceptance](docs/06_AUTOMATION.md)
- [VS Code / Codex guide](docs/CODEX_VSCODE.md)
- [AI repository instructions](AGENTS.md)
- [Target field dictionary](docs/05_TARGET_SCHEMA.md)
- [Local PostgreSQL, website acquisition, and dbt release](infra/README.md)
- [Airflow website workflow and recovery](orchestration/README.md)
- [eBay HTTP source and M05 acceptance](simulator/README.md)

## Run the existing offline fixture checks

Python 3 with the standard library is sufficient. From this repository root:

```bash
cd fixtures/s01
python verify.py
python -m unittest -v test_tools.py
```

Use `python3` instead if that is the installed executable. These commands validate the synthetic fixture/utility contract, not runtime ingestion. Source provider accounts are not required.

## S01 acceptance

Three independent orders, four lines, six ordered units and USD124 original merchandise amount. Six observed order versions (website/eBay/Etsy: 3/2/1), eight archived line rows, two logical webhook messages and three deliveries. Missing historical states must never be invented. Source states and expected outputs are separate test-only inputs.

## Repository organization

Implemented directories include `fixtures/`, `docs/`, `simulator/`, `ingestion/`,
`transformation/`, `transformations/`, `orchestration/`, `migrations/`, `tests/`
and `infra/`. M07 adds the read-only Streamlit dashboard under
[`reports/`](reports/README.md) (localhost:8501). One repository
supports a local demo while preserving source access boundaries.

The eBay/Etsy simulators implement selected local read subsets: fixed S01 by
default, opt-in bounded S02 current-state stores for tests.
Neither is a certified replica or completed live integration. A
frozen fixture does not generate new orders when polled. M05B adds scheduled jobs;
M08A isolates test storage/runtime; M08B adds a separate opt-in finite S02 driver;
M08C has partial recovery evidence; its complete matrix is paused. M08D load/stability
testing is deferred. M09 packages supported demos and reproducibility with these
limits visible. No measured production scale is claimed.

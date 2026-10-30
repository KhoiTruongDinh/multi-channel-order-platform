# Multi-channel Order Data Platform & Operations Reporting

Local DE portfolio project: internal website database + eBay-style polling API + Etsy-style webhook/receipt API → immutable raw → dbt → PostgreSQL published data → operations/data-health dashboard. Airflow orchestrates the bounded pipeline.

**Current state:** M05A adds a local eBay HTTP simulator/collector, observed
history and fulfillment allocation models, and source-specific tested releases.
The M04 website DAG remains manual. M05B adds opt-in periodic website/eBay DAGs,
durable windows and serialized tested releases; real scheduled/restart checks
passed. M06 adds the local Etsy signed-webhook receiver, durable receipt work,
independent scheduled recovery and tested source-specific release. The dashboard
remains M07. See the [polling guide](orchestration/POLLING.md),
[Etsy guide](orchestration/ETSY.md) and exact evidence/limits in STATUS.

## Start here

- [Documentation map](docs/README.md)
- [Actual status](docs/STATUS.md)
- [Milestones](docs/04_PLAN.md)
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

The eBay/Etsy simulators implement only the selected fixed local subsets.
Neither is a certified replica or completed live integration. A
frozen fixture does not generate new orders when polled. M05B adds scheduled jobs;
M08 adds a separate opt-in changing-source demo. No measured production scale
is claimed.

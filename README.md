# Multi-channel Order Data Platform & Operations Reporting

Local DE portfolio project: internal website database + eBay-style polling API + Etsy-style webhook/receipt API → immutable raw → dbt → PostgreSQL published data → operations/data-health dashboard. Airflow orchestrates the bounded pipeline.

**Current state:** M01 adds the local PostgreSQL bootstrap, role boundaries,
target schema contract, and stable empty publication surfaces. Source services,
runtime ingestion, dbt models, DAGs, and dashboard are not implemented yet.

## Start here

- [Documentation map](docs/README.md)
- [Actual status](docs/STATUS.md)
- [Milestones](docs/04_PLAN.md)
- [VS Code / Codex guide](docs/CODEX_VSCODE.md)
- [AI repository instructions](AGENTS.md)
- [Target field dictionary](docs/05_TARGET_SCHEMA.md)
- [Local PostgreSQL bootstrap](infra/README.md)

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

`fixtures/` and `docs/` are included now. Planned application directories are `simulator/`, `ingestion/`, `transformations/`, `orchestration/`, `migrations/`, `reports/`, `tests/` and `infra/`; milestones create them when needed. One repository supports an end-to-end demo while preserving source access boundaries.

eBay/Etsy services are planned local implementations of selected public contracts, not certified replicas or completed live integrations. No measured production scale is claimed.

# Local PostgreSQL, website acquisition, and dbt release

PostgreSQL is pinned to the official `postgres:16.15-bookworm` image. Copy
`.env.example` to `.env` and replace every placeholder before starting. `.env`
is ignored by Git. The default host port is `55432` to avoid colliding with an
existing local PostgreSQL; set `POSTGRES_PORT` to override it.

```powershell
docker compose --env-file .env --file infra/compose.yaml up --detach --wait
docker compose --env-file .env --file infra/compose.yaml exec -T postgres sh -c `
  'psql --username "$POSTGRES_USER" --dbname data_platform --command "TABLE public.schema_migrations;"'
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/migrate.ps1
Get-Content tests/m01_acceptance.sql -Raw | docker compose --env-file .env --file infra/compose.yaml exec -T postgres `
  sh -c 'psql --username "$POSTGRES_USER" --dbname data_platform'
```

The official image runs `infra/postgres/bootstrap/00-bootstrap.sh` only when the
named volume is first initialized. `migrate.ps1` is the explicit rerun path for
idempotent database baselines and platform migrations. It resolves the root
`.env` automatically; pass `-EnvFile path\to\another.env` to override it.
Never delete the named volume merely to apply a migration. A clean-volume test
may remove it only when the operator has confirmed it contains disposable local
test data.

`website_source`, `marketplace_sim`, `data_platform`, and `airflow_meta` are
separate databases in one lightweight instance. Marketplace ingestion is never
given database credentials; later milestones must use HTTP. The website reader
does not receive write access. Report clients receive only `platform_report`.

## M02 website scenario

Apply the source schema to an existing volume, then run the complete S01
acquisition acceptance sequence:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/migrate.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m02_s01.ps1
```

The runner builds two separate tool images. `website-simulator` contains the
allow-listed website source-state fixtures and connects as `website_writer`.
`website-collector` contains no fixture directory and connects to the source as
read-only `website_reader`, then appends audit rows as `platform_ingest`.

Each run uses a new execution ID and appends evidence; rerunning does not erase
earlier raw records. The sequence intentionally creates one failed run after a
durable raw write, then saves the three scheduled observations and one replay.
The final SQL assertions verify the observed cancellation states, checkpoint,
replay audit, and database role boundaries. It leaves source state `0914`
loaded and the PostgreSQL service running. It does not run M03 transformations,
so core and mart tables remain empty until M03 is run.

## M03 website dbt and release

Prerequisite: M01 migrations and the complete M02 observation sequence have run.
Use the existing volume; the runner consumes retained platform raw, never the
source-state fixtures or golden warehouse outputs.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m03_s01.ps1
```

The runner builds the pinned dbt Core/PostgreSQL adapter image, freezes the
eligible raw IDs into `ops.batch_inputs`, and builds/tests candidates as
`platform_transform` in `build`. The raw manifest includes successful website
acquisitions, including replay audits; failed acquisitions remain retained but
are excluded. First-observed source versions are deduplicated independently
of mapping/transformation versions.

After every required model and test passes, the batch command validates the
batch ID and invocation ID in `manifest.json`/`run_results.json`, and marks the
batch `TESTED`. The separate `platform_publisher` command copies its candidates
into stable website core/mart tables and updates `ops.publication_state` in one
transaction. The account/source keys and report views are unchanged.

Acceptance then builds a second batch with `inject_test_failure: true`, verifies
that exactly the injected dbt test fails, rejects publication of that failed
batch, and checks the previous publication through the report role. Expected
output ends with `M03 ... PASS`; the injected test error and rejected publish
traceback are intentional. Published data must show one current order/line,
three observed versions, two original units and USD40, with cancellation
preserving the paid state and original purchase amounts.

Artifacts are retained per batch under ignored `runtime/dbt/<batch UUID>/`.
The SQL/Python fingerprint parity check mounts fixtures only into its test
container; normal dbt/publisher services contain no fixture directory.

Run one transform/publication sequence at a time. `freeze` rejects a second
batch while one is `FROZEN`, `BUILDING`, or `TESTED`. For a genuinely interrupted
batch, inspect its run/artifacts and explicitly mark it failed before starting
another sequence:

```powershell
docker compose --env-file .env --file infra/compose.yaml --profile m03 run --rm `
  dbt-transform python -m transformation.batch failed --batch-id <batch-uuid> `
  --expected-status BUILDING --artifact target/<batch-uuid>/run_results.json
```

Use the actual persisted state as `--expected-status`; this is an explicit abort,
not an automatic database reset. dbt commands issued manually outside this
lifecycle are not supported for publication. Mapping version `s01-v1` is treated
as immutable during a run; mapping corrections must use a new version.

To inspect the published result in DBeaver, connect to `data_platform` and query
`report.orders_current`, `report.order_lines_current`, `report.order_activity_daily`,
`report.product_activity_daily`, and `report.publication_state`. The repeatable
read report SQL used by acceptance is `tests/m03_report.sql`.

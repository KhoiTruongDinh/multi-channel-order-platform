# Local PostgreSQL and M02 website acquisition

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
so core and mart tables remain empty.

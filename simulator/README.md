# M05A eBay local HTTP source

For the M06 local Etsy receipt/list simulator, signed sender and receiver/worker
workflow, see [the Etsy operating guide](../orchestration/ETSY.md). These are local
fixed subsets, not live vendor integrations.

This guide covers the implemented CLI/source part. M05B also implements eBay
Airflow orchestration and opt-in periodic polling; see [the polling guide](../orchestration/POLLING.md).
The existing `run_m05_s01.ps1` output `M05 PASS` refers to the original M05A checks,
not the separate `M05B PASS` scheduler/recovery acceptance. See STATUS for both.

This is a fixed, local simulation of the approved eBay subset, not a live vendor
integration. `ebay_api.py` uses Python's standard-library HTTP server to avoid a
new framework dependency for four GET routes. Website playback stays unchanged.

Data listener (container port 80, localhost port 8081 by default):

- `GET /sell/fulfillment/v1/order?filter=lastmodifieddate:[from..to]&limit=1&offset=0`
- `GET /sell/fulfillment/v1/order/{orderId}`
- `GET /sell/fulfillment/v1/order/{orderId}/shipping_fulfillment`
- `GET /sell/fulfillment/v1/order/{orderId}/shipping_fulfillment/{fulfillmentId}`

The local bearer token defaults to `local-s01-test-token`; override
`EBAY_SIM_TOKEN` in `.env` for both source and collector. There is one authenticated
seller, `seller_sim_01`. Production OAuth and seller onboarding are out of scope.
Fulfillment collections have no order-list pagination fields.

Test controls use a separate container listener 8081, published only on localhost
8091 by default. `POST /state` accepts `{"state":"0902"}` or `{"state":"0912"}`.
It changes only the simulator's in-memory source state; it never clears a database.
Restart defaults to 0912. Freeze source state while a collection runs. The controls
are development-only, not a marketplace API; do not expose either listener remotely.

Optional control fields are separate test variants: `repeat_page` repeats the same
order on a second page; `extra_order` makes a second synthetic order for HTTP tests;
`bad_next` returns an untrusted next origin; `fail_offset`, `error_status` and
`errors_left` inject bounded request failures. These are never golden business
outputs and must not be enabled for normal collection. Only simulator/test code
reads source fixtures. The collector image has no fixtures or source DB credentials.

## Local acceptance

After M01-M04 with the retained website history:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m05_s01.ps1
```

The runner builds/starts eBay, tests two distinct orders across two pages using a
disposable in-memory HTTP server, then runs the fixed S01 source through HTTP into
PostgreSQL. The S01 runtime variants use repeated pages without introducing another
business order. It tests a failed second page (five 500 responses), interruption
after durable page/work, untrusted pagination, a 429 retry with Retry-After, replay,
older observations after newer ones, and successful empty windows. It then runs
dbt/tests, checks Python/SQL fingerprint parity, publishes eBay only, and verifies
that an injected dbt failure cannot replace the good release. Expected final line:
`M05 PASS execution=... publication=...`. Intermediate failures are intentional.
No volumes, website source/raw, or previous acquisitions are removed.

The additional read-only negative-evidence suite executes the actual dbt SQL with
literal invalid allocations/timestamps and conflicting resource observations:

```powershell
docker compose --env-file .env --file infra/compose.yaml run --rm -T --no-deps `
  --volume "${PWD}:/repo:ro" dbt-transform python /repo/tests/test_m05_constraints.py
```

Normal collection after startup (explicit fixed S01 window):

```powershell
docker compose --env-file .env --file infra/compose.yaml run --rm -T ebay-collector `
  --execution-id manual-ebay-final --window-start 2026-10-17T09:01:00Z `
  --window-end 2026-10-17T09:13:00Z --observed-at 2026-10-17T09:13:00Z
```

Without `--window-start`, the collector reads its successful checkpoint minus
120 seconds (`--overlap-seconds` can override); the first run requires a start.
All required raw and identified detail work are committed before advancing pages.
The window succeeds only after required detail and shipping requests also succeed.
Failed cycles retain raw and failed/pending work; a new explicit acquisition cycle
reconciles the fixed window. There is no automatic stale-worker/raw-only queue
drainer in M05. Processing completion and acquisition audit remain distinct.

Each request allows at most five total attempts for timeouts, 429 and selected
5xx, using exponential backoff/jitter and Retry-After (numeric or HTTP date).
Retry-After above 60 seconds ends the bounded cycle for later replay. Permanent
errors stop without deleting source entities. Redirects are disabled; pagination
and fulfillment links must match the configured origin and requested paths/bounds.
Offset paging is not snapshot isolation; changing totals/list-detail evidence
fails reconciliation. Same-total moving-page completeness is not guaranteed.
List/detail comparisons allow the documented empty list `cancelRequests` versus
populated detail, and line-array reordering; the full detail bytes remain retained.

## Transformation and review

Read `ingestion/ebay.py`, `transformations/models/ebay/`,
`transformations/macros/ebay_canonical.sql`, and `transformations/tests/ebay*.sql`.
The existing batch/publisher commands accept `--source ebay_sim`; default remains
website. Use `mapping_version=s01-v1`, `transformation_version=m05-v1`, and
`release_source=ebay_sim` in dbt vars. The runner contains the exact release steps.
eBay freeze includes retained successful website inputs so all existing website
regression models/tests still run; only eBay candidates are copied on eBay release.
The global active-batch guard protects the shared build schema: never run M03,
M04, or M05 transforms concurrently. Inspect/finish or explicitly fail an active
task-created batch after an interrupted build before starting a new cycle.

DBeaver: database `data_platform`, host localhost, configured PostgreSQL host port
(5433 in the existing owner setup). Query `report.orders_current` and
`report.order_lines_current` filtered by `source_system='ebay_sim'`.
Expect one eBay order, two lines, three units, USD62 and two observed versions.
FUL001 contains both blue units; white has no shipment allocation. Combined
website/eBay output is two orders, three lines, five units, USD102. Etsy is M06.
Raw/evidence counts grow on replay while source-version counts remain fixed.
Test faults remain visible in health/audit; coverage is UNKNOWN, not COMPLETE.

The implemented M04 DAG remains website-only. eBay acquisition/release is a
reusable CLI in M05A; M05B wraps it in bounded periodic and manual-replay DAGs.
Recurring polling will not advance the frozen fixture or create new orders;
M08 adds a separate opt-in current-clock source driver. The broader recovery
campaign also remains M08. No actual vendor/sandbox authentication, source
DB-backed marketplace service, load test or production-grade server is claimed.

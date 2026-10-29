# M06 implementation readiness and delivery sequence

Reviewed/implemented: 2026-10-28. M05 is committed; M06 code and acceptance evidence
are now recorded in STATUS, with commands in `orchestration/ETSY.md`. The original
gates below remain the review checklist, not standalone runtime proof. Do not start M07 or change
approved S01/source semantics. No live Etsy accounts, OAuth or provider SLA claim.

## Inputs and fixed behavior

Read `02_SOURCE_CONTRACTS.md` B7-B9, `contracts/17_EtsySchema.csv`,
`contracts/18_EtsyRules.csv`, `05_TARGET_SCHEMA.md` and `06_AUTOMATION.md`.
Use the receipt/list examples, signed deliveries and fingerprint utilities in
`fixtures/s01` for simulator/test implementation, never as pipeline interfaces.

- Source/account: `etsy_sim` / shop `7001`; receipt `9001001`, transaction
  `8001001`. Shop context is not `seller_user_id`. Raw IDs retain their wire types.
- Baseline D1/D2/D3 means three deliveries, two logical messages and two receipt
  reads of the same observed version. Do not coalesce the distinct paid/shipped
  messages into one fetch or refetch solely for the duplicate D3 delivery.
- First observed receipt is already paid and shipped: one current order/line,
  one history version, one unit/USD22, PAID/SHIPPED/UNKNOWN cancellation.
  Never manufacture the 09:04 paid-only snapshot, delivered evidence, refunds or
  transaction-to-parcel allocations absent from the selected contract.
- Preserve nullable product fields/lines, exact amount/divisor arithmetic and
  separate subtotal/total/grandtotal meanings. Match `etsy_receipt` fingerprint
  canonicalization, including alias conflicts and absent/null distinctions.

## Implementation gates, in order

1. Finalize target definitions before DDL. Inventory existing inbox/delivery/work
   tables; specify dedupe keys, raw/run/inbox/work/batch links, rejection audit,
   attempts, retry times, lease ownership/fencing and recovery-cycle identity.
   Persist any additional fields in `05_TARGET_SCHEMA.md` before a new migration.
   A lease deadline alone is not sufficient proof that an old worker still owns
   work. Define expiry/reclaim and forbid stale owners completing reclaimed work.
2. Add fixed receipt detail/list HTTP simulator plus signed sender. List uses
   count/results, explicit modified bounds, updated sort, limit/offset and local
   receipt-ID tie-break, not an invented next URL. Test controls stay separate.
3. Add always-on receiver outside Airflow. Verify exact raw bytes and signing
   headers before interpreting JSON; use decoded signing secret, constant-time
   comparison and the approved configurable 300-second execution-clock tolerance.
   Validate configured subscription/shop and allowed resource origin/path; reject
   redirects, foreign shops/receipts and arbitrary URLs before any worker fetch.
4. In one transaction retain raw delivery evidence, logical inbox identity,
   delivery audit and required work before successful acknowledgment. Every valid
   duplicate gets a delivery audit but no second logical work item. Concurrent
   duplicates must be safe; conflicting content under one message ID must not
   overwrite the first message. Known unsupported events are retained/ignored
   without inventing state. Specify HTTP statuses, body/header limits and bounded
   reads; DB persistence failure must return non-success, never a false durable ACK.
5. Add reusable bounded worker/recovery commands. Claim durable work atomically;
   retain each HTTP attempt and checkpoint windows only after required responses
   and work are durable. Receipt completion is distinct from tested publication.
   Timeout/429/5xx use bounded backoff and Retry-After; 404 remains unresolved,
   not deletion. 400/401/403 cannot silently complete a source/window. Fix nested
   HTTP/workflow retry limits and preserve at most five work-cycle attempts across
   retry, restart, scheduler invocations and clear. An exhausted work cycle needs
   explicit controlled replay, not an automatic reset on every scheduled tick.
6. Extend source adapters and dbt release together. Current `polling.py`,
   `website_workflow.py`, `transformation/batch.py` and `publish.py` hard-code
   website/eBay source/account/resource/candidate choices. Add Etsy explicitly;
   do not treat every non-website source as eBay. Keep frozen manifest/mode/version
   checks and source-specific atomic `etsy_orders` publication; only committed,
   eligible receipt acquisitions become business snapshots, not notification bodies
   or rejected deliveries. Preserve website/eBay publication pointers and facts.
7. Add opt-in scheduled inbox drain and independent recovery scan DAGs, using
   reusable commands and the M05 coordinator/active-batch guard. Queue draining
   needs no extraction window; do not force it into the polling-window API.
   Recovery scans have explicit bootstrap, immutable upper bounds, 120-second
   default overlap and separate historical/runtime checkpoint scopes. Serialize
   the shared freeze-to-publish section across all sources and CLI workflows.
   Callbacks must still ACK durable deliveries while release coordination is busy.
8. Run deterministic acceptance, real scheduled/restart/negative checks and M05
   regression, record exact evidence, then stop for owner review. Do not reset
   the owner's volume/source state to obtain golden counts.

## Configuration and clock separation

During implementation choose/pin the receiver dependency and finalize environment
names for API token/origin, shop/subscription/signing secret, callback bind/port,
freshness tolerance, job intervals, bootstrap/overlap and lease/network limits.
Only placeholders belong in `.env.example`; no actual secrets in docs/logs/Git.
The previous FastAPI proposal was resolved to the already pinned standard-library
HTTP/Psycopg stack for this bounded local receiver; no new framework or production
deployment claim. Target operational additions are finalized in the dictionary
and migration 005, including lease fencing and explicit collection lineage.

Generate fresh delivery headers/signatures at send time; do not replay stale fixed
headers or disable freshness. `render_webhooks.py` renders but does not send, and
its existing synthetic secret is a test key, not arbitrary environment credentials.
Sender and receiver must use matching configured test credentials. Leave approved
fixture bytes unchanged. Actual received/fetched time and business S01 timestamps
are separate; specify simulated observation provenance before implementation.
No worker/DAG may read source controls, expected outputs or the scenario ledger.

Scheduled jobs default paused and use environment-configurable intervals; the
receiver stays available independently. Preserve the approved S01 observation
schedule and use separate operational scopes for current-clock recovery and
negative variants. A current-clock scan of frozen historical fixtures may be empty;
the missed-notification test must explicitly cover the receipt's modified time.
No new changing-source driver is required until M08.

## Required acceptance and evidence

| Check | Required result |
| --- | --- |
| Fixed S01 | Three delivery attempts, two inbox messages, one Etsy history/current order/line, one unit/USD22; combined three orders/four lines/six units/USD124 and six order-history versions |
| Replay/reordered events | Both event orders and duplicate delivery preserve one version/current state; raw/audits grow, no regression |
| Security | Altered bytes, malformed/missing signatures, stale/future timestamps outside tolerance and foreign URL/shop are rejected without fetch; valid signature-entry handling matches fixtures |
| Receiver persistence | Restart after inbox commit still drains; unavailable DB never produces success ACK; duplicate/concurrent delivery cannot create duplicate work |
| Worker recovery | Lease expiry/reclaim prevents stale-owner completion; retained failed HTTP/work evidence, bounded attempts and no counter reset after Airflow clear |
| Scheduled drain | At least two real scheduler-created cycles, accepted work processed without per-message manual commands; receiver never invokes dbt |
| Missed notification | Independent scheduled recovery list finds an omitted-notification receipt through HTTP and publishes without inventing inbox messages |
| Release concurrency | Etsy overlaps website/eBay operation without shared candidate interleaving; failed tests preserve each source's last good release |
| Data quality | SQL/Python fingerprint parity, aliases, positive divisor including non-100 case, nullable products, mapping exceptions and invariant tests; S01 golden assertions remain separate |
| Regression/roles | M05 fixture/CLI/manual/polling evidence preserved; least-privilege service and source boundaries remain intact |

For repeated runs, assert delivery/acquisition deltas scoped to the new test run;
do not demand that retained audit totals stay three or erase previous evidence.
Keep negative variants separate from the valid baseline. If a test needs a clean
scope, design it explicitly without silently changing approved IDs or resetting
the owner's data. Broader exception remediation and destructive cold setup remain
M08; a restricted read-only dashboard/live-health interface remains M07.

Implementation resolution: gate 1 is the finalized M06 dictionary/migration 005;
runtime uses `etsy_inbox`, `etsy_recovery` and manual `etsy_replay`, with separate
acceptance checkpoint scopes, source-wide durable Retry-After checks, and the
shared release coordinator. DAG contention yields via bounded retry after 15
seconds; backward lifecycle audit clocks are clamped without rewriting source
time. See STATUS for each check, intermediate failure and remaining limitation.

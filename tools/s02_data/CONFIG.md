# S02 generator configuration reference

## Optional observation campaign

The same JSON schema now accepts `campaign`; see [CAMPAIGN.md](CAMPAIGN.md#configcampaign-fields)
for its typed fields and normal/recovery commands. generate/prepare validate and
retain that section but DO NOT execute it. Only the campaign command with explicit
local consent can start schedules; an eBay pause additionally requires --allow-faults.
Optional `campaign.measurement` and `campaign.load` grade a predeclared finite
envelope; profiles without them remain observation-only. This is not production
SLA/capacity certification. See [the current load path](CAMPAIGN.md#current-calibrated-load-path).
No config filename is special.

## Prepared live webhook delivery plan (SIM extension)

Any JSON profile may opt in with `channels.etsy_sim.delivery_plan`; the filename
is not hardcoded. See [sim_delivery_demo.json](config/sim_delivery_demo.json) and
[read-only SQL inspection](inspect_delivery.sql). This is a SIM feature, not the
M08D campaign controller. New plans use live generate/live-source only; explicit
legacy playback refuses them before activation. Profiles without this object
retain existing behavior and require no JSON edits.

| Field inside `delivery_plan` | Default | Meaning |
| --- | --- | --- |
| `seed` | Resolved event_seed | Integer0..2147483647; independent delivery RNG |
| `reorder` | 0 | Non-omitted orders with a paid/shipped pair to reorder; nonzero requires faults profile |
| `delay_seconds` | `[0,0]` | Initial notification delay range; inclusive integers0..86400 |
| `repeat_count` | 2 | Total planned sends per message on duplicate-order quota; integer2..10 |
| `repeat_gap_seconds` | `[5,10]` | Inclusive repeat gap range,0..86400 |
| `late_gap_seconds` | `[5,10]` | Paid first-send delay after shipped first-send;1..86400 |

Existing notifications.omit/duplicate remain disjoint **order** quotas, not
message counts. Reorder selects eligible order keys with the delivery seed and
can overlap duplicate, never omission. Infeasible quotas fail before DB writes.
Source versions and updated timestamps are not altered to fake delivery order.
Source time and actual UTC send/ACK/retry time are stored separately; live
admission applies the same shift as source versions. Sends can extend beyond
source end_at: inspect manifest.delivery_plan.last_due_at.

Plan version1 lives in local_datasets.coverage.delivery_plan. Logical messages
reference source versions; child s02.delivery_schedule rows hold planned sends
without copying payloads. Plans are sealed; progress is mutable. Lost ACKs or
sender crashes can cause extra physical retries, not extra logical messages.
generate checks that the running live-source image supports the extension;
rebuild that image first. Missing capability fails before dataset preparation.
No negative-data or transport/controller faults are enabled by these fields.

Configuration describes manually prepared source data, not Airflow scheduling.
Daily: start live-up once, then run `python -m tools.s02_data generate --config <path.json>`
manually to append live data. prepare only stores data for explicit replay;
it does not publish to live APIs. There is no generation
on Docker startup, API GET or DAG execution. Secrets belong in `.env`, not JSON.
See [workflow commands](README.md) and [storage/clock contract](../../docs/15_S02_LOCAL_WORKFLOW.md).

Live mode translates the persisted source timeline to admission time, keeping
relative intervals; dates below describe the prepared timeline. Exact historical
business dates require replay, not generate. Both original config and live shift
remain visible in DB. See [live contract](../../docs/16_M08_LIVE_LOCAL.md).

## Minimal five-hour workload

```json
{
  "dataset": "my-five-hour-demo",
  "timezone": "Asia/Bangkok",
  "order_seed": 17,
  "event_seed": 91,
  "channels": {
    "internal_web": {"orders": 6},
    "ebay_sim": {"orders": 4},
    "etsy_sim": {"orders": 5}
  }
}
```

Omitting global `start_at` resolves it to the actual instant of config validation
at manual prepare, to whole seconds. Omitting global `end_at` resolves it to
the resolved global start plus `duration_minutes` (**300 minutes / five hours** by default). Global missing, `null`
and `""` dates all use these defaults. An explicit date must include its UTC
offset, e.g. `2026-10-31T10:00:00+07:00` or `2026-10-31T03:00:00Z`.

For example, prepare at10:00+07 without either date gives10:00–15:00+07.
Explicit start01:00+07 with omitted end gives01:00–06:00+07, not now+5h.
If only end is specified, start is now; an end before/equal to start is rejected.
The config can store resolved timestamps in UTC; these are the same instants.
`timezone` controls local peak-hour interpretation, not a different machine clock.

All resolved dates and seeds are saved in `marketplace_sim.s02.campaigns.config`
and the dataset manifest. Reading/starting/resuming a prepared dataset does not
recompute them. To reproduce exactly, reuse the **resolved** config/code/catalog,
not a moving-now input. Existing dataset names are refused, not overwritten.
Changing the name changes the campaign/order identity namespace.

## Global fields

| Field | Default | Meaning and constraints |
| --- | --- | --- |
| `dataset` | Required | Name3..61 characters matching `[a-z][a-z0-9-]{2,60}`. prepare requires a unique name; generate uses the first48 characters as a prefix plus an automatic unique suffix, so repeated calls append without edits |
| `timezone` | `UTC` | Peak-hour timezone inherited by channels. `Asia/Bangkok`, `Asia/Ho_Chi_Minh`, `UTC` work without host tzdata; other available IANA zones may require tzdata |
| `start_at` | Current instant | Inclusive source generation start; explicit ISO8601 needs an offset |
| `end_at` | Global start+duration | Exclusive generation end; events at this instant are not generated |
| `duration_minutes` | `300` | Global fallback duration when `end_at` is missing/null/empty; integer1..527040 (366 days). Explicit `end_at` wins. Does not change polling intervals or playback speed |
| `order_seed` | Chosen once | Integer0..2147483647. Controls purchase choices/customer/basket/creation time; not order count |
| `event_seed` | Chosen once | Integer0..2147483647. Controls weighted lifecycle choices and causal delays; not event count |
| `profile` | `normal` | `normal`, `coverage` or `faults`; only `faults` permits nonzero notification fault quotas |
| `channels` | Required | Exactly `internal_web`, `ebay_sim`, `etsy_sim`; set `orders: 0` to disable generation for a source |

Seeds derive separate per-source/per-order random streams. Increasing eBay volume
does not reshuffle Website purchases. Reproducibility also requires fixed dates,
all other config, generator version and catalog. `coverage` does not automatically
populate quotas: declare `required` yourself. Current sample files retain their
explicit historical dates; those take precedence over the new defaults.

## Short manual demo (five or six minutes)

Use `config/quick_6min.json`: empty global dates, `duration_minutes: 6`, six
orders per source and per-transition `delay_seconds: [15, 30]`. Change duration
to5 for five minutes. Existing files and prepared datasets are not modified.

```powershell
python -m tools.s02_data prepare --config tools/s02_data/config/quick_6min.json
python -m tools.s02_data inspect --dataset local-s02-quick-6min-01
```

Choose a fresh dataset name for each new preparation. Prepare writes immutable
source plans/references, NOT pipeline output and does not activate playback.
The duration begins at resolved prepare time, not when Airflow becomes healthy.
An old plan viewed through realtime may already expose its final states; replay
from the stored start is appropriate for inspecting its timeline (existing local
activation/retention guards still apply). No reset or second environment is
implied by this configuration.

Shorten transition delays as well as the range: the default maximum3600s cannot
fit required cancel/full-shipping branches in six minutes and is rejected.
Nonreserved branches can still stop at the window boundary. A short source
window is NOT an end-to-end runtime limit: startup, polling and dbt can take
longer. Fast transitions may occur between polls; warehouse history contains
only observed snapshots, not every prepared version. Full scheduled acceptance
still requires at least two successes per path and reconciliation.

## Per-channel fields

| Field | Default | Meaning and constraints |
| --- | --- | --- |
| `orders` | Required | Exact order count, integer0..100000. This input limit is not certified pipeline capacity |
| `start_at`, `end_at` | Each inherits global value | Override the range for just this source; explicit nonempty offset-aware strings required. A channel start override alone does NOT recalculate its inherited end |
| `timezone` | Global timezone or `UTC` | Timezone used for this source's peak-hour windows |
| `peak_hours` | `[]` | Relative arrival-rate windows; see below |
| `basket` | 1..8 lines,1..5 quantity | All four fields required when this object is provided; see below |
| `branches` | pending0.25; cancel/ship0.75 | Weighted lifecycle selection for orders not reserved by `required` |
| `delay_seconds` | `[60, 3600]` | Inclusive min/max seconds **per transition**. Integers,1<=min<=max<=2592000 |
| `required` | `{}` | Minimum distinct order counts reserved for named lifecycle branches |
| `notifications` | `{"omit":0,"duplicate":0}` | Etsy-only order quotas for notification faults; nonzero requires `profile: faults` |

Each effective channel range must start on/after2026-01-08T00:00:00Z and span
1 second..366 days. Unknown fields, invalid ranges or infeasible quotas are
rejected before source loading. Dates are normalized to second precision.

### Basket

```json
"basket": {
  "lines_min": 2,
  "lines_max": 8,
  "quantity_min": 1,
  "quantity_max": 5
}
```

Line counts are distinct purchased products; quantity is units per line.
Supported line bounds:1..8; quantity bounds:1..100. Each min must be<=max.
eBay's partial-shipping branch requires `lines_min >= 2`. Prices come from the
fixed30-product catalog;100 synthetic customers and90 mapping rows are shared
references, not configurable counts. Not every small workload buys every product.

### Peak hours

```json
"peak_hours": [{"start":"19:00","end":"22:00","weight":3}]
```

In that source's local timezone, arrival rate inside19:00–22:00 is weighted3x
the outside baseline1x, not a fixed75% share. Sampling uses duration*weight.
Windows recur daily, must use `HH:MM`, may cross midnight (`22:00`–`02:00`),
must not overlap, must have different start/end and finite positive weights.
Windows outside the configured date range have no effect. Required orders may
use a shortened creation range so their full branch fits before the exclusive end.

### Branches and required quotas

| Source | Branch | Prepared lifecycle |
| --- | --- | --- |
| Website | `pending` | Initial order only; pending here means no planned progression, not necessarily unpaid |
| Website | `request` | Initial → cancellation requested |
| Website | `cancel` | Initial → cancellation requested → canceled |
| eBay | `pending` | Initial order only |
| eBay | `partial` | Initial → partially fulfilled; requires at least2 lines |
| eBay | `ship` | Initial → partial → fulfilled for multiple lines; initial → fulfilled for one line |
| Etsy | `pending` | Initial receipt only |
| Etsy | `ship` | Initial → shipped receipt |

Example Website block:

```json
"internal_web": {
  "orders": 6,
  "branches": {"pending": 0.2, "request": 0.3, "cancel": 0.5},
  "required": {"pending": 1, "request": 1, "cancel": 1},
  "delay_seconds": [60, 180]
}
```

Three distinct orders are reserved: one stops initial, one stops at requested,
one completes cancellation. The other three choose branches by the given weights;
they can add to those counts. A cancel order passing through requested does NOT
satisfy the separate `request` quota, which means a branch ending at requested.
Quotas count **orders**, not events, and do not add orders on top of `orders`.
Sum of quotas must be<=orders. Quotas can require a branch absent from `branches`.

Weights need not sum to1; must be finite/nonnegative with a positive total.
Default nonreserved choices: Website pending:cancel=0.25:0.75;
eBay/Etsy pending:ship=0.25:0.75. The event seed selects the branch and delays;
events always follow the allowed causal path. Random nonreserved orders created
near the end may stop before completing their planned branch. Reserved orders
must have room for every transition: transitions*maximum_delay < range duration,
otherwise validation refuses the config rather than claiming coverage.

There are no new Website shipping, marketplace refund/cancellation or delivered
branches here. This generator is not a full vendor business simulator.

### Notification faults

```json
"profile": "faults",
"channels": {
  "internal_web": {"orders": 2},
  "ebay_sim": {"orders": 2},
  "etsy_sim": {"orders": 4, "notifications": {"omit": 1, "duplicate": 1}}
}
```

This example is a fragment of a workload: also supply `dataset`.
The first Etsy order omits all planned notifications (API state still exists);
the next order duplicates its notifications using the same message identity.
These are disjoint order quotas, not percentages or total event counts.
Each quota is integer0..orders, their sum<=orders; either key may be omitted.
Physical attempts remain audited while logical messages/versions deduplicate.
Preparation records a fault plan; it does NOT prove recovery/dedupe passed.
API429/500/timeout/malformed, invalid signature, missing mapping and crash/restart
faults are not injected by these fields. Broader runtime checks remain M08C.

## Configuration is not scheduling or playback

### Finite low-rate step gates

Use `config/campaign_rate_website.json` (24 Website orders/6 minutes) then
`config/campaign_rate_mixed.json` (24 per source/6 minutes). Optional
`campaign.load` requires `campaign.measurement`, normal profile, no campaign
outage and active source intervals of at least360 seconds. It is not a new
generator mode; seeds, baskets, lifecycle rules and HTTP/SQL interfaces stay fixed.

| load field | Default | Allowed | Meaning |
| --- | ---: | --- | --- |
| min_scheduled_successes | 2 | integer1..10 | successes per required active-source live DAG, started during the fixed admission/source window, completed by drain deadline |
| max_drain_seconds | 900 | integer30..1800 | observation/cycle budget after configured source-window end |

Both Etsy DAGs must meet the cycle minimum when Etsy offers orders. Manual or
old successes do not count. Source-window end is shifted with live admission;
the runner cannot finish early merely because sampled orders arrived early.
Set campaign.timeout_seconds large enough for the whole source range plus drain
and60-second startup margin. Missing cycles/drain expiration fails, not a green
stress result. Report measurement.load_assessment and final_progress retain
actual SQL clocks/cycle IDs and observed backlog. Exact commit/publication
latency is still NOT_MEASURED; low-rate PASS is not soak/capacity certification.

After both low profiles PASS, owner-authorized higher examples are
`config/campaign_rate_300.json` (100/source,6min) and `config/campaign_rate_900.json`
(300/source,10min). Their max_orders1000/max_source_versions3000 and
max_pending_sends1000 are predeclared count ceilings; pending sends include future
planned sends, not just due retries. RAM/disk/DB-growth and delay/drain budgets
are unchanged. Stop on any failure/ceiling, never adjust the failed run's limits
or skip its reconciliation to proceed. See STATUS for actual runtime outcomes.

One explicitly predeclared exposure calibration is also supplied:
`campaign_rate_144.json` gives144/12min at the same0.2 orders/s as72/6min;
`campaign_rate_600.json` gives600/12min at the same0.8333/s as300/6min. Both use
the larger count ceilings and the SAME resource/latency/drain/cycle gates. They
increase total data and exposure without lowering offered pressure. Preserve
short-profile failures; do not call longer exposure a software speedup. The
qualification must pass before600/900; another failure stops this calibration.

Live-only scheduler tuning is separate from generator JSON: optional non-secret
`.env` LIVE_AIRFLOW_PARALLELISM is2 by default, supported values2 or4. Base and
disposable Compose keep2; per-DAG concurrency1 and global dbt publication
serialization remain fixed. A4-slot experiment changes executor queue capacity,
not source rules or the profile's PASS thresholds. Normal campaign startup drains
before recreating Airflow; always remeasure memory/queue and retain failed runs.

### Optional bounded campaign baseline

`campaign.measurement` is opt-in. Omit it to preserve the normal/recovery
review-only campaign behavior. Use `config/campaign_baseline.json` as a complete
12-order example; all fields below are integer limits (booleans are rejected).

| Field | Default | Allowed range | Unit / meaning |
| --- | ---: | --- | --- |
| max_orders | 100 | 1..1000 | finite order count before generation |
| max_source_versions | 500 | 1..10000 | prepared logical source versions |
| max_generated_bytes | 10485760 | 1024..104857600 | serialized generated source bytes, not DB storage |
| min_free_disk_mb | 2048 | 256..1048576 | MiB free on workspace and PG volume |
| max_db_growth_mb | 512 | 1..10240 | MiB aggregate growth of four local databases |
| max_docker_memory_percent | 90 | 20..95 | scoped Docker CLI reported memory sum / Docker RAM |
| max_container_memory_mb | 2400 | 128..16384 | MiB per observed container |
| max_pending_sends | 500 | 1..10000 | unfinished physical source sends |
| max_final_observed_delay_seconds | 1200 | 30..3600 | final source eligibility to first matching SQL observation |

These are local safety/review budgets, not capacity claims. A breach fails the
observer and preserves evidence; it does not delete an admitted source timeline
or kill the main stack. Preparation/admission is timed separately. Exact
source-commit-to-first-publication latency remains NOT_MEASURED. See
[M08D measurement](../../docs/19_M08D_MEASUREMENT.md) for scope and commands.

Five hours means the range of fake source event timestamps, not five hours of
data already published or a five-hour Airflow interval. Realtime exposes states
as actual time reaches them; replay1x uses an explicitly chosen logical clock.
Prepare performs neither activation nor pipeline execution. Read [README.md](README.md)
for opt-in commands and the existing-S01 activation guard. No volume reset or
automatic migration of current owner data is implied.

"""Render fresh test headers for local playback; does not send HTTP requests."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from fixture_tools import iso, sign, utc_seconds

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'runtime_webhooks')
    parser.add_argument('--first-delivery-at', default=None,
                        help='UTC ISO time for D1 receipt; default=current UTC time')
    args = parser.parse_args()
    start = utc_seconds(args.first_delivery_at or datetime.now(timezone.utc).isoformat())
    anchor = utc_seconds('2026-10-17T09:06:00Z')
    shift = start - anchor
    deliveries = json.loads((ROOT / 'webhooks/deliveries.json').read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    schedule = []
    for delivery in deliveries:
        did = delivery['attempt_id']
        raw = (ROOT / delivery['body_file']).read_bytes()
        old = json.loads((ROOT / delivery['headers_file']).read_text())
        stamp = int(old['webhook-timestamp']) + shift
        headers = dict(old, **{'webhook-timestamp': str(stamp),
                              'webhook-signature': sign(old['webhook-id'], stamp, raw)})
        (args.output_dir / f'{did}.body.json').write_bytes(raw)
        (args.output_dir / f'{did}.headers.json').write_text(json.dumps(headers, indent=2) + '\n')
        schedule.append({'attempt_id': did, 'send_at_utc': iso(utc_seconds(delivery['received_at']) + shift),
                         'body_file': f'{did}.body.json', 'headers_file': f'{did}.headers.json'})
    (args.output_dir / 'schedule.json').write_text(json.dumps(schedule, indent=2) + '\n')
    print(f'Rendered fresh local-test webhook deliveries in {args.output_dir}')
    print('Respect schedule.json when sending. No HTTP requests were sent.')


if __name__ == '__main__':
    main()

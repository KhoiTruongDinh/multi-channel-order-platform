"""Signed local delivery sender. Source-state/test files never enter the receiver."""
import argparse
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen

from ingestion.etsy_common import secret, signature


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--body-file', required=True, type=Path)
    p.add_argument('--message-id', required=True)
    p.add_argument('--callback', default=os.environ.get('ETSY_CALLBACK_URL', 'http://etsy-receiver:8000/webhooks/etsy'))
    args = p.parse_args()
    body, stamp = args.body_file.read_bytes(), str(int(time.time()))
    headers = {'Content-Type': 'application/json', 'webhook-id': args.message_id, 'webhook-timestamp': stamp,
               'webhook-signature': signature(args.message_id, stamp, body, secret())}
    with urlopen(Request(args.callback, data=body, headers=headers), timeout=15) as response:
        print(response.status, json.loads(response.read()))


if __name__ == '__main__':
    main()

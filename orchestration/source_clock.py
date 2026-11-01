"""Opt-in source clock over HTTP only; operational UTC clocks remain untouched."""
import json
import os
from urllib.request import Request, urlopen
from datetime import datetime


def read():
    if os.environ.get('S02_LOCAL_PLAYBACK')!='true': return None
    # Fixed configured simulator origin, not URLs received in source payloads.
    origin=os.environ['EBAY_ORIGIN'].rstrip('/')
    with urlopen(Request(origin+'/s02/clock',headers={
            'Authorization':'Bearer '+os.environ['EBAY_SIM_TOKEN']}),timeout=10) as response:
        if response.status!=200: raise ValueError('logical clock unavailable')
        value=json.loads(response.read(4097))
    if value['campaign_id']!=os.environ['S02_CAMPAIGN_ID']:
        raise ValueError('unexpected clock dataset')
    for key in ('now','initial_start'):
        if datetime.fromisoformat(value[key]).tzinfo is None: raise ValueError('naive source clock')
    return value

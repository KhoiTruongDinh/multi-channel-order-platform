"""Parse-time maintenance switch: stop new intervals, not existing task retries."""
import os


def periodic_schedule(interval, manual=False):
    mode = os.environ.get('POLLING_DRAIN_MODE', 'false').lower()
    if mode not in ('true', 'false'):
        raise ValueError('POLLING_DRAIN_MODE must be true or false')
    return None if manual or mode == 'true' else interval

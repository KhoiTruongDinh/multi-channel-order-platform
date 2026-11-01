"""Parse-time maintenance switch: stop new intervals, not existing task retries."""
import os
from pathlib import Path


def slot_wait_seconds():
    """Bounded infrastructure wait, independent of durable business attempts."""
    value = int(os.environ.get('POLLING_SLOT_WAIT_SECONDS', '15'))
    if not 0 <= value <= 600:
        raise ValueError('POLLING_SLOT_WAIT_SECONDS must be between 0 and 600')
    return value


def periodic_schedule(interval, manual=False):
    mode = os.environ.get('POLLING_DRAIN_MODE', 'false').lower()
    if mode not in ('true', 'false'):
        raise ValueError('POLLING_DRAIN_MODE must be true or false')
    signal = os.environ.get('POLLING_DRAIN_FILE', '/opt/airflow/state/polling-drain')
    if signal and signal != '/opt/airflow/state/polling-drain':
        raise ValueError('Unsupported polling drain signal path')
    drained = bool(signal) and Path(signal).is_file()
    return None if manual or mode == 'true' or drained else interval

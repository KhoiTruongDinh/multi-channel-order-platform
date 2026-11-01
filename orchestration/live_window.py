"""Live polling bounds: acquire current state, retry immutable prior windows."""
from datetime import datetime,timezone


def bounds(previous,now=None):
    if previous is not None:
        return previous[0],previous[1].get('window_policy')
    return now or datetime.now(timezone.utc),'acquisition-start'

"""Bounded test-listener configuration; disabled unless explicitly requested."""
import time
from urllib.parse import parse_qs, urlsplit


class Faults:
    def __init__(self, config=None):
        if config is not None and not isinstance(config, dict):
            raise ValueError('transport fault must be an object')
        value = config or {}
        if set(value) - {'kind', 'count', 'offset', 'delay_seconds'}:
            raise ValueError('unknown transport fault option')
        self.kind = value.get('kind', 'none')
        self.left = value.get('count', 0)
        self.offset = value.get('offset', 0)
        self.delay = value.get('delay_seconds', 11)
        if self.kind not in ('none', 'malformed', 'timeout'):
            raise ValueError('unsupported transport fault')
        if type(self.left) is not int or not 0 <= self.left <= 5:
            raise ValueError('fault count must be integer0..5')
        if type(self.offset) is not int or not 0 <= self.offset <= 1000:
            raise ValueError('invalid fault offset')
        if type(self.delay) not in (int, float) or not 0 < self.delay <= 15:
            raise ValueError('fault delay must be0..15 seconds')

    def response(self, path, status):
        """Caller serializes state access; health/control replies are never faults."""
        parts = urlsplit(path)
        if status != 200 or not self.left or parts.path in ('/health', '/state', '/control'):
            return None
        offset = int(parse_qs(parts.query).get('offset', ['0'])[0])
        if offset != self.offset:
            return None
        self.left -= 1
        if self.kind == 'timeout':
            time.sleep(self.delay)
        return b'{intentional-malformed-json' if self.kind == 'malformed' else None

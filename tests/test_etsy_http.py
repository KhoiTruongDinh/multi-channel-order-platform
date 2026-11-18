"""HTTP setup reuse without weakening per-attempt authentication or errors."""
import threading
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from io import BytesIO

from ingestion import etsy


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.local = patch.object(etsy, '_http', threading.local())
        self.local.start()
        self.addCleanup(self.local.stop)

    def test_one_opener_but_fresh_request_credentials_and_closed_responses(self):
        response = MagicMock(status=200, headers={'Content-Type': 'application/json'})
        response.read.return_value = b'{}'
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        with patch.object(etsy, 'build_opener', return_value=opener) as factory:
            for token in ('first', 'second'):
                with patch.dict(etsy.os.environ, ETSY_SIM_TOKEN=token):
                    self.assertEqual(etsy.fetch('http://example.test/receipt'),
                                     (200, b'{}', {'Content-Type': 'application/json'}))
            factory.assert_called_once_with(etsy.NoRedirect)
        requests = [call.args[0] for call in opener.open.call_args_list]
        self.assertIsNot(requests[0], requests[1])
        self.assertEqual([r.get_header('Authorization') for r in requests],
                         ['Bearer first', 'Bearer second'])
        self.assertEqual(opener.open.return_value.__exit__.call_count, 2)
        response.read.assert_called_with(2097153)

    def test_http_error_preserves_status_body_and_retry_after(self):
        opener = MagicMock()
        opener.open.side_effect = HTTPError('http://example.test', 429, 'limited',
                                            {'Retry-After': '7'}, BytesIO(b'limited'))
        with patch.object(etsy, 'build_opener', return_value=opener), \
                patch.dict(etsy.os.environ, ETSY_SIM_TOKEN='test'):
            self.assertEqual(etsy.fetch('http://example.test'),
                             (429, b'limited', {'Retry-After': '7'}))

    def test_transport_error_and_redirect_refusal(self):
        opener = MagicMock()
        opener.open.side_effect = URLError('offline')
        with patch.object(etsy, 'build_opener', return_value=opener), \
                patch.dict(etsy.os.environ, ETSY_SIM_TOKEN='test'):
            self.assertEqual(etsy.fetch('http://example.test'),
                             (599, b'', {'_transport_error': 'network_or_timeout'}))
        self.assertIsNone(etsy.NoRedirect().redirect_request())

    def test_workers_do_not_share_mutable_opener(self):
        with patch.object(etsy, 'build_opener', side_effect=lambda *args: object()) as factory:
            main = etsy.http_opener()
            other = []
            worker = threading.Thread(target=lambda: other.append(etsy.http_opener()))
            worker.start()
            worker.join()
            self.assertIs(main, etsy.http_opener())
            self.assertIsNot(main, other[0])
            self.assertEqual(factory.call_count, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)

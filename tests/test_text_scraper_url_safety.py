import socket
import unittest
from unittest.mock import patch

import text_scraper
from text_scraper import TextScraper
from test_text_scraper_transport import (
    SyntheticResponse,
    SyntheticResponseContext,
)


PUBLIC_GETADDRINFO = [
    (
        socket.AF_INET,
        socket.SOCK_STREAM,
        6,
        "",
        ("93.184.216.34", 443),
    )
]


class TextScraperUrlSafetyTests(unittest.TestCase):
    def setUp(self):
        self.node = TextScraper()

    def test_scheme_less_url_normalizes_to_https(self):
        with patch("text_scraper.socket.getaddrinfo", return_value=PUBLIC_GETADDRINFO):
            url, error = self.node.normalize_and_validate_url("example.com/news")

        self.assertIsNone(error)
        self.assertEqual("https://example.com/news", url)

    def test_blocks_non_http_scheme(self):
        url, error = self.node.normalize_and_validate_url("file:///etc/passwd")

        self.assertIsNone(url)
        self.assertEqual("Blocked URL: only http and https URLs are allowed.", error)

    def test_blocks_loopback_before_http_request(self):
        with patch("text_scraper._open_pinned_response") as open_response:
            output, = self.node.scrape_news("http://127.0.0.1:8188", seed=1)

        open_response.assert_not_called()
        self.assertEqual("Blocked URL: private or local network addresses are not allowed.", output)

    def test_blocks_hostname_that_resolves_to_private_address(self):
        private_addr = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("192.168.1.10", 443),
            )
        ]
        with patch("text_scraper.socket.getaddrinfo", return_value=private_addr):
            url, error = self.node.normalize_and_validate_url("https://example.test")

        self.assertIsNone(url)
        self.assertEqual("Blocked URL: private or local network addresses are not allowed.", error)

    def test_safe_public_url_uses_bounded_pinned_transport(self):
        response = SyntheticResponse(
            chunks=[b"<html><h1>Example headline long enough</h1></html>"],
        )

        with patch("text_scraper.socket.getaddrinfo", return_value=PUBLIC_GETADDRINFO):
            with patch(
                "text_scraper._open_pinned_response",
                return_value=SyntheticResponseContext(response),
            ) as open_response:
                output, = self.node.scrape_news("https://example.com", seed=2)

        open_response.assert_called_once()
        target = open_response.call_args.args[0]
        self.assertEqual("example.com", target.hostname)
        self.assertEqual("93.184.216.34", target.address)
        self.assertTrue(response.closed)
        self.assertIn("Example headline long enough", output)

    def test_stable_errors_do_not_include_workflow_url_or_raw_exception(self):
        with patch(
            "text_scraper.socket.getaddrinfo",
            side_effect=OSError("DNS_SECRET_CANARY"),
        ):
            output, = self.node.scrape_news(
                "https://example.test/private?token=URL_SECRET_CANARY",
                seed=3,
            )

        self.assertEqual(text_scraper.ERROR_RESOLUTION, output)
        self.assertNotIn("CANARY", output)
        self.assertNotIn("example.test", output)


if __name__ == "__main__":
    unittest.main()

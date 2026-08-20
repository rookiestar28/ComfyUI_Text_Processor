import contextlib
import io
from pathlib import Path
import unittest

import text_scraper
from text_scraper import TextScraper


class TextScraperDisabledCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.node = TextScraper()

    def test_public_schema_and_registration_surface_remain_exact(self):
        schema = TextScraper.INPUT_TYPES()
        self.assertEqual(["url", "seed"], list(schema["required"]))
        self.assertEqual("STRING", schema["required"]["url"][0])
        self.assertEqual(
            "https://news.ycombinator.com",
            schema["required"]["url"][1]["default"],
        )
        self.assertEqual("INT", schema["required"]["seed"][0])
        self.assertEqual(0, schema["required"]["seed"][1]["default"])
        self.assertEqual(("STRING",), TextScraper.RETURN_TYPES)
        self.assertEqual(("text",), TextScraper.RETURN_NAMES)
        self.assertEqual("scrape_news", TextScraper.FUNCTION)
        self.assertEqual("ComfyUI Text Processor", TextScraper.CATEGORY)

    def test_every_invocation_returns_static_disabled_message_without_echo(self):
        cases = (
            ("https://PUBLIC_URL_CANARY.invalid/path?secret=URL_CANARY", 123456),
            ("http://127.0.0.1/PRIVATE_CANARY", 0),
            ("not a url", -1),
            (None, object()),
        )
        for url, seed in cases:
            with self.subTest(
                url_type=type(url).__name__,
                seed_type=type(seed).__name__,
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = self.node.scrape_news(url, seed)
                self.assertEqual((text_scraper.TEXT_SCRAPER_DISABLED,), result)
                self.assertEqual("", output.getvalue())
                self.assertNotIn("CANARY", result[0])

    def test_compatibility_helpers_are_static_and_content_free(self):
        normalized, error = self.node.normalize_and_validate_url("PRIVATE_URL_CANARY")
        self.assertIsNone(normalized)
        self.assertEqual(text_scraper.TEXT_SCRAPER_DISABLED, error)
        self.assertEqual(
            [{"headline": text_scraper.TEXT_SCRAPER_DISABLED}],
            self.node.scrape_headlines("PRIVATE_URL_CANARY"),
        )

    def test_product_module_has_no_network_or_html_client_surface(self):
        source = Path(text_scraper.__file__).read_text(encoding="utf-8").lower()
        for forbidden in (
            "import requests",
            "from requests",
            "import socket",
            "from socket",
            "getaddrinfo",
            "urllib3",
            "urlopen(",
            "beautifulsoup",
            "from bs4",
            "requests.",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()

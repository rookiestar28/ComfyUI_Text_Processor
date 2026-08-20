import builtins
import contextlib
import io
import os
import socket
import subprocess
import unittest
from unittest import mock
import urllib.request

import text_scraper
from text_scraper import TextScraper


class TextScraperCapabilityRetirementTests(unittest.TestCase):
    def test_execution_opens_no_network_process_file_or_environment_boundary(self):
        node = TextScraper()
        output = io.StringIO()
        with (
            mock.patch.object(
                socket,
                "getaddrinfo",
                side_effect=AssertionError("dns opened"),
            ),
            mock.patch.object(
                socket,
                "create_connection",
                side_effect=AssertionError("socket opened"),
            ),
            mock.patch.object(
                urllib.request,
                "urlopen",
                side_effect=AssertionError("url opened"),
            ),
            mock.patch.object(
                subprocess,
                "run",
                side_effect=AssertionError("process opened"),
            ),
            mock.patch.object(
                subprocess,
                "Popen",
                side_effect=AssertionError("process opened"),
            ),
            mock.patch.object(
                builtins,
                "open",
                side_effect=AssertionError("file opened"),
            ),
            mock.patch.object(
                os,
                "getenv",
                side_effect=AssertionError("environment read"),
            ),
            mock.patch.object(
                os.environ,
                "get",
                side_effect=AssertionError("environment read"),
            ),
            contextlib.redirect_stdout(output),
        ):
            result = node.scrape_news("https://PRIVATE_CANARY.invalid", 99)
        self.assertEqual((text_scraper.TEXT_SCRAPER_DISABLED,), result)
        self.assertEqual("", output.getvalue())

    def test_repeated_calls_are_deterministic_and_retain_no_instance_state(self):
        node = TextScraper()
        expected = (text_scraper.TEXT_SCRAPER_DISABLED,)
        for index in range(100):
            self.assertEqual(expected, node.scrape_news(f"input-{index}", index))
        self.assertEqual({}, vars(node))

    def test_disabled_message_and_help_are_explicit(self):
        self.assertEqual(
            "Text Scraper is disabled because remote network access is not available in this node pack.",
            text_scraper.TEXT_SCRAPER_DISABLED,
        )
        self.assertIn("disabled", TextScraper.DESCRIPTION.lower())
        self.assertIn("disabled", TextScraper.OUTPUT_TOOLTIPS[0].lower())


if __name__ == "__main__":
    unittest.main()

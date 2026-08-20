from __future__ import annotations

from typing import Any


TEXT_SCRAPER_DISABLED = (
    "Text Scraper is disabled because remote network access is not available in this "
    "node pack."
)


class TextScraper:
    """Compatibility node retained so existing workflows remain loadable."""

    def __init__(self) -> None:
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": (
                    "STRING",
                    {
                        "default": "https://news.ycombinator.com",
                        "multiline": False,
                        "tooltip": (
                            "Retained for workflow compatibility; remote fetching is "
                            "disabled."
                        ),
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "tooltip": (
                            "Retained for workflow compatibility; this value has no "
                            "effect while the node is disabled."
                        ),
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "scrape_news"
    CATEGORY = "ComfyUI Text Processor"
    DESCRIPTION = (
        "Compatibility placeholder for existing Text Scraper workflows; remote "
        "fetching is disabled."
    )
    SEARCH_ALIASES = ["text scraper disabled", "scraper compatibility"]
    OUTPUT_TOOLTIPS = ("Static message explaining that remote fetching is disabled.",)

    def normalize_and_validate_url(self, url: Any):
        del url
        return None, TEXT_SCRAPER_DISABLED

    def scrape_headlines(self, url: Any):
        del url
        return [{"headline": TEXT_SCRAPER_DISABLED}]

    def scrape_news(self, url: Any, seed: Any):
        # IMPORTANT: do not restore network access without Registry and security review.
        del url, seed
        return (TEXT_SCRAPER_DISABLED,)

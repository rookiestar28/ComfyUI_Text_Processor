from __future__ import annotations

import ipaddress
import socket
import time
from contextlib import contextmanager
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread
from typing import (
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    cast,
)
from urllib.parse import urljoin, urlsplit, urlunsplit


# CRITICAL: keep imports fail-closed so the package can report missing node dependencies.
try:
    import requests
    from bs4 import BeautifulSoup
    from requests.adapters import HTTPAdapter
    from urllib3 import HTTPConnectionPool, HTTPSConnectionPool
except ImportError:
    requests = None
    BeautifulSoup = None
    HTTPAdapter = object
    HTTPConnectionPool = None
    HTTPSConnectionPool = None


BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}
ALLOWED_MEDIA_TYPES = {
    "application/xhtml+xml",
    "text/html",
    "text/plain",
}
REDIRECT_STATUSES = {301, 302, 303, 307, 308}

MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 1_048_576
STREAM_CHUNK_BYTES = 64 * 1024
CONNECT_TIMEOUT_SECONDS = 3.05
READ_TIMEOUT_SECONDS = 5.0
TOTAL_TIMEOUT_SECONDS = 10.0

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)

ERROR_INVALID_URL = "Please enter a valid URL."
ERROR_SCHEME = "Blocked URL: only http and https URLs are allowed."
ERROR_CREDENTIALS = "Blocked URL: credentials are not allowed."
ERROR_FRAGMENT = "Blocked URL: URL fragments are not allowed."
ERROR_PORT = "Blocked URL: only standard http and https ports are allowed."
ERROR_PRIVATE_ADDRESS = (
    "Blocked URL: private or local network addresses are not allowed."
)
ERROR_RESOLUTION = "URL validation error: hostname resolution failed."
ERROR_REDIRECT = "Network Error: redirect was rejected."
ERROR_REDIRECT_LIMIT = "Network Error: redirect limit exceeded."
ERROR_TIMEOUT = "Network Error: request timed out."
ERROR_REQUEST = "Network Error: request failed."
ERROR_STATUS = "Network Error: response status was not successful."
ERROR_MEDIA_TYPE = "Network Error: response content type is not supported."
ERROR_BODY_TOO_LARGE = "Network Error: response body is too large."
ERROR_PARSE = "Scraping Error: response could not be parsed."
ERROR_DEPENDENCIES = (
    "Error: Please install 'requests' and 'beautifulsoup4' in your Python environment."
)
ERROR_NO_HEADLINES = (
    "No headlines found. The site might use JavaScript rendering (SPA) or block bots."
)


class _TransportError(Exception):
    def __init__(self, public_message: str):
        super().__init__(public_message)
        self.public_message = public_message


_DeadlineResult = TypeVar("_DeadlineResult")


def _run_before_deadline(
    operation: Callable[[], _DeadlineResult],
    deadline: float,
) -> _DeadlineResult:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _TransportError(ERROR_TIMEOUT)

    results: Queue[Tuple[bool, object]] = Queue(maxsize=1)

    def invoke() -> None:
        try:
            outcome: Tuple[bool, object] = (True, operation())
        except Exception as error:
            outcome = (False, error)
        results.put_nowait(outcome)

    # CRITICAL: blocking DNS/body work must not extend the caller past its deadline.
    worker = Thread(target=invoke, name="text-scraper-deadline", daemon=True)
    worker.start()
    try:
        succeeded, value = results.get(timeout=remaining)
    except Empty:
        raise _TransportError(ERROR_TIMEOUT) from None

    if not succeeded:
        if isinstance(value, Exception):
            raise value
        raise _TransportError(ERROR_REQUEST)
    return cast(_DeadlineResult, value)


@dataclass(frozen=True)
class _ValidatedTarget:
    url: str
    scheme: str
    hostname: str
    host_header: str
    address: str
    addresses: Tuple[str, ...]
    port: int


def _contains_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


class _PinnedAddressAdapter(HTTPAdapter):
    """Bind Requests to one validated IP without changing HTTP or TLS hostname identity."""

    def __init__(self, target: _ValidatedTarget):
        if requests is None or HTTPConnectionPool is None or HTTPSConnectionPool is None:
            raise _TransportError(ERROR_DEPENDENCIES)
        super().__init__(max_retries=0)
        self._target = target
        self._pinned_pool = None

    def _get_pinned_pool(self):
        if self._pinned_pool is None:
            if self._target.scheme == "https":
                self._pinned_pool = HTTPSConnectionPool(
                    self._target.address,
                    self._target.port,
                    maxsize=1,
                    block=True,
                    retries=False,
                    assert_hostname=self._target.hostname,
                    server_hostname=self._target.hostname,
                )
            else:
                self._pinned_pool = HTTPConnectionPool(
                    self._target.address,
                    self._target.port,
                    maxsize=1,
                    block=True,
                    retries=False,
                )
        return self._pinned_pool

    @staticmethod
    def _reject_proxy(proxies: Optional[Mapping[str, str]]) -> None:
        if proxies:
            # CRITICAL: a proxy would invalidate the validated destination binding.
            raise requests.exceptions.ProxyError("proxy use is disabled")

    def get_connection_with_tls_context(
        self,
        request,
        verify,
        proxies=None,
        cert=None,
    ):
        self._reject_proxy(proxies)
        return self._get_pinned_pool()

    def get_connection(self, url, proxies=None):
        self._reject_proxy(proxies)
        return self._get_pinned_pool()

    def close(self):
        if self._pinned_pool is not None:
            self._pinned_pool.close()
            self._pinned_pool = None
        super().close()


@contextmanager
def _open_pinned_response(
    target: _ValidatedTarget,
    timeout: Tuple[float, float],
) -> Iterator:
    if requests is None:
        raise _TransportError(ERROR_DEPENDENCIES)

    session = requests.Session()
    response = None
    try:
        adapter = _PinnedAddressAdapter(target)
        # CRITICAL: environment proxies must never bypass the validated IP connector.
        session.trust_env = False
        session.mount(f"{target.scheme}://", adapter)
        response = session.get(
            target.url,
            allow_redirects=False,
            stream=True,
            timeout=timeout,
            verify=True,
            proxies={},
            headers={
                "Host": target.host_header,
                "User-Agent": USER_AGENT,
            },
        )
        yield response
    finally:
        if response is not None:
            response.close()
        session.close()


class TextScraper:
    """A ComfyUI node that extracts headline-like text from a bounded public URL."""

    def __init__(self):
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
                            "Public HTTP or HTTPS page to fetch; local and private "
                            "destinations are blocked."
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
                            "Change this value to force a fresh fetch when the URL "
                            "is unchanged."
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
        "Fetches headline-like text from public HTTP or HTTPS pages with "
        "local/private address blocking."
    )
    SEARCH_ALIASES = [
        "web scraper",
        "text scraper",
        "headlines",
        "fetch url",
        "news scraper",
    ]
    OUTPUT_TOOLTIPS = (
        "Scraped headline text or a clear validation/network error message.",
    )

    def _resolve_target(
        self,
        url: str,
        deadline: Optional[float] = None,
    ) -> _ValidatedTarget:
        if not isinstance(url, str):
            raise _TransportError(ERROR_INVALID_URL)

        candidate = url.strip()
        if not candidate:
            raise _TransportError(ERROR_INVALID_URL)
        if _contains_control_character(candidate):
            raise _TransportError(ERROR_INVALID_URL)

        if "://" not in candidate:
            candidate = "https://" + candidate

        try:
            parsed = urlsplit(candidate)
            scheme = parsed.scheme.lower()
            if scheme not in {"http", "https"}:
                raise _TransportError(ERROR_SCHEME)
            if not parsed.netloc or "\\" in parsed.netloc:
                raise _TransportError(ERROR_INVALID_URL)
            if parsed.username is not None or parsed.password is not None:
                raise _TransportError(ERROR_CREDENTIALS)
            if parsed.fragment:
                raise _TransportError(ERROR_FRAGMENT)
            hostname_value = parsed.hostname
            if not hostname_value:
                raise _TransportError(ERROR_INVALID_URL)
        except _TransportError:
            raise
        except ValueError:
            raise _TransportError(ERROR_INVALID_URL) from None

        hostname_value = hostname_value.rstrip(".").lower()
        if not hostname_value:
            raise _TransportError(ERROR_INVALID_URL)

        zone_free_hostname = hostname_value.split("%", 1)[0]
        literal_ip = None
        try:
            literal_ip = ipaddress.ip_address(zone_free_hostname)
        except ValueError:
            pass

        if literal_ip is not None and not literal_ip.is_global:
            raise _TransportError(ERROR_PRIVATE_ADDRESS)
        if literal_ip is not None and "%" in hostname_value:
            raise _TransportError(ERROR_PRIVATE_ADDRESS)

        authority = parsed.netloc.rsplit("@", 1)[-1]
        if authority.endswith(":"):
            raise _TransportError(ERROR_PORT)
        try:
            explicit_port = parsed.port
        except ValueError:
            raise _TransportError(ERROR_PORT) from None
        default_port = 443 if scheme == "https" else 80
        port = explicit_port if explicit_port is not None else default_port
        if port != default_port:
            raise _TransportError(ERROR_PORT)

        if literal_ip is not None:
            hostname = literal_ip.compressed
            addresses = (hostname,)
        else:
            try:
                hostname = hostname_value.encode("idna").decode("ascii").lower()
            except UnicodeError:
                raise _TransportError(ERROR_INVALID_URL) from None
            if hostname in BLOCKED_HOSTNAMES:
                raise _TransportError(ERROR_PRIVATE_ADDRESS)

            def resolve_addresses():
                return socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)

            try:
                resolved = (
                    resolve_addresses()
                    if deadline is None
                    else _run_before_deadline(resolve_addresses, deadline)
                )
            except (OSError, ValueError):
                raise _TransportError(ERROR_RESOLUTION) from None

            parsed_addresses = {}
            for entry in resolved:
                try:
                    resolved_ip = ipaddress.ip_address(entry[4][0].split("%", 1)[0])
                except (IndexError, TypeError, ValueError):
                    raise _TransportError(ERROR_RESOLUTION) from None
                if not resolved_ip.is_global:
                    raise _TransportError(ERROR_PRIVATE_ADDRESS)
                parsed_addresses[(resolved_ip.version, int(resolved_ip))] = (
                    resolved_ip.compressed
                )

            if not parsed_addresses:
                raise _TransportError(ERROR_RESOLUTION)
            addresses = tuple(
                parsed_addresses[key] for key in sorted(parsed_addresses)
            )

        host_header = f"[{hostname}]" if ":" in hostname else hostname
        canonical_url = urlunsplit(
            (
                scheme,
                host_header,
                parsed.path,
                parsed.query,
                "",
            )
        )
        return _ValidatedTarget(
            url=canonical_url,
            scheme=scheme,
            hostname=hostname,
            host_header=host_header,
            address=addresses[0],
            addresses=addresses,
            port=port,
        )

    def normalize_and_validate_url(self, url: str):
        try:
            target = self._resolve_target(url)
        except _TransportError as error:
            return None, error.public_message
        return target.url, None

    @staticmethod
    def _bounded_response_text(response, deadline: float) -> str:
        content_type = response.headers.get("Content-Type")
        if not isinstance(content_type, str):
            raise _TransportError(ERROR_MEDIA_TYPE)
        media_type = content_type.split(";", 1)[0].strip().lower()
        if not media_type or media_type not in ALLOWED_MEDIA_TYPES:
            raise _TransportError(ERROR_MEDIA_TYPE)

        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            value = str(content_length).strip()
            if not value.isdecimal():
                raise _TransportError(ERROR_REQUEST)
            if int(value) > MAX_RESPONSE_BYTES:
                raise _TransportError(ERROR_BODY_TOO_LARGE)

        def consume_body() -> bytes:
            content = bytearray()
            for chunk in response.iter_content(
                chunk_size=STREAM_CHUNK_BYTES,
                decode_unicode=False,
            ):
                if not isinstance(chunk, (bytes, bytearray)):
                    raise _TransportError(ERROR_REQUEST)
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise _TransportError(ERROR_BODY_TOO_LARGE)
            return bytes(content)

        content = _run_before_deadline(consume_body, deadline)
        if time.monotonic() >= deadline:
            raise _TransportError(ERROR_TIMEOUT)

        encoding = response.encoding or "utf-8"
        try:
            return content.decode(encoding, errors="replace")
        except (LookupError, TypeError):
            raise _TransportError(ERROR_PARSE) from None

    def _fetch_text(self, url: str) -> str:
        if requests is None:
            raise _TransportError(ERROR_DEPENDENCIES)

        deadline = time.monotonic() + TOTAL_TIMEOUT_SECONDS
        current_url = url
        seen_urls = set()
        redirect_count = 0

        while True:
            target = self._resolve_target(current_url, deadline=deadline)
            if target.url in seen_urls:
                raise _TransportError(ERROR_REDIRECT)
            seen_urls.add(target.url)

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _TransportError(ERROR_TIMEOUT)
            timeout = (
                min(CONNECT_TIMEOUT_SECONDS, remaining),
                min(READ_TIMEOUT_SECONDS, remaining),
            )

            try:
                with _open_pinned_response(target, timeout) as response:
                    status = response.status_code
                    if status in REDIRECT_STATUSES:
                        if redirect_count >= MAX_REDIRECTS:
                            raise _TransportError(ERROR_REDIRECT_LIMIT)
                        raw_headers = getattr(
                            getattr(response, "raw", None),
                            "headers",
                            None,
                        )
                        getlist = getattr(raw_headers, "getlist", None)
                        if callable(getlist):
                            locations = list(getlist("Location"))
                        else:
                            location_value = response.headers.get("Location")
                            locations = [] if location_value is None else [location_value]
                        if (
                            len(locations) != 1
                            or not isinstance(locations[0], str)
                            or not locations[0].strip()
                        ):
                            raise _TransportError(ERROR_REDIRECT)
                        try:
                            next_url = urljoin(target.url, locations[0].strip())
                            next_scheme = urlsplit(next_url).scheme.lower()
                        except (TypeError, ValueError):
                            raise _TransportError(ERROR_REDIRECT) from None
                        if target.scheme == "https" and next_scheme == "http":
                            raise _TransportError(ERROR_REDIRECT)
                        redirect_count += 1
                        current_url = next_url
                        continue

                    if not 200 <= status < 300:
                        raise _TransportError(ERROR_STATUS)
                    return self._bounded_response_text(response, deadline)
            except _TransportError:
                raise
            except requests.exceptions.Timeout:
                raise _TransportError(ERROR_TIMEOUT) from None
            except requests.exceptions.RequestException:
                raise _TransportError(ERROR_REQUEST) from None
            except Exception:
                raise _TransportError(ERROR_REQUEST) from None

    @staticmethod
    def _extract_headlines(response_text: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(response_text, "html.parser")

        headline_tags = soup.find_all(["h1", "h2", "h3"])
        keywords = [
            "title",
            "headline",
            "heading",
            "story-link",
            "article-title",
        ]
        headline_classes = soup.find_all(
            class_=lambda value: value
            and any(keyword in str(value).lower() for keyword in keywords)
        )
        article_titles = soup.find_all(
            "a",
            class_=lambda value: value
            and any(keyword in str(value).lower() for keyword in keywords),
        )
        candidates = headline_tags + headline_classes + article_titles

        results = []
        seen_headlines = set()
        for tag in candidates:
            text = " ".join(tag.get_text().strip().split())
            if not text or len(text) < 15 or text in seen_headlines:
                continue
            seen_headlines.add(text)
            results.append({"headline": text})
            if len(results) >= 15:
                break
        return results

    def scrape_headlines(self, url: str) -> List[Dict[str, str]]:
        if requests is None or BeautifulSoup is None:
            return [{"headline": ERROR_DEPENDENCIES}]

        try:
            return self._extract_headlines(self._fetch_text(url))
        except _TransportError as error:
            return [{"headline": error.public_message}]
        except Exception:
            return [{"headline": ERROR_PARSE}]

    def scrape_news(self, url: str, seed: int):
        del seed
        if requests is None or BeautifulSoup is None:
            return (ERROR_DEPENDENCIES,)
        try:
            headlines = self._extract_headlines(self._fetch_text(url))
        except _TransportError as error:
            return (error.public_message,)
        except Exception:
            return (ERROR_PARSE,)
        if not headlines:
            return (ERROR_NO_HEADLINES,)
        return ("".join(f"{item['headline']}\n" for item in headlines),)

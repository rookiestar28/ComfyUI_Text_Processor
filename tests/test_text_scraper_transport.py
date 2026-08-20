import contextlib
import io
import socket
import threading
import time
import unittest
from unittest.mock import Mock, patch

import requests

import text_scraper


PUBLIC_V4 = "93.184.216.34"
PUBLIC_V4_SECOND = "8.8.8.8"
PUBLIC_V6 = "2606:4700:4700::1111"


def getaddrinfo_for(*addresses, port=443):
    entries = []
    for address in addresses:
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
        entries.append((family, socket.SOCK_STREAM, 6, "", sockaddr))
    return entries


class SyntheticResponse:
    def __init__(
        self,
        *,
        status=200,
        headers=None,
        chunks=None,
        encoding="utf-8",
    ):
        self.status_code = status
        self.headers = dict(
            {"Content-Type": "text/html; charset=utf-8"}
            if headers is None
            else headers
        )
        self.encoding = encoding
        self._chunks = list(chunks or [b"<h1>Synthetic headline long enough</h1>"])
        self.closed = False
        self.iter_calls = []

    def iter_content(self, chunk_size=1, decode_unicode=False):
        self.iter_calls.append((chunk_size, decode_unicode))
        for chunk in self._chunks:
            if isinstance(chunk, BaseException):
                raise chunk
            yield chunk

    def close(self):
        self.closed = True


class SyntheticResponseContext:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self.response

    def __exit__(self, exc_type, exc, traceback):
        self.response.close()
        return False


class TextScraperTargetValidationTests(unittest.TestCase):
    def setUp(self):
        self.node = text_scraper.TextScraper()

    def resolve(self, url, answers=(PUBLIC_V4,)):
        with patch(
            "text_scraper.socket.getaddrinfo",
            return_value=getaddrinfo_for(*answers),
        ) as resolver:
            target = self.node._resolve_target(url)
        return target, resolver

    def assert_transport_error(self, expected, url, answers=(PUBLIC_V4,)):
        with patch(
            "text_scraper.socket.getaddrinfo",
            return_value=getaddrinfo_for(*answers),
        ):
            with self.assertRaises(text_scraper._TransportError) as raised:
                self.node._resolve_target(url)
        self.assertEqual(expected, raised.exception.public_message)

    def test_scheme_less_url_is_canonical_https_and_pinned(self):
        target, resolver = self.resolve("Example.Test./news?q=1")

        self.assertEqual("https://example.test/news?q=1", target.url)
        self.assertEqual("https", target.scheme)
        self.assertEqual("example.test", target.hostname)
        self.assertEqual("example.test", target.host_header)
        self.assertEqual(PUBLIC_V4, target.address)
        self.assertEqual(443, target.port)
        resolver.assert_called_once_with(
            "example.test",
            443,
            type=socket.SOCK_STREAM,
        )

    def test_idna_hostname_is_ascii_for_dns_host_and_tls_identity(self):
        target, resolver = self.resolve("https://bücher.example/path")

        self.assertEqual("xn--bcher-kva.example", target.hostname)
        self.assertEqual("xn--bcher-kva.example", target.host_header)
        self.assertIn("xn--bcher-kva.example", target.url)
        resolver.assert_called_once_with(
            "xn--bcher-kva.example",
            443,
            type=socket.SOCK_STREAM,
        )

    def test_explicit_standard_ports_are_accepted_and_canonicalized_away(self):
        https_target, _ = self.resolve("https://example.test:443/a")
        http_target, _ = self.resolve(
            "http://example.test:80/b",
            answers=(PUBLIC_V4,),
        )

        self.assertEqual("https://example.test/a", https_target.url)
        self.assertEqual("http://example.test/b", http_target.url)
        self.assertEqual(443, https_target.port)
        self.assertEqual(80, http_target.port)

    def test_public_literal_ipv4_does_not_use_dns(self):
        with patch("text_scraper.socket.getaddrinfo") as resolver:
            target = self.node._resolve_target(f"https://{PUBLIC_V4}/a")

        resolver.assert_not_called()
        self.assertEqual(PUBLIC_V4, target.address)
        self.assertEqual(PUBLIC_V4, target.hostname)
        self.assertEqual(PUBLIC_V4, target.host_header)

    def test_public_literal_ipv6_is_bracketed_and_does_not_use_dns(self):
        with patch("text_scraper.socket.getaddrinfo") as resolver:
            target = self.node._resolve_target(f"https://[{PUBLIC_V6}]/a")

        resolver.assert_not_called()
        self.assertEqual(PUBLIC_V6, target.address)
        self.assertEqual(PUBLIC_V6, target.hostname)
        self.assertEqual(f"[{PUBLIC_V6}]", target.host_header)
        self.assertEqual(f"https://[{PUBLIC_V6}]/a", target.url)

    def test_all_dns_answers_must_be_global(self):
        self.assert_transport_error(
            text_scraper.ERROR_PRIVATE_ADDRESS,
            "https://example.test",
            answers=(PUBLIC_V4, "192.168.1.10"),
        )

    def test_dns_selection_is_deduplicated_and_deterministic(self):
        target, _ = self.resolve(
            "https://example.test",
            answers=(PUBLIC_V6, PUBLIC_V4, PUBLIC_V4_SECOND, PUBLIC_V4),
        )

        self.assertEqual(PUBLIC_V4_SECOND, target.address)
        self.assertEqual((PUBLIC_V4_SECOND, PUBLIC_V4, PUBLIC_V6), target.addresses)

    def test_dns_empty_malformed_and_exception_are_content_free(self):
        for answer in ([], getaddrinfo_for("not-an-ip")):
            with self.subTest(answer=answer):
                with patch("text_scraper.socket.getaddrinfo", return_value=answer):
                    with self.assertRaises(text_scraper._TransportError) as raised:
                        self.node._resolve_target("https://example.test/private-query")
                self.assertEqual(
                    text_scraper.ERROR_RESOLUTION,
                    raised.exception.public_message,
                )

        with patch(
            "text_scraper.socket.getaddrinfo",
            side_effect=OSError("DNS_SECRET_CANARY"),
        ):
            with self.assertRaises(text_scraper._TransportError) as raised:
                self.node._resolve_target("https://example.test/private-query")
        self.assertEqual(text_scraper.ERROR_RESOLUTION, raised.exception.public_message)
        self.assertNotIn("CANARY", raised.exception.public_message)

    def test_invalid_authority_and_policy_inputs_fail_before_dns(self):
        cases = (
            ("", text_scraper.ERROR_INVALID_URL),
            ("file:///etc/passwd", text_scraper.ERROR_SCHEME),
            ("https://user@example.test/a", text_scraper.ERROR_CREDENTIALS),
            ("https://example.test/a#frag", text_scraper.ERROR_FRAGMENT),
            ("https://example.test:/a", text_scraper.ERROR_PORT),
            ("http://example.test:/a", text_scraper.ERROR_PORT),
            (f"https://[{PUBLIC_V6}]:/a", text_scraper.ERROR_PORT),
            ("https://example.test:444/a", text_scraper.ERROR_PORT),
            ("http://example.test:443/a", text_scraper.ERROR_PORT),
            ("https://example.test\\@evil.test/a", text_scraper.ERROR_INVALID_URL),
            ("https://example.test/\x00a", text_scraper.ERROR_INVALID_URL),
            ("https://[fe80::1%25eth0]/", text_scraper.ERROR_PRIVATE_ADDRESS),
        )
        for url, expected in cases:
            with self.subTest(url=url):
                with patch("text_scraper.socket.getaddrinfo") as resolver:
                    with self.assertRaises(text_scraper._TransportError) as raised:
                        self.node._resolve_target(url)
                resolver.assert_not_called()
                self.assertEqual(expected, raised.exception.public_message)

    def test_loopback_with_nonstandard_port_keeps_private_address_diagnostic(self):
        with patch("text_scraper.socket.getaddrinfo") as resolver:
            with self.assertRaises(text_scraper._TransportError) as raised:
                self.node._resolve_target("http://127.0.0.1:8188")

        resolver.assert_not_called()
        self.assertEqual(
            text_scraper.ERROR_PRIVATE_ADDRESS,
            raised.exception.public_message,
        )


class TextScraperPinnedConnectorTests(unittest.TestCase):
    def target(self, scheme="https", address=PUBLIC_V4, hostname="example.test"):
        host_header = f"[{hostname}]" if ":" in hostname else hostname
        return text_scraper._ValidatedTarget(
            url=f"{scheme}://{host_header}/path",
            scheme=scheme,
            hostname=hostname,
            host_header=host_header,
            address=address,
            addresses=(address,),
            port=443 if scheme == "https" else 80,
        )

    def test_https_pool_connects_to_ip_and_preserves_tls_hostname(self):
        target = self.target()
        adapter = text_scraper._PinnedAddressAdapter(target)

        pool = adapter.get_connection_with_tls_context(
            Mock(),
            True,
            proxies={},
            cert=None,
        )
        adapter.cert_verify(pool, target.url, True, None)
        connection = pool._new_conn()

        self.assertEqual(PUBLIC_V4, pool.host)
        self.assertEqual(443, pool.port)
        self.assertEqual("example.test", pool.assert_hostname)
        self.assertEqual("example.test", pool.conn_kw["server_hostname"])
        self.assertEqual(PUBLIC_V4, connection._dns_host)
        self.assertEqual("example.test", connection.server_hostname)
        self.assertEqual("example.test", connection.assert_hostname)
        self.assertEqual("CERT_REQUIRED", pool.cert_reqs)
        self.assertTrue(pool.ca_certs)

    def test_tcp_connector_receives_only_the_validated_ip(self):
        adapter = text_scraper._PinnedAddressAdapter(self.target())
        connection = adapter._get_pinned_pool()._new_conn()
        fake_socket = Mock()

        with patch(
            "urllib3.connection.connection.create_connection",
            return_value=fake_socket,
        ) as create_connection:
            opened_socket = connection._new_conn()

        self.assertIs(fake_socket, opened_socket)
        self.assertEqual(
            (PUBLIC_V4, 443),
            create_connection.call_args.args[0],
        )
        self.assertNotIn(
            "example.test",
            repr(create_connection.call_args),
        )

    def test_http_pool_connects_to_ip_without_tls_options(self):
        target = self.target(scheme="http")
        adapter = text_scraper._PinnedAddressAdapter(target)

        pool = adapter.get_connection_with_tls_context(
            Mock(),
            True,
            proxies={},
            cert=None,
        )
        connection = pool._new_conn()

        self.assertEqual(PUBLIC_V4, pool.host)
        self.assertEqual(80, pool.port)
        self.assertEqual(PUBLIC_V4, connection._dns_host)
        self.assertNotIn("server_hostname", pool.conn_kw)

    def test_current_and_legacy_hooks_return_the_same_pinned_pool(self):
        target = self.target()
        adapter = text_scraper._PinnedAddressAdapter(target)

        current = adapter.get_connection_with_tls_context(
            Mock(),
            True,
            proxies={},
            cert=None,
        )
        legacy = adapter.get_connection(target.url, proxies={})

        self.assertIs(current, legacy)
        self.assertEqual(PUBLIC_V4, legacy.host)

    def test_any_explicit_proxy_map_fails_closed(self):
        target = self.target()
        adapter = text_scraper._PinnedAddressAdapter(target)

        with self.assertRaises(requests.exceptions.ProxyError):
            adapter.get_connection_with_tls_context(
                Mock(),
                True,
                proxies={"https": "http://proxy.invalid"},
                cert=None,
            )
        with self.assertRaises(requests.exceptions.ProxyError):
            adapter.get_connection(target.url, proxies={"https": "http://proxy.invalid"})

    def test_adapter_close_closes_custom_pool(self):
        adapter = text_scraper._PinnedAddressAdapter(self.target())
        pool = adapter.get_connection_with_tls_context(
            Mock(),
            True,
            proxies={},
            cert=None,
        )
        pool.close = Mock(wraps=pool.close)

        adapter.close()

        pool.close.assert_called_once_with()

    def test_open_boundary_disables_environment_redirects_retries_and_preload(self):
        target = self.target()
        response = SyntheticResponse()
        captured = {}

        def fake_get(session, url, **kwargs):
            captured["session"] = session
            captured["url"] = url
            captured["kwargs"] = kwargs
            captured["adapter"] = session.get_adapter(url)
            return response

        with patch.object(requests.Session, "get", autospec=True, side_effect=fake_get):
            with text_scraper._open_pinned_response(target, (2.0, 3.0)) as opened:
                self.assertIs(response, opened)
                self.assertFalse(response.closed)

        self.assertTrue(response.closed)
        self.assertFalse(captured["session"].trust_env)
        self.assertEqual(target.url, captured["url"])
        self.assertIsInstance(captured["adapter"], text_scraper._PinnedAddressAdapter)
        self.assertEqual(0, captured["adapter"].max_retries.total)
        self.assertEqual(
            {
                "allow_redirects": False,
                "stream": True,
                "timeout": (2.0, 3.0),
                "verify": True,
                "proxies": {},
                "headers": {
                    "Host": "example.test",
                    "User-Agent": text_scraper.USER_AGENT,
                },
            },
            captured["kwargs"],
        )

    def test_open_boundary_closes_session_when_adapter_creation_fails(self):
        target = self.target()
        with patch(
            "text_scraper._PinnedAddressAdapter",
            side_effect=RuntimeError("synthetic adapter failure"),
        ), patch.object(
            requests.Session,
            "close",
            autospec=True,
        ) as close_session:
            with self.assertRaises(RuntimeError):
                with text_scraper._open_pinned_response(target, (2.0, 3.0)):
                    self.fail("the response context must not yield")

        close_session.assert_called_once()


class TextScraperBoundedTransportTests(unittest.TestCase):
    def setUp(self):
        self.node = text_scraper.TextScraper()

    def run_with_responses(self, url, responses, dns_answers=None, monotonic=None):
        contexts = [SyntheticResponseContext(response) for response in responses]
        dns_answers = dns_answers or {
            "first.test": (PUBLIC_V4,),
            "second.test": (PUBLIC_V4_SECOND,),
        }

        def resolve(host, port, type):
            self.assertEqual(socket.SOCK_STREAM, type)
            return getaddrinfo_for(*dns_answers[host], port=port)

        patches = [
            patch("text_scraper.socket.getaddrinfo", side_effect=resolve),
            patch("text_scraper._open_pinned_response", side_effect=contexts),
        ]
        if monotonic is not None:
            patches.append(patch("text_scraper.time.monotonic", side_effect=monotonic))

        with contextlib.ExitStack() as stack:
            resolver = stack.enter_context(patches[0])
            opener = stack.enter_context(patches[1])
            if len(patches) == 3:
                stack.enter_context(patches[2])
            text = self.node._fetch_text(url)
        return text, resolver, opener

    def assert_transport_failure(self, expected, response, **kwargs):
        with self.assertRaises(text_scraper._TransportError) as raised:
            self.run_with_responses("https://first.test/start", [response], **kwargs)
        self.assertEqual(expected, raised.exception.public_message)
        self.assertTrue(response.closed)

    def test_success_streams_decoded_bytes_at_exact_cap_and_closes(self):
        payload = b"A" * text_scraper.MAX_RESPONSE_BYTES
        response = SyntheticResponse(
            headers={"Content-Type": "text/plain; charset=utf-8"},
            chunks=[payload[:600_000], payload[600_000:]],
        )

        text, resolver, opener = self.run_with_responses(
            "https://first.test/start",
            [response],
        )

        self.assertEqual(text_scraper.MAX_RESPONSE_BYTES, len(text))
        self.assertEqual(
            [(text_scraper.STREAM_CHUNK_BYTES, False)],
            response.iter_calls,
        )
        self.assertTrue(response.closed)
        resolver.assert_called_once()
        self.assertEqual(PUBLIC_V4, opener.call_args.args[0].address)

    def test_declared_streamed_and_decoded_expansion_oversize_fail(self):
        declared = SyntheticResponse(
            headers={
                "Content-Type": "text/html",
                "Content-Length": str(text_scraper.MAX_RESPONSE_BYTES + 1),
            },
        )
        self.assert_transport_failure(text_scraper.ERROR_BODY_TOO_LARGE, declared)
        self.assertEqual([], declared.iter_calls)

        streamed = SyntheticResponse(
            chunks=[
                b"A" * text_scraper.MAX_RESPONSE_BYTES,
                b"B",
            ],
        )
        self.assert_transport_failure(text_scraper.ERROR_BODY_TOO_LARGE, streamed)

        compressed_expansion = SyntheticResponse(
            headers={
                "Content-Type": "text/html",
                "Content-Encoding": "gzip",
                "Content-Length": "128",
            },
            chunks=[b"C" * (text_scraper.MAX_RESPONSE_BYTES + 1)],
        )
        self.assert_transport_failure(
            text_scraper.ERROR_BODY_TOO_LARGE,
            compressed_expansion,
        )

    def test_media_type_allowlist_is_case_insensitive_and_parameter_aware(self):
        for media_type in (
            "text/html",
            "Text/Plain; charset=utf-8",
            "application/xhtml+xml; charset=UTF-8",
        ):
            with self.subTest(media_type=media_type):
                response = SyntheticResponse(headers={"Content-Type": media_type})
                text, _, _ = self.run_with_responses(
                    "https://first.test/start",
                    [response],
                )
                self.assertIn("Synthetic headline", text)
                self.assertTrue(response.closed)

    def test_missing_malformed_and_binary_media_types_fail_before_read(self):
        for headers in (
            {},
            {"Content-Type": "; charset=utf-8"},
            {"Content-Type": "application/octet-stream"},
            {"Content-Type": "image/svg+xml"},
        ):
            with self.subTest(headers=headers):
                response = SyntheticResponse(headers=headers)
                self.assert_transport_failure(text_scraper.ERROR_MEDIA_TYPE, response)
                self.assertEqual([], response.iter_calls)

    def test_malformed_or_negative_content_length_fails_closed(self):
        for value in ("-1", "not-a-number", "1, 2"):
            with self.subTest(value=value):
                response = SyntheticResponse(
                    headers={
                        "Content-Type": "text/plain",
                        "Content-Length": value,
                    }
                )
                self.assert_transport_failure(text_scraper.ERROR_REQUEST, response)
                self.assertEqual([], response.iter_calls)

    def test_unknown_charset_and_iterator_failure_are_static_and_closed(self):
        unknown_charset = SyntheticResponse(
            headers={"Content-Type": "text/plain"},
            encoding="SECRET-CANARY-CHARSET",
        )
        self.assert_transport_failure(text_scraper.ERROR_PARSE, unknown_charset)

        iterator_failure = SyntheticResponse(
            chunks=[requests.exceptions.ChunkedEncodingError("BODY_SECRET_CANARY")]
        )
        self.assert_transport_failure(text_scraper.ERROR_REQUEST, iterator_failure)

    def test_redirects_are_manual_per_hop_and_relative_location_is_resolved(self):
        first = SyntheticResponse(
            status=302,
            headers={"Location": "/next"},
            chunks=[],
        )
        second = SyntheticResponse(
            status=200,
            headers={"Content-Type": "text/html"},
        )

        text, resolver, opener = self.run_with_responses(
            "https://first.test/start",
            [first, second],
        )

        self.assertIn("Synthetic headline", text)
        self.assertTrue(first.closed)
        self.assertTrue(second.closed)
        self.assertEqual(2, resolver.call_count)
        self.assertEqual(2, opener.call_count)
        self.assertEqual(
            "https://first.test/next",
            opener.call_args_list[1].args[0].url,
        )

    def test_each_redirect_status_is_followed_under_policy(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                first = SyntheticResponse(
                    status=status,
                    headers={"Location": "https://second.test/final"},
                    chunks=[],
                )
                second = SyntheticResponse()
                text, _, opener = self.run_with_responses(
                    "https://first.test/start",
                    [first, second],
                )
                self.assertIn("Synthetic headline", text)
                self.assertEqual(PUBLIC_V4_SECOND, opener.call_args.args[0].address)
                self.assertTrue(first.closed)
                self.assertTrue(second.closed)

    def test_private_redirect_is_rejected_before_second_request(self):
        first = SyntheticResponse(
            status=302,
            headers={"Location": "https://127.0.0.1/private"},
            chunks=[],
        )
        with patch(
            "text_scraper.socket.getaddrinfo",
            return_value=getaddrinfo_for(PUBLIC_V4),
        ), patch(
            "text_scraper._open_pinned_response",
            return_value=SyntheticResponseContext(first),
        ) as opener:
            with self.assertRaises(text_scraper._TransportError) as raised:
                self.node._fetch_text("https://first.test/start")

        self.assertEqual(
            text_scraper.ERROR_PRIVATE_ADDRESS,
            raised.exception.public_message,
        )
        self.assertEqual(1, opener.call_count)
        self.assertTrue(first.closed)

    def test_redirect_downgrade_missing_location_loop_and_fourth_hop_fail(self):
        cases = (
            (
                [SyntheticResponse(status=302, headers={"Location": "http://second.test"})],
                text_scraper.ERROR_REDIRECT,
            ),
            (
                [SyntheticResponse(status=302, headers={})],
                text_scraper.ERROR_REDIRECT,
            ),
            (
                [SyntheticResponse(status=302, headers={"Location": "/start"})],
                text_scraper.ERROR_REDIRECT,
            ),
            (
                [
                    SyntheticResponse(status=302, headers={"Location": "/1"}),
                    SyntheticResponse(status=302, headers={"Location": "/2"}),
                    SyntheticResponse(status=302, headers={"Location": "/3"}),
                    SyntheticResponse(status=302, headers={"Location": "/4"}),
                ],
                text_scraper.ERROR_REDIRECT_LIMIT,
            ),
        )
        for responses, expected in cases:
            with self.subTest(expected=expected, count=len(responses)):
                with self.assertRaises(text_scraper._TransportError) as raised:
                    self.run_with_responses(
                        "https://first.test/start",
                        responses,
                    )
                self.assertEqual(expected, raised.exception.public_message)
                self.assertTrue(all(response.closed for response in responses))

    def test_duplicate_location_headers_fail_closed(self):
        response = SyntheticResponse(
            status=302,
            headers={"Location": "/fallback"},
            chunks=[],
        )
        response.raw = Mock()
        response.raw.headers = Mock()
        response.raw.headers.getlist.return_value = ["/one", "/two"]

        self.assert_transport_failure(text_scraper.ERROR_REDIRECT, response)

    def test_redirect_targets_reenter_full_url_and_dns_policy(self):
        cases = (
            (
                "https://user@second.test/path",
                text_scraper.ERROR_CREDENTIALS,
                {"first.test": (PUBLIC_V4,), "second.test": (PUBLIC_V4_SECOND,)},
            ),
            (
                "https://second.test/path#fragment",
                text_scraper.ERROR_FRAGMENT,
                {"first.test": (PUBLIC_V4,), "second.test": (PUBLIC_V4_SECOND,)},
            ),
            (
                "https://second.test:444/path",
                text_scraper.ERROR_PORT,
                {"first.test": (PUBLIC_V4,), "second.test": (PUBLIC_V4_SECOND,)},
            ),
            (
                "https://second.test:/path",
                text_scraper.ERROR_PORT,
                {"first.test": (PUBLIC_V4,), "second.test": (PUBLIC_V4_SECOND,)},
            ),
            (
                "https://second.test/path",
                text_scraper.ERROR_PRIVATE_ADDRESS,
                {
                    "first.test": (PUBLIC_V4,),
                    "second.test": (PUBLIC_V4_SECOND, "192.168.1.10"),
                },
            ),
        )
        for location, expected, answers in cases:
            with self.subTest(location=location):
                first = SyntheticResponse(
                    status=302,
                    headers={"Location": location},
                    chunks=[],
                )
                with self.assertRaises(text_scraper._TransportError) as raised:
                    self.run_with_responses(
                        "https://first.test/start",
                        [first],
                        dns_answers=answers,
                    )
                self.assertEqual(expected, raised.exception.public_message)
                self.assertTrue(first.closed)

    def test_non_success_status_is_static_and_closed(self):
        response = SyntheticResponse(status=503)
        self.assert_transport_failure(text_scraper.ERROR_STATUS, response)

    def test_connect_read_timeouts_are_clamped_to_remaining_deadline(self):
        response = SyntheticResponse()
        _, _, opener = self.run_with_responses(
            "https://first.test/start",
            [response],
            monotonic=[100.0, 101.0, 101.0, 101.5, 101.5],
        )
        self.assertEqual(
            (
                text_scraper.CONNECT_TIMEOUT_SECONDS,
                text_scraper.READ_TIMEOUT_SECONDS,
            ),
            opener.call_args.args[1],
        )

        near_deadline = SyntheticResponse()
        _, _, near_opener = self.run_with_responses(
            "https://first.test/start",
            [near_deadline],
            monotonic=[100.0, 109.75, 109.75, 109.8, 109.8],
        )
        self.assertEqual((0.25, 0.25), near_opener.call_args.args[1])

    def test_deadline_before_request_and_after_chunk_is_enforced(self):
        before = SyntheticResponse()
        with patch(
            "text_scraper.socket.getaddrinfo",
            return_value=getaddrinfo_for(PUBLIC_V4),
        ), patch("text_scraper._open_pinned_response") as opener, patch(
            "text_scraper.time.monotonic",
            side_effect=[100.0, 110.0],
        ):
            with self.assertRaises(text_scraper._TransportError) as raised:
                self.node._fetch_text("https://first.test/start")
        self.assertEqual(text_scraper.ERROR_TIMEOUT, raised.exception.public_message)
        opener.assert_not_called()
        self.assertFalse(before.closed)

        after = SyntheticResponse(chunks=[b"A"])
        with self.assertRaises(text_scraper._TransportError) as raised:
            self.run_with_responses(
                "https://first.test/start",
                [after],
                monotonic=[100.0, 100.1, 100.1, 100.2, 110.0],
            )
        self.assertEqual(text_scraper.ERROR_TIMEOUT, raised.exception.public_message)
        self.assertTrue(after.closed)

    def test_blocked_dns_returns_at_aggregate_deadline_without_opening_request(self):
        resolver_started = threading.Event()
        release_resolver = threading.Event()
        outcome = []

        def blocked_resolver(host, port, type):
            del host, port, type
            resolver_started.set()
            release_resolver.wait(1.0)
            return getaddrinfo_for(PUBLIC_V4)

        def fetch():
            try:
                self.node._fetch_text("https://first.test/start")
            except Exception as error:
                outcome.append(error)

        with patch(
            "text_scraper.TOTAL_TIMEOUT_SECONDS",
            0.05,
        ), patch(
            "text_scraper.socket.getaddrinfo",
            side_effect=blocked_resolver,
        ), patch(
            "text_scraper._open_pinned_response",
        ) as opener:
            caller = threading.Thread(target=fetch, daemon=True)
            started_at = time.perf_counter()
            caller.start()
            try:
                resolver_did_start = resolver_started.wait(0.2)
                caller.join(0.15)
                elapsed = time.perf_counter() - started_at
                returned_within_bound = not caller.is_alive()
                request_not_opened = opener.call_count == 0
            finally:
                release_resolver.set()
                caller.join(1.0)

        self.assertTrue(resolver_did_start)
        self.assertTrue(returned_within_bound)
        self.assertLess(elapsed, 0.2)
        self.assertTrue(request_not_opened)
        self.assertEqual(1, len(outcome))
        self.assertIsInstance(outcome[0], text_scraper._TransportError)
        self.assertEqual(text_scraper.ERROR_TIMEOUT, outcome[0].public_message)
        opener.assert_not_called()

    def test_blocked_body_read_returns_at_deadline_and_closes_response(self):
        iterator_started = threading.Event()
        release_iterator = threading.Event()
        outcome = []

        class BlockingResponse(SyntheticResponse):
            def iter_content(self, chunk_size=1, decode_unicode=False):
                self.iter_calls.append((chunk_size, decode_unicode))
                iterator_started.set()
                release_iterator.wait(1.0)
                yield b"late body"

        response = BlockingResponse()

        def fetch():
            try:
                self.node._fetch_text("https://first.test/start")
            except Exception as error:
                outcome.append(error)

        with patch(
            "text_scraper.TOTAL_TIMEOUT_SECONDS",
            0.05,
        ), patch(
            "text_scraper.socket.getaddrinfo",
            return_value=getaddrinfo_for(PUBLIC_V4),
        ), patch(
            "text_scraper._open_pinned_response",
            return_value=SyntheticResponseContext(response),
        ):
            caller = threading.Thread(target=fetch, daemon=True)
            started_at = time.perf_counter()
            caller.start()
            try:
                iterator_did_start = iterator_started.wait(0.2)
                caller.join(0.15)
                elapsed = time.perf_counter() - started_at
                returned_within_bound = not caller.is_alive()
                closed_before_release = response.closed
            finally:
                release_iterator.set()
                caller.join(1.0)

        self.assertTrue(iterator_did_start)
        self.assertTrue(returned_within_bound)
        self.assertLess(elapsed, 0.2)
        self.assertTrue(closed_before_release)
        self.assertEqual(1, len(outcome))
        self.assertIsInstance(outcome[0], text_scraper._TransportError)
        self.assertEqual(text_scraper.ERROR_TIMEOUT, outcome[0].public_message)

    def test_network_exception_and_privacy_canaries_are_not_exposed_or_logged(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch(
            "text_scraper.socket.getaddrinfo",
            return_value=getaddrinfo_for(PUBLIC_V4),
        ), patch(
            "text_scraper._open_pinned_response",
            side_effect=requests.exceptions.ConnectionError("EXCEPTION_SECRET_CANARY"),
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            output, = self.node.scrape_news(
                "https://first.test/private-query?token=URL_SECRET_CANARY",
                99,
            )

        self.assertEqual(text_scraper.ERROR_REQUEST, output)
        combined = output + stdout.getvalue() + stderr.getvalue()
        for canary in (
            "EXCEPTION_SECRET_CANARY",
            "URL_SECRET_CANARY",
            "private-query",
            "first.test",
        ):
            self.assertNotIn(canary, combined)

    def test_timeout_exception_maps_to_static_timeout_and_closes_context(self):
        class RaisingContext:
            def __enter__(self):
                raise requests.exceptions.ReadTimeout("TIMEOUT_SECRET_CANARY")

            def __exit__(self, exc_type, exc, traceback):
                return False

        with patch(
            "text_scraper.socket.getaddrinfo",
            return_value=getaddrinfo_for(PUBLIC_V4),
        ), patch(
            "text_scraper._open_pinned_response",
            return_value=RaisingContext(),
        ):
            output, = self.node.scrape_news("https://first.test/path", seed=100)

        self.assertEqual(text_scraper.ERROR_TIMEOUT, output)
        self.assertNotIn("CANARY", output)


class TextScraperHeadlineCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.node = text_scraper.TextScraper()

    def test_representative_headline_tuple_preserves_order_deduplication_and_limit(self):
        repeated = "Repeated synthetic headline long enough"
        unique = [f"Synthetic headline number {index:02d}" for index in range(20)]
        html = (
            f"<h1>{repeated}</h1><h2>{repeated}</h2>"
            + "".join(f"<h3>{value}</h3>" for value in unique)
            + '<div class="title">tiny</div>'
        ).encode("utf-8")
        response = SyntheticResponse(chunks=[html])

        with patch(
            "text_scraper.socket.getaddrinfo",
            return_value=getaddrinfo_for(PUBLIC_V4),
        ), patch(
            "text_scraper._open_pinned_response",
            return_value=SyntheticResponseContext(response),
        ):
            output = self.node.scrape_news("https://example.test", seed=7)

        expected = [repeated, *unique[:14]]
        self.assertEqual(("\n".join(expected) + "\n",), output)
        self.assertTrue(response.closed)

    def test_no_headline_and_dependency_errors_are_static(self):
        response = SyntheticResponse(chunks=[b"<p>No candidate</p>"])
        with patch(
            "text_scraper.socket.getaddrinfo",
            return_value=getaddrinfo_for(PUBLIC_V4),
        ), patch(
            "text_scraper._open_pinned_response",
            return_value=SyntheticResponseContext(response),
        ):
            output, = self.node.scrape_news("https://example.test/secret", seed=8)

        self.assertEqual(text_scraper.ERROR_NO_HEADLINES, output)
        self.assertNotIn("example.test", output)

        with patch.object(text_scraper, "requests", None), patch.object(
            text_scraper,
            "BeautifulSoup",
            None,
        ):
            output, = self.node.scrape_news("https://example.test", seed=9)
        self.assertEqual(text_scraper.ERROR_DEPENDENCIES, output)

    def test_node_public_contract_is_unchanged(self):
        self.assertEqual(("STRING",), self.node.RETURN_TYPES)
        self.assertEqual(("text",), self.node.RETURN_NAMES)
        self.assertEqual("scrape_news", self.node.FUNCTION)
        self.assertEqual("ComfyUI Text Processor", self.node.CATEGORY)
        required = self.node.INPUT_TYPES()["required"]
        self.assertEqual(["url", "seed"], list(required))


if __name__ == "__main__":
    unittest.main()

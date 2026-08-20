import hashlib
import io
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import unittest
import urllib.error
import zipfile
from unittest.mock import patch

from scripts import validate_publish_candidate as candidate


ROOT = pathlib.Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / ".tmp" / "test-publish-candidate"


class _Response:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _zip_bytes(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data, mode in entries:
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = mode << 16
            archive.writestr(info, data)
    return stream.getvalue()


def _git_blob_id(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


class PublishCandidateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TMP_ROOT.mkdir(parents=True, exist_ok=True)

    def test_semver_is_strict_and_orderable(self):
        self.assertEqual(candidate.parse_semver("2.10.3"), (2, 10, 3))
        for value in ("1.2", "v1.2.3", "1.2.3-rc1", "01.2.3", "1.2.3 ", "secret"):
            with self.subTest(value=value), self.assertRaisesRegex(
                candidate.CandidateError, "invalid_version"
            ):
                candidate.parse_semver(value)

    def test_version_intent_allows_only_a_strictly_increasing_version_field(self):
        base = b'[project]\nname="text_processor"\nversion="1.7.5"\n[tool.comfy]\nPublisherId="rookiestar"\n'
        head = b'[project]\nname="text_processor"\nversion="1.8.0"\n[tool.comfy]\nPublisherId="rookiestar"\n'
        result = candidate.validate_version_intent(base, head, "1.8.0")
        self.assertEqual(result.version, "1.8.0")
        self.assertEqual(result.node_id, "text_processor")
        self.assertEqual(result.publisher_id, "rookiestar")

        rejected = (
            (base, base, "1.7.5", "version_not_increased"),
            (head, base, "1.7.5", "version_not_increased"),
            (base, head, "1.8.1", "version_mismatch"),
            (
                base,
                head.replace(b'version="1.8.0"', b'version="1.8.0"\ndescription="changed"'),
                "1.8.0",
                "metadata_delta",
            ),
        )
        for old, new, expected, code in rejected:
            with self.subTest(code=code), self.assertRaisesRegex(candidate.CandidateError, code):
                candidate.validate_version_intent(old, new, expected)

    def test_release_context_fails_closed_for_event_identity_mismatches(self):
        sha = "a" * 40
        base = "b" * 40
        candidate.validate_release_context(
            event_name="push",
            ref="refs/heads/main",
            repository_owner="rookiestar28",
            expected_sha=sha,
            head_sha=sha,
            event_sha=sha,
            base_sha=base,
            manual_publish=False,
        )
        candidate.validate_release_context(
            event_name="workflow_dispatch",
            ref="refs/heads/main",
            repository_owner="rookiestar28",
            expected_sha=sha,
            head_sha=sha,
            event_sha=sha,
            base_sha=base,
            manual_publish=True,
            manual_candidate_sha=sha,
        )

        mutations = (
            {"event_name": "pull_request"},
            {"ref": "refs/heads/dev"},
            {"repository_owner": "fork"},
            {"head_sha": "c" * 40},
            {"event_sha": "c" * 40},
            {"base_sha": "0" * 40},
            {"event_name": "workflow_dispatch", "manual_publish": False},
        )
        defaults = dict(
            event_name="push",
            ref="refs/heads/main",
            repository_owner="rookiestar28",
            expected_sha=sha,
            head_sha=sha,
            event_sha=sha,
            base_sha=base,
            manual_publish=False,
        )
        for mutation in mutations:
            args = defaults | mutation
            with self.subTest(mutation=mutation), self.assertRaises(candidate.CandidateError):
                candidate.validate_release_context(**args)

    def test_registry_check_treats_only_404_as_absent_and_sends_no_credentials(self):
        requested = []

        def absent(request, timeout):
            requested.append((request, timeout))
            raise urllib.error.HTTPError(request.full_url, 404, "missing", {}, None)

        candidate.check_registry_version_absent("text_processor", "1.8.0", opener=absent)
        request, timeout = requested[0]
        self.assertEqual(request.full_url, "https://api.comfy.org/nodes/text_processor/versions/1.8.0")
        self.assertEqual(timeout, candidate.REGISTRY_TIMEOUT_SECONDS)
        self.assertNotIn("Authorization", request.headers)

        with self.assertRaisesRegex(candidate.CandidateError, "duplicate_version"):
            candidate.check_registry_version_absent(
                "text_processor", "1.8.0", opener=lambda *_args, **_kwargs: _Response(200)
            )
        with self.assertRaisesRegex(candidate.CandidateError, "registry_unavailable"):
            candidate.check_registry_version_absent(
                "text_processor", "1.8.0", opener=lambda *_args, **_kwargs: _Response(503)
            )
        with self.assertRaisesRegex(candidate.CandidateError, "registry_unavailable"):
            candidate.check_registry_version_absent(
                "text_processor",
                "1.8.0",
                opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib.error.URLError("canary")),
            )

    def test_tracked_path_policy_rejects_internal_traversal_and_symlinks(self):
        candidate.validate_tracked_paths(
            [candidate.TrackedPath("README.md", candidate.REGULAR_FILE_MODE)]
        )
        rejected = (
            candidate.TrackedPath(".planning/private.md", candidate.REGULAR_FILE_MODE),
            candidate.TrackedPath("reference/source.py", candidate.REGULAR_FILE_MODE),
            candidate.TrackedPath(".sessions/id.md", candidate.REGULAR_FILE_MODE),
            candidate.TrackedPath("../escape", candidate.REGULAR_FILE_MODE),
            candidate.TrackedPath("secrets/id_rsa", candidate.REGULAR_FILE_MODE),
            candidate.TrackedPath("link.py", candidate.SYMLINK_MODE),
        )
        for item in rejected:
            with self.subTest(path=item.path), self.assertRaises(candidate.CandidateError):
                candidate.validate_tracked_paths([item])

    def test_archive_requires_exact_regular_member_set_and_size_limits(self):
        expected = [
            candidate.TrackedPath("README.md", candidate.REGULAR_FILE_MODE),
            candidate.TrackedPath("module.py", candidate.EXECUTABLE_FILE_MODE),
        ]
        payload = _zip_bytes(
            [
                ("README.md", b"readme", stat.S_IFREG | 0o644),
                ("module.py", b"print('ok')", stat.S_IFREG | 0o755),
            ]
        )
        summary = candidate.verify_archive_bytes(payload, expected)
        self.assertEqual(summary.member_count, 2)
        self.assertEqual(summary.sha256, hashlib.sha256(payload).hexdigest())

        attacks = (
            _zip_bytes([("README.md", b"x", stat.S_IFREG | 0o644)]),
            _zip_bytes(
                [
                    ("README.md", b"x", stat.S_IFREG | 0o644),
                    ("module.py", b"x", stat.S_IFREG | 0o755),
                    ("../escape", b"x", stat.S_IFREG | 0o644),
                ]
            ),
            _zip_bytes(
                [
                    ("README.md", b"x", stat.S_IFREG | 0o644),
                    ("module.py", b"target", stat.S_IFLNK | 0o777),
                ]
            ),
        )
        for payload in attacks:
            with self.subTest(digest=hashlib.sha256(payload).hexdigest()), self.assertRaises(
                candidate.CandidateError
            ):
                candidate.verify_archive_bytes(payload, expected)

    def test_archive_manifest_honors_only_literal_comfyignore_exclusions(self):
        tracked = [
            candidate.TrackedPath(".comfyignore", candidate.REGULAR_FILE_MODE),
            candidate.TrackedPath("README.md", candidate.REGULAR_FILE_MODE),
            candidate.TrackedPath(".github/workflows/publish.yml", candidate.REGULAR_FILE_MODE),
            candidate.TrackedPath("tests/test_node.py", candidate.REGULAR_FILE_MODE),
            candidate.TrackedPath("package.json", candidate.REGULAR_FILE_MODE),
        ]
        filtered = candidate.filter_archive_paths(
            tracked,
            "# public package exclusions\n.github/\ntests/\npackage.json\n",
        )
        self.assertEqual([item.path for item in filtered], [".comfyignore", "README.md"])

        unsupported = ("*.log\n", "!README.md\n", "docs/[ab].md\n")
        for manifest in unsupported:
            with self.subTest(manifest=manifest), self.assertRaisesRegex(
                candidate.CandidateError, "comfyignore_unsupported"
            ):
                candidate.filter_archive_paths(tracked, manifest)

    def test_archive_content_is_bound_to_exact_git_blob_ids(self):
        expected_content = b"exact candidate bytes\n"
        expected = [
            candidate.TrackedPath(
                "module.py",
                candidate.REGULAR_FILE_MODE,
                _git_blob_id(expected_content),
            )
        ]
        candidate.verify_archive_bytes(
            _zip_bytes([("module.py", expected_content, stat.S_IFREG | 0o644)]),
            expected,
        )
        with self.assertRaisesRegex(candidate.CandidateError, "archive_content"):
            candidate.verify_archive_bytes(
                _zip_bytes([("module.py", b"substituted\n", stat.S_IFREG | 0o644)]),
                expected,
            )

    def test_archive_rejects_duplicate_member_names(self):
        stream = io.BytesIO()
        with patch("warnings.warn"):
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("README.md", b"one")
                archive.writestr("README.md", b"two")
        with self.assertRaisesRegex(candidate.CandidateError, "archive_duplicate"):
            candidate.verify_archive_bytes(
                stream.getvalue(),
                [candidate.TrackedPath("README.md", candidate.REGULAR_FILE_MODE)],
            )

    def test_actual_git_checkout_checks_sha_cleanliness_and_mtime_normalization(self):
        work = pathlib.Path(tempfile.mkdtemp(dir=TMP_ROOT))
        self.addCleanup(shutil.rmtree, work, True)
        subprocess.run(["git", "init", "--template=", str(work)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=work, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=work, check=True)
        (work / "README.md").write_text("ok\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=work, check=True)
        subprocess.run(["git", "commit", "-m", "test"], cwd=work, check=True, capture_output=True)
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()

        summary = candidate.validate_checkout(sha, cwd=work)
        self.assertEqual(summary.head_sha, sha)
        self.assertEqual([item.path for item in summary.tracked_paths], ["README.md"])
        epoch = candidate.normalize_tracked_mtimes(summary.tracked_paths, cwd=work)
        self.assertEqual(int((work / "README.md").stat().st_mtime), epoch)

        (work / "README.md").write_text("second\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=work, check=True)
        subprocess.run(["git", "commit", "-m", "second"], cwd=work, check=True, capture_output=True)
        second_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()
        candidate.validate_base_ancestry(sha, second_sha, cwd=work)
        with self.assertRaisesRegex(candidate.CandidateError, "base_not_ancestor"):
            candidate.validate_base_ancestry(second_sha, sha, cwd=work)

        (work / "untracked.txt").write_text("canary", encoding="utf-8")
        with self.assertRaisesRegex(candidate.CandidateError, "dirty_checkout") as caught:
            candidate.validate_checkout(second_sha, cwd=work)
        self.assertNotIn("canary", str(caught.exception))
        with self.assertRaisesRegex(candidate.CandidateError, "sha_mismatch"):
            candidate.validate_checkout("f" * 40, cwd=work)


if __name__ == "__main__":
    unittest.main()

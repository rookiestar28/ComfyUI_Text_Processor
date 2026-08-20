#!/usr/bin/env python3
"""Fail-closed validation for hosted Registry publication candidates."""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import io
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import zipfile


FULL_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
SEMVER_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
REGISTRY_TIMEOUT_SECONDS = 10
REGULAR_FILE_MODE = "100644"
EXECUTABLE_FILE_MODE = "100755"
SYMLINK_MODE = "120000"
ALLOWED_FILE_MODES = frozenset({REGULAR_FILE_MODE, EXECUTABLE_FILE_MODE})
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_MEMBER_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_EXPANDED_BYTES = 200 * 1024 * 1024
EXPECTED_NODE_ID = "text_processor"
EXPECTED_PUBLISHER_ID = "rookiestar"
EXPECTED_REPOSITORY_OWNER = "rookiestar28"
EXPECTED_RELEASE_REF = "refs/heads/main"
FORBIDDEN_TOP_LEVEL = frozenset(
    {".git", ".planning", ".sessions", ".tmp", "reference", "references"}
)
FORBIDDEN_FILENAMES = frozenset(
    {".env", "id_dsa", "id_ecdsa", "id_ed25519", "id_rsa"}
)
FORBIDDEN_SUFFIXES = frozenset({".key", ".p12", ".pfx", ".pem"})


class CandidateError(ValueError):
    """Static error code safe for public CI logs."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class TrackedPath:
    path: str
    mode: str


@dataclasses.dataclass(frozen=True)
class CheckoutSummary:
    head_sha: str
    tracked_paths: tuple[TrackedPath, ...]


@dataclasses.dataclass(frozen=True)
class VersionIntent:
    version: str
    node_id: str
    publisher_id: str


@dataclasses.dataclass(frozen=True)
class ArchiveSummary:
    sha256: str
    member_count: int
    compressed_bytes: int
    expanded_bytes: int


def _require_full_sha(value: str, code: str = "invalid_sha") -> str:
    if not FULL_SHA_PATTERN.fullmatch(value):
        raise CandidateError(code)
    return value


def _run_git(arguments: list[str], cwd: pathlib.Path) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CandidateError("git_unavailable") from exc
    if result.returncode != 0:
        raise CandidateError("git_command_failed")
    return result.stdout


def _validate_relative_path(value: str) -> pathlib.PurePosixPath:
    raw_parts = value.split("/")
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or ":" in value
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise CandidateError("unsafe_path")
    path = pathlib.PurePosixPath(value)
    if path.is_absolute():
        raise CandidateError("unsafe_path")
    lowered = tuple(part.casefold() for part in path.parts)
    if lowered[0] in FORBIDDEN_TOP_LEVEL:
        raise CandidateError("internal_path")
    filename = lowered[-1]
    if filename in FORBIDDEN_FILENAMES or filename.startswith(".env."):
        raise CandidateError("secret_path")
    if pathlib.PurePosixPath(filename).suffix in FORBIDDEN_SUFFIXES:
        raise CandidateError("secret_path")
    return path


def validate_tracked_paths(paths: list[TrackedPath] | tuple[TrackedPath, ...]) -> None:
    seen: set[str] = set()
    for item in paths:
        _validate_relative_path(item.path)
        if item.path in seen:
            raise CandidateError("tracked_path_duplicate")
        seen.add(item.path)
        if item.mode == SYMLINK_MODE:
            raise CandidateError("tracked_symlink")
        if item.mode not in ALLOWED_FILE_MODES:
            raise CandidateError("tracked_file_type")


def list_tracked_paths(cwd: pathlib.Path | str = ".") -> tuple[TrackedPath, ...]:
    root = pathlib.Path(cwd)
    raw = _run_git(["ls-files", "-s", "-z"], root)
    entries: list[TrackedPath] = []
    for record in raw.split("\x00"):
        if not record:
            continue
        try:
            metadata, path = record.split("\t", 1)
            mode, _object_id, stage = metadata.split(" ", 2)
        except ValueError as exc:
            raise CandidateError("tracked_manifest_invalid") from exc
        if stage != "0":
            raise CandidateError("tracked_stage_invalid")
        entries.append(TrackedPath(path=path, mode=mode))
    if not entries:
        raise CandidateError("tracked_manifest_empty")
    validate_tracked_paths(entries)
    return tuple(entries)


def _head_sha(cwd: pathlib.Path) -> str:
    head = _run_git(["rev-parse", "HEAD"], cwd).strip()
    return _require_full_sha(head, "head_sha_invalid")


def validate_checkout(
    expected_sha: str,
    *,
    cwd: pathlib.Path | str = ".",
    allowed_untracked: tuple[str, ...] = (),
) -> CheckoutSummary:
    root = pathlib.Path(cwd)
    expected = _require_full_sha(expected_sha)
    head = _head_sha(root)
    if head != expected:
        raise CandidateError("sha_mismatch")

    allowed = set(allowed_untracked)
    status = _run_git(["status", "--porcelain=v1", "--untracked-files=all"], root)
    dirty = []
    for line in status.splitlines():
        if not line:
            continue
        path = line[3:]
        if line.startswith("?? ") and path in allowed:
            continue
        dirty.append(line[:2])
    if dirty:
        raise CandidateError("dirty_checkout")

    tracked = list_tracked_paths(root)
    return CheckoutSummary(head_sha=head, tracked_paths=tracked)


def normalize_tracked_mtimes(
    tracked_paths: tuple[TrackedPath, ...] | list[TrackedPath],
    *,
    cwd: pathlib.Path | str = ".",
) -> int:
    root = pathlib.Path(cwd)
    raw_epoch = _run_git(["show", "-s", "--format=%ct", "HEAD"], root).strip()
    try:
        epoch = int(raw_epoch)
    except ValueError as exc:
        raise CandidateError("commit_time_invalid") from exc
    if epoch <= 315532800:
        raise CandidateError("commit_time_invalid")
    for item in tracked_paths:
        target = root.joinpath(*pathlib.PurePosixPath(item.path).parts)
        if not target.is_file() or target.is_symlink():
            raise CandidateError("tracked_file_missing")
        try:
            # IMPORTANT: symlinks are rejected above; Windows may not expose
            # follow_symlinks for utime even though the regular-file operation is safe.
            try:
                os.utime(target, (epoch, epoch), follow_symlinks=False)
            except NotImplementedError:
                os.utime(target, (epoch, epoch))
        except OSError as exc:
            raise CandidateError("mtime_normalization_failed") from exc
    return epoch


def parse_semver(value: str) -> tuple[int, int, int]:
    match = SEMVER_PATTERN.fullmatch(value)
    if not match:
        raise CandidateError("invalid_version")
    return tuple(int(part) for part in match.groups())


def _parse_pyproject(payload: bytes) -> dict:
    try:
        return tomllib.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise CandidateError("invalid_pyproject") from exc


def _metadata_identity(document: dict) -> tuple[str, str, str]:
    try:
        project = document["project"]
        comfy = document["tool"]["comfy"]
        node_id = project["name"]
        version = project["version"]
        publisher_id = comfy["PublisherId"]
    except (KeyError, TypeError) as exc:
        raise CandidateError("metadata_identity") from exc
    if (
        node_id != EXPECTED_NODE_ID
        or publisher_id != EXPECTED_PUBLISHER_ID
        or not isinstance(version, str)
    ):
        raise CandidateError("metadata_identity")
    return node_id, publisher_id, version


def validate_version_intent(
    base_payload: bytes, head_payload: bytes, expected_version: str
) -> VersionIntent:
    expected_tuple = parse_semver(expected_version)
    base = _parse_pyproject(base_payload)
    head = _parse_pyproject(head_payload)
    base_node, base_publisher, base_version = _metadata_identity(base)
    node_id, publisher_id, head_version = _metadata_identity(head)
    base_tuple = parse_semver(base_version)
    head_tuple = parse_semver(head_version)
    if head_version != expected_version:
        raise CandidateError("version_mismatch")
    if head_tuple != expected_tuple or head_tuple <= base_tuple:
        raise CandidateError("version_not_increased")
    if (base_node, base_publisher) != (node_id, publisher_id):
        raise CandidateError("metadata_delta")

    normalized_head = copy.deepcopy(head)
    normalized_head["project"]["version"] = base_version
    if normalized_head != base:
        raise CandidateError("metadata_delta")
    return VersionIntent(version=head_version, node_id=node_id, publisher_id=publisher_id)


def validate_release_context(
    *,
    event_name: str,
    ref: str,
    repository_owner: str,
    expected_sha: str,
    head_sha: str,
    event_sha: str,
    base_sha: str,
    manual_publish: bool,
    manual_candidate_sha: str | None = None,
) -> None:
    expected = _require_full_sha(expected_sha)
    if _require_full_sha(head_sha, "head_sha_invalid") != expected:
        raise CandidateError("sha_mismatch")
    if _require_full_sha(event_sha, "event_sha_invalid") != expected:
        raise CandidateError("event_sha_mismatch")
    base = _require_full_sha(base_sha, "base_sha_invalid")
    if base == "0" * 40 or base == expected:
        raise CandidateError("base_sha_invalid")
    if repository_owner != EXPECTED_REPOSITORY_OWNER:
        raise CandidateError("owner_mismatch")
    if ref != EXPECTED_RELEASE_REF:
        raise CandidateError("ref_mismatch")
    if event_name == "push":
        if manual_publish:
            raise CandidateError("event_mismatch")
    elif event_name == "workflow_dispatch":
        if not manual_publish:
            raise CandidateError("manual_confirmation_missing")
        if manual_candidate_sha != expected:
            raise CandidateError("manual_confirmation_missing")
    else:
        raise CandidateError("event_mismatch")


def validate_base_ancestry(base_sha: str, head_sha: str, *, cwd: pathlib.Path | str = ".") -> None:
    base = _require_full_sha(base_sha, "base_sha_invalid")
    head = _require_full_sha(head_sha, "head_sha_invalid")
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", base, head],
            cwd=pathlib.Path(cwd),
            check=False,
            capture_output=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CandidateError("git_unavailable") from exc
    if result.returncode != 0:
        raise CandidateError("base_not_ancestor")


def check_registry_version_absent(
    node_id: str,
    version: str,
    *,
    opener=urllib.request.urlopen,
) -> None:
    if node_id != EXPECTED_NODE_ID:
        raise CandidateError("metadata_identity")
    parse_semver(version)
    quoted_node = urllib.parse.quote(node_id, safe="")
    quoted_version = urllib.parse.quote(version, safe="")
    url = f"https://api.comfy.org/nodes/{quoted_node}/versions/{quoted_version}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with opener(request, timeout=REGISTRY_TIMEOUT_SECONDS) as response:
            status_code = response.status
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return
        raise CandidateError("registry_unavailable") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CandidateError("registry_unavailable") from None
    if status_code == 404:
        return
    if status_code == 200:
        raise CandidateError("duplicate_version")
    raise CandidateError("registry_unavailable")


def verify_archive_bytes(
    payload: bytes,
    expected_paths: tuple[TrackedPath, ...] | list[TrackedPath],
) -> ArchiveSummary:
    if not payload or len(payload) > MAX_ARCHIVE_BYTES:
        raise CandidateError("archive_size")
    validate_tracked_paths(expected_paths)
    expected_names = [item.path for item in expected_paths]
    expanded = 0
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise CandidateError("archive_duplicate")
            for info in infos:
                _validate_relative_path(info.filename)
                if info.is_dir():
                    raise CandidateError("archive_member_type")
                unix_mode = info.external_attr >> 16
                file_type = stat.S_IFMT(unix_mode)
                if file_type not in {0, stat.S_IFREG}:
                    raise CandidateError("archive_member_type")
                if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                    raise CandidateError("archive_member_size")
                expanded += info.file_size
                if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
                    raise CandidateError("archive_expanded_size")
            if names != expected_names:
                raise CandidateError("archive_members")
            bad_member = archive.testzip()
            if bad_member is not None:
                raise CandidateError("archive_crc")
    except CandidateError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError):
        raise CandidateError("archive_invalid") from None
    return ArchiveSummary(
        sha256=hashlib.sha256(payload).hexdigest(),
        member_count=len(expected_names),
        compressed_bytes=len(payload),
        expanded_bytes=expanded,
    )


def verify_archive_file(
    archive_path: pathlib.Path,
    expected_paths: tuple[TrackedPath, ...],
) -> ArchiveSummary:
    try:
        payload = archive_path.read_bytes()
    except OSError as exc:
        raise CandidateError("archive_unreadable") from exc
    return verify_archive_bytes(payload, expected_paths)


def _base_pyproject(base_sha: str, cwd: pathlib.Path) -> bytes:
    _require_full_sha(base_sha, "base_sha_invalid")
    text = _run_git(["show", f"{base_sha}:pyproject.toml"], cwd)
    return text.encode("utf-8", errors="surrogateescape")


def _safe_result(**values) -> None:
    print(json.dumps({"status": "pass", **values}, sort_keys=True, separators=(",", ":")))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--expected-sha", required=True)

    release = subparsers.add_parser("release")
    release.add_argument("--expected-sha", required=True)
    release.add_argument("--event-sha", required=True)
    release.add_argument("--event-name", required=True)
    release.add_argument("--ref", required=True)
    release.add_argument("--repository-owner", required=True)
    release.add_argument("--base-sha", required=True)
    release.add_argument("--expected-version", required=True)
    release.add_argument("--manual-publish", action="store_true")
    release.add_argument("--manual-candidate-sha")
    release.add_argument("--check-registry", action="store_true")
    release.add_argument("--normalize-mtimes", action="store_true")

    archive = subparsers.add_parser("archive")
    archive.add_argument("--archive", required=True)
    archive.add_argument("--expected-sha", required=True)
    archive.add_argument("--expected-archive-sha")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cwd = pathlib.Path.cwd()
    try:
        if args.mode == "validate":
            checkout = validate_checkout(args.expected_sha, cwd=cwd)
            _safe_result(
                mode="validate",
                sha=checkout.head_sha,
                tracked_count=len(checkout.tracked_paths),
            )
            return 0

        if args.mode == "release":
            checkout = validate_checkout(args.expected_sha, cwd=cwd)
            validate_release_context(
                event_name=args.event_name,
                ref=args.ref,
                repository_owner=args.repository_owner,
                expected_sha=args.expected_sha,
                head_sha=checkout.head_sha,
                event_sha=args.event_sha,
                base_sha=args.base_sha,
                manual_publish=args.manual_publish,
                manual_candidate_sha=args.manual_candidate_sha,
            )
            validate_base_ancestry(args.base_sha, checkout.head_sha, cwd=cwd)
            head_payload = (cwd / "pyproject.toml").read_bytes()
            intent = validate_version_intent(
                _base_pyproject(args.base_sha, cwd), head_payload, args.expected_version
            )
            if args.check_registry:
                check_registry_version_absent(intent.node_id, intent.version)
            epoch = None
            if args.normalize_mtimes:
                epoch = normalize_tracked_mtimes(checkout.tracked_paths, cwd=cwd)
            _safe_result(
                mode="release",
                sha=checkout.head_sha,
                version=intent.version,
                tracked_count=len(checkout.tracked_paths),
                normalized_epoch=epoch,
            )
            return 0

        expected = _require_full_sha(args.expected_sha)
        head = _head_sha(cwd)
        if head != expected:
            raise CandidateError("sha_mismatch")
        tracked = list_tracked_paths(cwd)
        summary = verify_archive_file(pathlib.Path(args.archive), tracked)
        if args.expected_archive_sha and summary.sha256 != args.expected_archive_sha:
            raise CandidateError("archive_hash_mismatch")
        _safe_result(
            mode="archive",
            sha=head,
            archive_sha256=summary.sha256,
            member_count=summary.member_count,
            compressed_bytes=summary.compressed_bytes,
            expanded_bytes=summary.expanded_bytes,
        )
        return 0
    except (CandidateError, OSError) as exc:
        code = exc.code if isinstance(exc, CandidateError) else "filesystem_error"
        print(
            json.dumps({"status": "error", "code": code}, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "publish.yml"
CI_LOCK = ROOT / ".github" / "requirements-ci.txt"
PUBLISH_LOCK = ROOT / ".github" / "requirements-publish.txt"
PRECOMMIT_CONFIG = ROOT / ".pre-commit-config.yaml"
LINUX_FULL_GATE = ROOT / "scripts" / "run_full_tests_linux.sh"
WINDOWS_FULL_GATE = ROOT / "scripts" / "run_full_tests_windows.ps1"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def audit_workflow(text):
    findings = []
    lowered = text.lower()
    for forbidden in (
        "pull_request_target",
        "workflow_run",
        "actions/cache",
        "upload-artifact",
        "download-artifact",
        "continue-on-error",
        "issues: write",
        "contents: write",
        "publish-node-action",
    ):
        if forbidden in lowered:
            findings.append(f"forbidden:{forbidden}")

    uses = re.findall(r"^\s*uses:\s*([^\s#]+)", text, re.MULTILINE)
    if not uses:
        findings.append("missing:uses")
    for value in uses:
        revision = value.rsplit("@", 1)[-1] if "@" in value else ""
        if not FULL_SHA.fullmatch(revision):
            findings.append("mutable_action")

    required = (
        "pull_request:",
        "workflow_dispatch:",
        "branches: [main]",
        "permissions:\n  contents: read",
        "publication-readiness:",
        "publish-node:",
        "needs: validate",
        "needs: [validate, publication-readiness]",
        "persist-credentials: false",
        "--require-hashes --only-binary=:all:",
        "scripts/run_full_tests_linux.sh",
        "validate_publish_candidate.py release",
        "validate_publish_candidate.py archive",
        "--no-enable-telemetry node pack",
        "archive-sha256: ${{ steps.archive.outputs.archive-sha256 }}",
        "READINESS_ARCHIVE_SHA: ${{ needs.publication-readiness.outputs.archive-sha256 }}",
        "needs.publication-readiness.result == 'success'",
    )
    for token in required:
        if token not in text:
            findings.append(f"missing:{token}")

    if text.count("persist-credentials: false") != 3:
        findings.append("checkout_credentials")
    if text.count("--require-hashes --only-binary=:all:") != 3:
        findings.append("dependency_hash_boundary")
    if text.count("validate_publish_candidate.py release") != 2:
        findings.append("release_recheck")
    if text.count("validate_publish_candidate.py archive") != 4:
        findings.append("archive_recheck")
    if text.count("--no-enable-telemetry node pack") != 4:
        findings.append("archive_pack_count")
    if text.count("--check-registry") != 2:
        findings.append("registry_recheck")
    if text.count("--event-sha") != 2 or text.count("--manual-candidate-sha") != 2:
        findings.append("manual_sha_binding")
    if text.count("github.repository_owner == 'rookiestar28'") != 2:
        findings.append("owner_gate")
    if text.count("github.ref == 'refs/heads/main'") != 2:
        findings.append("ref_gate")

    publish_marker = "- name: Publish exact candidate"
    if text.count(publish_marker) != 1:
        findings.append("publish_step")
    else:
        before, final_step = text.split(publish_marker, 1)
        if "secrets." in before or "REGISTRY_ACCESS_TOKEN" in before:
            findings.append("early_secret")
        if "REGISTRY_ACCESS_TOKEN: ${{ secrets.REGISTRY_ACCESS_TOKEN }}" not in final_step:
            findings.append("missing_secret")
        if 'comfy --skip-prompt --no-enable-telemetry node publish --token "$REGISTRY_ACCESS_TOKEN"' not in final_step:
            findings.append("unsafe_publish_command")

    return findings


class PublishWorkflowSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_workflow_has_no_security_findings(self):
        self.assertEqual(audit_workflow(self.text), [])

    def test_fork_validation_is_secretless_and_read_only(self):
        validate_job = self.text.split("  validate:", 1)[1].split(
            "  publication-readiness:", 1
        )[0]
        self.assertIn("pull_request:", self.text)
        self.assertNotIn("secrets.", validate_job)
        self.assertNotIn("permissions:", validate_job)
        self.assertIn("contents: read", self.text)

    def test_release_jobs_are_gated_to_trusted_main_and_exact_inputs(self):
        readiness = self.text.split("  publication-readiness:", 1)[1].split(
            "  publish-node:", 1
        )[0]
        for token in (
            "github.repository_owner == 'rookiestar28'",
            "github.ref == 'refs/heads/main'",
            "github.event_name == 'push'",
            "github.event_name == 'workflow_dispatch'",
            "inputs.publish == true",
            "--expected-sha",
            "--event-sha",
            "--base-sha",
            "--expected-version",
            "--check-registry",
        ):
            self.assertIn(token, readiness)

    def test_dependency_locks_are_exact_hashed_and_binary_installed(self):
        for path in (CI_LOCK, PUBLISH_LOCK):
            text = path.read_text(encoding="utf-8")
            requirements = [line for line in text.splitlines() if line and not line[0].isspace() and not line.startswith(("#", "--"))]
            self.assertTrue(requirements, path)
            for line in requirements:
                self.assertRegex(
                    line,
                    r"^[a-zA-Z0-9_.-]+(?:==[^ ;\\]+| @ https://[^ ]+#sha256=[0-9a-f]{64})",
                )
            self.assertIn("--hash=sha256:", text)
        ci_text = CI_LOCK.read_text(encoding="utf-8")
        self.assertNotIn("--extra-index-url", ci_text)
        self.assertRegex(ci_text, r"torch @ https://download\.pytorch\.org/.+#sha256=[0-9a-f]{64}")
        self.assertRegex(ci_text, r"torchvision @ https://download\.pytorch\.org/.+#sha256=[0-9a-f]{64}")
        self.assertIn("comfy-cli==1.16.0", PUBLISH_LOCK.read_text(encoding="utf-8"))

    def test_ci_lock_pins_pillow_at_complete_security_floor(self):
        ci_text = CI_LOCK.read_text(encoding="utf-8")
        match = re.search(r"(?mi)^pillow==(\d+)\.(\d+)\.(\d+)\s+\\$", ci_text)
        self.assertIsNotNone(match, "CI lock must contain one exact Pillow pin")
        self.assertGreaterEqual(
            tuple(int(part) for part in match.groups()),
            (12, 3, 0),
            "Pillow 12.3.0 is the first release covering the complete advisory set",
        )

        pillow_block = ci_text[match.start() :].split("\nplatformdirs==", 1)[0]
        self.assertIn("--hash=sha256:", pillow_block)
        self.assertNotIn(" @ ", pillow_block.splitlines()[0])

    def test_ci_lock_pins_requests_at_security_floor_without_product_reachability(self):
        ci_text = CI_LOCK.read_text(encoding="utf-8")
        publish_text = PUBLISH_LOCK.read_text(encoding="utf-8")
        pattern = r"(?mi)^requests==(\d+)\.(\d+)\.(\d+)\s+\\$"
        ci_match = re.search(pattern, ci_text)
        publish_match = re.search(pattern, publish_text)
        self.assertIsNotNone(ci_match, "CI lock must contain one exact Requests pin")
        self.assertIsNotNone(
            publish_match, "publication lock must contain one exact Requests pin"
        )
        ci_version = tuple(int(part) for part in ci_match.groups())
        publish_version = tuple(int(part) for part in publish_match.groups())
        self.assertGreaterEqual(
            ci_version,
            (2, 33, 0),
            "Requests 2.33.0 is the first release outside the vulnerable range",
        )
        self.assertEqual(ci_version, (2, 34, 2))
        self.assertEqual(ci_version, publish_version)

        requests_block = ci_text[ci_match.start() :].split("\nsimpleeval==", 1)[0]
        self.assertIn("--hash=sha256:", requests_block)
        self.assertNotIn(" @ ", requests_block.splitlines()[0])

        for path in ROOT.glob("*.py"):
            product_text = path.read_text(encoding="utf-8")
            self.assertNotRegex(
                product_text,
                r"(?m)^\s*(?:import requests\b|from requests\b)",
                f"Requests must remain outside product source: {path.name}",
            )
            self.assertNotIn("extract_zipped_paths", product_text, path.name)

    def test_detect_secrets_uses_selected_hash_locked_interpreter(self):
        config = PRECOMMIT_CONFIG.read_text(encoding="utf-8")
        ci_lock = CI_LOCK.read_text(encoding="utf-8")
        linux = LINUX_FULL_GATE.read_text(encoding="utf-8")
        windows = WINDOWS_FULL_GATE.read_text(encoding="utf-8")

        self.assertNotIn("github.com/Yelp/detect-secrets", config)
        self.assertRegex(
            config,
            r"repo:\s*local[\s\S]*?id:\s*detect-secrets[\s\S]*?"
            r"entry:\s*python -m detect_secrets\.pre_commit_hook[\s\S]*?"
            r"language:\s*system",
        )
        self.assertRegex(
            ci_lock,
            r"(?m)^detect-secrets==1\.5\.0\s+\\\n"
            r"\s+--hash=sha256:[0-9a-f]{64}",
        )
        self.assertIn("import sys; print(sys.executable)", linux)
        self.assertIn('export PATH="$(dirname "$SelectedPython"):$PATH"', linux)
        self.assertIn("import sys; print(sys.executable)", windows)
        self.assertIn("[IO.Path]::PathSeparator", windows)
        self.assertIn("$env:PATH", windows)

        mutations = (
            config.replace("language: system", "language: python", 1),
            ci_lock.replace("detect-secrets==1.5.0", "detect-secrets-unlocked", 1),
            linux.replace('export PATH="$(dirname "$SelectedPython"):$PATH"', "", 1),
            windows.replace("[IO.Path]::PathSeparator", "", 1),
        )
        self.assertIn("language: python", mutations[0])
        self.assertNotRegex(mutations[1], r"(?m)^detect-secrets==1\.5\.0")
        self.assertNotIn('export PATH="$(dirname "$SelectedPython"):$PATH"', mutations[2])
        self.assertNotIn("[IO.Path]::PathSeparator", mutations[3])

    def test_mutations_are_detected(self):
        mutations = (
            self.text.replace("needs: validate", "needs: []", 1),
            self.text.replace("@11bd71901bbe5b1630ceea73d27597364c9af683", "@v4", 1),
            self.text.replace("persist-credentials: false", "persist-credentials: true", 1),
            self.text.replace("--require-hashes --only-binary=:all:", "", 1),
            self.text.replace("validate_publish_candidate.py archive", "validator_disabled", 1),
            self.text.replace("--check-registry", "--registry-check-disabled", 1),
            self.text.replace("github.repository_owner == 'rookiestar28'", "true", 1),
            self.text.replace(
                "- name: Run hosted Linux diagnostics",
                "- name: Run hosted Linux diagnostics\n        env:\n          LEAK: ${{ secrets.REGISTRY_ACCESS_TOKEN }}",
                1,
            ),
        )
        for mutation in mutations:
            with self.subTest(digest=hash(mutation)):
                self.assertTrue(audit_workflow(mutation))


if __name__ == "__main__":
    unittest.main()

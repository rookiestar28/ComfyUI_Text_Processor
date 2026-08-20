# E2E Testing Notice

<!-- CURRENT-TEST-GOVERNANCE:START -->
## Current Governance Scope

A change limited to pure text/documentation files, a version-field-only `pyproject.toml` update, or
both does not enter this E2E workflow and requires no planning, roadmap item, record/log,
independent review, documentation test contract, browser installation, or full gate. Behavior-
bearing metadata changes do not qualify. For non-exempt work, applicable E2E runs through the
authoritative Windows Full Gate. Hosted CI repetitions are optional diagnostics and are not
acceptance prerequisites or pushed-commit evidence. Explicit item-scoped live/supported-host checks
remain separate when required.
<!-- CURRENT-TEST-GOVERNANCE:END -->

Mandatory testing-design rule:

- E2E tests must be designed to reproduce real user-visible failures and catch bugs early, not merely to pass validation.
- Do not add pass-only E2E checks that cannot fail for the bug class under review.
- For every user-reported or high-risk frontend regression, ask which E2E assertion would have caught it before release, then add or update that assertion.
All integration or end-to-end validation for this repository must follow `tests/E2E_TESTING_SOP.md`.

## Repo-specific Scope

This repository contains a tracked Node.js 18+ Playwright harness. Its foundational
contracts validate frontend precision and extension safety; runtime extensions use
the same mandatory lane.

Every change outside the text/version-only-`pyproject.toml` fast-path must run:

- module load behavior
- node registration
- changed-node runtime behavior
- image/tensor shape and channel contracts where applicable
- `npm test` for browser precision, interaction, event, and extension safety

Use repo-local `.tmp/` npm cache, browser, and temp paths. Do not allow Playwright or
npm validation to write browser/test caches outside the workspace.

## Exception

Changes whose complete tracked scope is limited to pure text/documentation files,
a version-field-only `pyproject.toml` update, or both do not enter the E2E workflow
and require no prior plan, roadmap item, record, command log, or independent review.

Dependency, build, tool-configuration, entry-point, packaging, or runtime-semantic
changes in `pyproject.toml` are behavior-bearing and do not qualify. If product code,
tests, executable scripts, generated runtime artifacts, or other behavior-bearing
files also change, this exception does not apply.

## Evidence Requirement

Implementation records must state one of:

- `E2E lane passed`
- `E2E lane not applicable: text/version-only-pyproject fast-path`
- `E2E lane blocked`, with the exact missing dependency or infrastructure

Route-load-only or import-only evidence is not sufficient for changed node behavior. Include at least one assertion against the final output contract of the changed node.
<!-- ROOKIEUI-GLOBAL-E2E-NOTICE:START -->
## RookieUI-Derived Global E2E Notice

All E2E tests must follow `tests/E2E_TESTING_SOP.md`. Full acceptance workflow and gate order remain defined by `tests/TEST_SOP.md`.

Mandatory testing-design rule:

- E2E tests must be designed to reproduce real user-visible failures and catch bugs early, not merely to pass validation.
- Do not add pass-only E2E checks that cannot fail for the bug class under review.
- For every user-reported or high-risk frontend regression, ask which E2E assertion would have caught it before release, then add or update that assertion.

Exception:

- pure text/documentation and/or version-field-only `pyproject.toml` changes do not enter E2E
- once other code/tests/scripts/generated/runtime files change, this exception does not apply

For transaction-sensitive features, acceptance evidence must include at least one action-level assertion of final outcome, not route-load evidence only.
<!-- ROOKIEUI-GLOBAL-E2E-NOTICE:END -->

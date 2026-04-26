# E2E Testing Notice

Mandatory testing-design rule:

- E2E tests must be designed to reproduce real user-visible failures and catch bugs early, not merely to pass validation.
- Do not add pass-only E2E checks that cannot fail for the bug class under review.
- For every user-reported or high-risk frontend regression, ask which E2E assertion would have caught it before release, then add or update that assertion.
All integration or end-to-end validation for this repository must follow `tests/E2E_TESTING_SOP.md`.

## Repo-specific Scope

This repository does not currently contain:

- frontend JavaScript or TypeScript extension files
- `package.json`
- Playwright configuration
- a browser-based test harness

Therefore `npm test` and Playwright browser E2E are not applicable for the current repo state.

## Required Replacement Lane

Use the ComfyUI custom-node smoke/integration lane in `tests/E2E_TESTING_SOP.md`.

That lane verifies the custom node pack at the ComfyUI integration boundary:

- module load behavior
- node registration
- changed-node runtime behavior
- image/tensor shape and channel contracts where applicable

## Exception

Strict documentation-only changes do not require entering the E2E workflow.

Once product code, tests, scripts, packaging, or runtime configuration changes, this exception does not apply.

## Evidence Requirement

Implementation records must state one of:

- `E2E lane passed`
- `E2E lane not applicable: documentation-only change`
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

- strictly documentation-only changes do not require entering the E2E workflow
- once code/tests/scripts/config/runtime files change, this exception does not apply

For transaction-sensitive features, acceptance evidence must include at least one action-level assertion of final outcome, not route-load evidence only.
<!-- ROOKIEUI-GLOBAL-E2E-NOTICE:END -->

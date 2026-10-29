"""Shared offline source observations; these facades do not execute ComfyUI."""
import copy
import json
from pathlib import Path


MATRIX_PATH = Path(__file__).parent / "fixtures/host_compatibility_matrix_v1.json"


def host_matrix():
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def host_tiers():
    matrix = host_matrix()
    return [
        {**matrix["contracts"], **tier,
         "core_version": tier["core"]["version"],
         "frontend_version": tier["frontend"]["version"]}
        for tier in matrix["tiers"]
    ]


def replay_output(ui, output_root, *, assets_enabled, cached=False):
    """Narrow authored contract for additive descriptor enrichment and cache replay.

    Not a host emulator: storage, policy, asset DB and media probing are excluded.
    Invalid paths are refused by this assertion boundary, never opened.
    """
    result = copy.deepcopy(ui)
    root = output_root.resolve()
    for descriptor in result.get("images", []):
        if not isinstance(descriptor, dict):
            raise AssertionError("image descriptor must be a mapping")
        if not {"filename", "subfolder", "type"} <= descriptor.keys():
            raise AssertionError("missing legacy descriptor fields")
        if descriptor["type"] != "output":
            raise AssertionError("this contract expects output descriptors")
        candidate = (root / descriptor["subfolder"] / descriptor["filename"]).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise AssertionError("descriptor must resolve to a contained existing file")
        if cached:
            descriptor.pop("id", None)
            descriptor.pop("preview_id", None)
        if assets_enabled:
            descriptor.update(id="contract-asset", preview_id="contract-preview")
    return result


def assert_custom_ui_preserved(original, replayed):
    for key, value in original.items():
        if key != "images" and replayed.get(key) != value:
            raise AssertionError(f"custom UI lost during replay: {key}")

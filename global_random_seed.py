"""Precision-safe global seed orchestration for ComfyUI prompts."""

from __future__ import annotations

import copy
import logging
import secrets
from collections.abc import Callable
from typing import Any


NODE_ID = "Global_RandomSeed"
EVENT_NAME = "text-processor-global-random-seed"
PROMPT_HANDLER_MARKER = "_text_processor_global_random_seed_handler"

SEED_WIDTH_MAXIMA = {
    "uint32": 4_294_967_295,
    "uint53": 9_007_199_254_740_991,
    "uint64": 18_446_744_073_709_551_615,
}
TIMINGS = ("before_generation", "after_generation")
QUEUE_ACTIONS = ("fixed", "increment", "decrement", "randomize")
DISTRIBUTIONS = ("same", "increment", "decrement", "randomize")
TARGET_INPUT_NAMES = ("seed", "noise_seed", "seed_num")

RandomSource = Callable[[int], int]


def _range_size(seed_width: str) -> int:
    try:
        return SEED_WIDTH_MAXIMA[seed_width] + 1
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported seed width: {seed_width!r}") from exc


def normalize_seed(value: str, seed_width: str) -> int:
    """Parse a canonical unsigned decimal string and normalize it to the width."""
    if not isinstance(value, str) or not value:
        raise ValueError("seed must be a canonical unsigned decimal string")
    if value != "0" and (value.startswith("0") or not value.isascii()):
        raise ValueError("seed must be a canonical unsigned decimal string")
    if not value.isdecimal():
        raise ValueError("seed must be a canonical unsigned decimal string")
    return int(value) % _range_size(seed_width)


def _random_seed(seed_width: str, random_source: RandomSource | None) -> int:
    source = random_source or secrets.randbelow
    size = _range_size(seed_width)
    value = source(size)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < size:
        raise ValueError("random source returned a value outside the requested range")
    return value


def apply_queue_action(
    value: int,
    action: str,
    seed_width: str,
    *,
    random_source: RandomSource | None = None,
) -> int:
    size = _range_size(seed_width)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("queue action value must be an integer")
    value %= size
    if action == "fixed":
        return value
    if action == "increment":
        return (value + 1) % size
    if action == "decrement":
        return (value - 1) % size
    if action == "randomize":
        return _random_seed(seed_width, random_source)
    raise ValueError(f"unsupported queue action: {action!r}")


def _node_id_sort_key(node_id: Any) -> tuple[int, int | str, str]:
    text = str(node_id)
    if text.isascii() and text.isdecimal():
        return 0, int(text), text
    return 1, text, text


def _validated_choice(value: Any, allowed: tuple[str, ...], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"unsupported {label}: {value!r}")
    return value


def _target_fields(node: Any) -> list[str]:
    if not isinstance(node, dict):
        return []
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        return []
    return [
        name
        for name in TARGET_INPUT_NAMES
        if name in inputs
        and isinstance(inputs[name], int)
        and not isinstance(inputs[name], bool)
    ]


def _distributed_seed(
    applied_seed: int,
    target_index: int,
    distribution: str,
    seed_width: str,
    random_source: RandomSource | None,
) -> int:
    size = _range_size(seed_width)
    if distribution == "same":
        return applied_seed
    if distribution == "increment":
        return (applied_seed + target_index) % size
    if distribution == "decrement":
        return (applied_seed - target_index) % size
    if distribution == "randomize":
        return _random_seed(seed_width, random_source)
    raise ValueError(f"unsupported distribution: {distribution!r}")


def _plan_prompt_mutation(
    json_data: Any,
    random_source: RandomSource | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    if not isinstance(json_data, dict):
        raise ValueError("prompt envelope must be an object")
    prompt = json_data.get("prompt")
    if not isinstance(prompt, dict):
        raise ValueError("prompt must be an object")

    controller_ids = [
        node_id
        for node_id, node in prompt.items()
        if isinstance(node, dict) and node.get("class_type") == NODE_ID
    ]
    if not controller_ids:
        return json_data, None, None

    controller_ids.sort(key=_node_id_sort_key)
    controller_id = controller_ids[0]
    controller = prompt[controller_id]
    inputs = controller.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("controller inputs must be an object")

    seed_width = _validated_choice(
        inputs.get("seed_width"), tuple(SEED_WIDTH_MAXIMA), "seed width"
    )
    timing = _validated_choice(inputs.get("timing"), TIMINGS, "timing")
    queue_action = _validated_choice(
        inputs.get("queue_action"), QUEUE_ACTIONS, "queue action"
    )
    distribution = _validated_choice(
        inputs.get("distribution"), DISTRIBUTIONS, "distribution"
    )
    current_seed = normalize_seed(inputs.get("value"), seed_width)
    normalize_seed(inputs.get("last_seed"), seed_width)

    acted_seed = apply_queue_action(
        current_seed,
        queue_action,
        seed_width,
        random_source=random_source,
    )
    if timing == "before_generation":
        applied_seed = acted_seed
        next_value = acted_seed
    else:
        applied_seed = current_seed
        next_value = acted_seed

    target_plans = []
    controller_id_set = {str(item) for item in controller_ids}
    target_ids = sorted(prompt, key=_node_id_sort_key)
    for target_id in target_ids:
        if str(target_id) in controller_id_set:
            continue
        fields = _target_fields(prompt[target_id])
        if not fields:
            continue
        assigned_seed = _distributed_seed(
            applied_seed,
            len(target_plans),
            distribution,
            seed_width,
            random_source,
        )
        target_plans.append((target_id, fields, assigned_seed))

    result = copy.deepcopy(json_data)
    result_prompt = result["prompt"]
    result_controller_inputs = result_prompt[controller_id]["inputs"]
    result_controller_inputs["value"] = str(applied_seed)
    result_controller_inputs["last_seed"] = str(applied_seed)

    event_targets = []
    for target_id, fields, assigned_seed in target_plans:
        result_inputs = result_prompt[target_id]["inputs"]
        event_inputs = []
        for field in fields:
            result_inputs[field] = assigned_seed
            event_inputs.append({"name": field, "seed": str(assigned_seed)})
        event_targets.append({"node_id": str(target_id), "inputs": event_inputs})

    client_id = None
    # CRITICAL: on-prompt handlers run before Core copies the request's top-level
    # client_id into extra_data; keep the fallback for direct/API host seams.
    candidate = json_data.get("client_id")
    if not isinstance(candidate, str) or not candidate:
        extra_data = json_data.get("extra_data")
        candidate = (
            extra_data.get("client_id") if isinstance(extra_data, dict) else None
        )
    if isinstance(candidate, str) and candidate:
        client_id = candidate

    event = None
    if client_id is not None:
        event = {
            "controller_id": str(controller_id),
            "seed_width": seed_width,
            "timing": timing,
            "queue_action": queue_action,
            "distribution": distribution,
            "applied_seed": str(applied_seed),
            "next_value": str(next_value),
            "targets": event_targets,
        }
    return result, event, client_id


def build_prompt_handler(
    prompt_server: Any,
    *,
    random_source: RandomSource | None = None,
):
    def on_prompt(json_data):
        try:
            result, event, client_id = _plan_prompt_mutation(
                json_data, random_source
            )
        except Exception:
            logging.warning(
                "[Global Random Seed] Prompt validation or derivation failed; "
                "the original prompt was preserved."
            )
            return json_data

        if event is not None and client_id is not None:
            try:
                prompt_server.send_sync(EVENT_NAME, event, client_id)
            except Exception:
                logging.warning(
                    "[Global Random Seed] Client readback event failed; "
                    "backend prompt assignment remains valid."
                )
        return result

    setattr(on_prompt, PROMPT_HANDLER_MARKER, True)
    return on_prompt


def register_prompt_server_hook(
    prompt_server: Any,
    *,
    random_source: RandomSource | None = None,
):
    handlers = getattr(prompt_server, "on_prompt_handlers", None)
    add_handler = getattr(prompt_server, "add_on_prompt_handler", None)
    if not isinstance(handlers, list) or not callable(add_handler):
        return None
    for handler in handlers:
        if getattr(handler, PROMPT_HANDLER_MARKER, False):
            return handler
    handler = build_prompt_handler(prompt_server, random_source=random_source)
    add_handler(handler)
    return handler


def register_available_prompt_server():
    # CRITICAL: keep this optional; direct server imports break package discovery
    # outside a running ComfyUI host.
    try:
        from server import PromptServer
    except (ImportError, ModuleNotFoundError):
        return None
    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None:
        return None
    return register_prompt_server_hook(prompt_server)


class GlobalRandomSeed:
    DESCRIPTION = (
        "Applies one bounded global seed to recognized literal seed inputs before "
        "execution, with exact uint32 or uint53 public profiles. Legacy uint64 "
        "workflows remain backend-compatible."
    )
    SEARCH_ALIASES = [
        "global seed",
        "random seed",
        "全域種子",
        "隨機種子",
    ]
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("applied_seed",)
    OUTPUT_TOOLTIPS = ("The exact bounded seed applied to this controller run.",)
    FUNCTION = "apply_seed"
    CATEGORY = "ComfyUI Text Processor/Logic"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (
                    "STRING",
                    {
                        "default": "0",
                        "tooltip": "Current seed as an exact unsigned decimal string.",
                    },
                ),
                "seed_width": (
                    ["uint32", "uint53"],
                    {
                        "default": "uint32",
                        "tooltip": (
                            "uint32 is the safe default; uint53 is the largest "
                            "JavaScript-safe selectable range. Legacy uint64 "
                            "workflows remain backend-compatible."
                        ),
                    },
                ),
                "timing": (
                    list(TIMINGS),
                    {
                        "default": "before_generation",
                        "tooltip": "Apply the queue action before or after this prompt.",
                    },
                ),
                "queue_action": (
                    list(QUEUE_ACTIONS),
                    {
                        "default": "fixed",
                        "tooltip": "How the controller value advances between prompts.",
                    },
                ),
                "distribution": (
                    list(DISTRIBUTIONS),
                    {
                        "default": "same",
                        "tooltip": "How one applied seed is distributed across target nodes.",
                    },
                ),
                "last_seed": (
                    "STRING",
                    {
                        "default": "0",
                        "tooltip": "Exact decimal readback of the last applied seed.",
                    },
                ),
            }
        }

    def apply_seed(
        self,
        value,
        seed_width,
        timing,
        queue_action,
        distribution,
        last_seed,
    ):
        _validated_choice(timing, TIMINGS, "timing")
        _validated_choice(queue_action, QUEUE_ACTIONS, "queue action")
        _validated_choice(distribution, DISTRIBUTIONS, "distribution")
        normalize_seed(last_seed, seed_width)
        return (normalize_seed(value, seed_width),)


NODE_CLASS_MAPPINGS = {NODE_ID: GlobalRandomSeed}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_ID: "Global Random Seed"}

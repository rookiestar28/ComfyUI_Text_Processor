import copy
import importlib
import json
import sys
import types
import unittest
from pathlib import Path

try:
    from test_host_compatibility_contracts import PackageImportContext
except ModuleNotFoundError:
    from tests.test_host_compatibility_contracts import PackageImportContext


REPO_DIR = Path(__file__).resolve().parents[1]
HOST_TIERS_PATH = REPO_DIR / "tests" / "fixtures" / "global_random_seed_host_tiers_v1.json"


class _SequenceRandom:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self, upper_exclusive):
        value = next(self.values)
        if value < 0 or value >= upper_exclusive:
            raise ValueError("synthetic random value is outside the requested range")
        return value


class _FailingRandom:
    def __init__(self):
        self.calls = 0

    def __call__(self, _upper_exclusive):
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("synthetic derivation failure")
        return 1


class _FakePromptServer:
    def __init__(self):
        self.on_prompt_handlers = []
        self.sent = []

    def add_on_prompt_handler(self, handler):
        self.on_prompt_handlers.append(handler)

    def send_sync(self, event, data, sid=None):
        self.sent.append((event, data, sid))


def _controller(
    value="7",
    seed_width="uint32",
    timing="before_generation",
    queue_action="fixed",
    distribution="same",
    last_seed="0",
):
    return {
        "class_type": "Global_RandomSeed",
        "inputs": {
            "value": value,
            "seed_width": seed_width,
            "timing": timing,
            "queue_action": queue_action,
            "distribution": distribution,
            "last_seed": last_seed,
        },
    }


def _envelope(prompt, client_id="client-a"):
    data = {"prompt": prompt}
    if client_id is not None:
        data["client_id"] = client_id
    return data


class GlobalRandomSeedDomainTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module("global_random_seed")
        except ModuleNotFoundError as exc:
            self.fail(f"F18 production module is missing: {exc}")

    def test_reproduction_and_uint32_profile_prevent_consumer_overflow(self):
        module = self.module()

        def uint32_consumer(value):
            if not 0 <= value <= 4294967295:
                raise ValueError("uint32 consumer rejected seed")
            return value

        with self.assertRaisesRegex(ValueError, "uint32 consumer rejected"):
            uint32_consumer(4294967296)

        bounded = module.normalize_seed("4294967296", "uint32")
        self.assertEqual(0, bounded)
        self.assertEqual(0, uint32_consumer(bounded))

    def test_exact_range_boundaries_and_import_normalization(self):
        module = self.module()
        cases = {
            ("0", "uint32"): 0,
            ("1", "uint32"): 1,
            ("4294967295", "uint32"): 4294967295,
            ("4294967296", "uint32"): 0,
            ("0", "uint64"): 0,
            ("18446744073709551615", "uint64"): 18446744073709551615,
            ("18446744073709551616", "uint64"): 0,
        }
        for (value, width), expected in cases.items():
            with self.subTest(value=value, width=width):
                self.assertEqual(expected, module.normalize_seed(value, width))

        for invalid in ("", "-1", "+1", " 1", "1 ", "1.0", "1e2"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    module.normalize_seed(invalid, "uint32")
        with self.assertRaises(ValueError):
            module.normalize_seed(True, "uint32")
        with self.assertRaises(ValueError):
            module.normalize_seed("1", "uint16")

    def test_increment_decrement_wrap_and_random_endpoints(self):
        module = self.module()
        self.assertEqual(0, module.apply_queue_action(4294967295, "increment", "uint32"))
        self.assertEqual(4294967295, module.apply_queue_action(0, "decrement", "uint32"))
        self.assertEqual(
            18446744073709551615,
            module.apply_queue_action(0, "decrement", "uint64"),
        )
        self.assertEqual(
            0,
            module.apply_queue_action(
                1, "randomize", "uint64", random_source=_SequenceRandom([0])
            ),
        )
        self.assertEqual(
            18446744073709551615,
            module.apply_queue_action(
                1,
                "randomize",
                "uint64",
                random_source=_SequenceRandom([18446744073709551615]),
            ),
        )

    def test_node_v1_contract_and_full_width_output(self):
        module = self.module()
        node = module.GlobalRandomSeed
        required = node.INPUT_TYPES()["required"]
        self.assertEqual(
            [
                "value",
                "seed_width",
                "timing",
                "queue_action",
                "distribution",
                "last_seed",
            ],
            list(required),
        )
        self.assertEqual("uint32", required["seed_width"][1]["default"])
        self.assertEqual(("INT",), node.RETURN_TYPES)
        self.assertEqual(("applied_seed",), node.RETURN_NAMES)
        self.assertEqual("apply_seed", node.FUNCTION)
        self.assertEqual("ComfyUI Text Processor/Logic", node.CATEGORY)
        self.assertTrue(node.OUTPUT_NODE)
        self.assertEqual(
            (18446744073709551615,),
            node().apply_seed(
                "18446744073709551615",
                "uint64",
                "before_generation",
                "fixed",
                "same",
                "18446744073709551615",
            ),
        )

    def test_production_schema_matches_the_frozen_t07_contract(self):
        module = self.module()
        frozen = json.loads(
            (
                REPO_DIR
                / "tests"
                / "fixtures"
                / "global_random_seed_contract_v1.json"
            ).read_text(encoding="utf-8")
        )
        required = module.GlobalRandomSeed.INPUT_TYPES()["required"]
        self.assertEqual(frozen["node_id"], module.NODE_ID)
        self.assertEqual(
            frozen["display_name"],
            module.NODE_DISPLAY_NAME_MAPPINGS[module.NODE_ID],
        )
        self.assertEqual(frozen["category"], module.GlobalRandomSeed.CATEGORY)
        self.assertEqual(
            [widget["name"] for widget in frozen["widgets"]],
            list(required),
        )
        self.assertEqual(
            frozen["seed_width"]["default"],
            required["seed_width"][1]["default"],
        )
        self.assertEqual(
            int(frozen["seed_width"]["profiles"]["uint32"]["maximum"]),
            module.SEED_WIDTH_MAXIMA["uint32"],
        )
        self.assertEqual(
            int(frozen["seed_width"]["profiles"]["uint64"]["maximum"]),
            module.SEED_WIDTH_MAXIMA["uint64"],
        )

    def test_runtime_source_uses_only_official_frontend_seams(self):
        source = (REPO_DIR / "web" / "global_random_seed.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('from "../../scripts/app.js"', source)
        self.assertIn('from "../../scripts/api.js"', source)
        self.assertIn("app.registerExtension(", source)
        self.assertIn("api.addEventListener(", source)
        for forbidden in (
            "api.queuePrompt =",
            "app.queuePrompt =",
            "app.graphToPrompt =",
            ".prototype.",
            "eval(",
            "innerHTML",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


class GlobalRandomSeedPromptTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module("global_random_seed")
        except ModuleNotFoundError as exc:
            self.fail(f"F18 production module is missing: {exc}")

    def run_hook(self, data, random_source=None):
        module = self.module()
        server = _FakePromptServer()
        handler = module.build_prompt_handler(server, random_source=random_source)
        return handler(data), server

    def test_before_and_after_generation_semantics(self):
        for timing, expected_applied, expected_next in (
            ("before_generation", "8", "8"),
            ("after_generation", "7", "8"),
        ):
            with self.subTest(timing=timing):
                data = _envelope(
                    {
                        "1": _controller(timing=timing, queue_action="increment"),
                        "2": {"class_type": "Sampler", "inputs": {"seed": 99}},
                    }
                )
                result, server = self.run_hook(data)
                self.assertEqual(expected_applied, result["prompt"]["1"]["inputs"]["value"])
                self.assertEqual(int(expected_applied), result["prompt"]["2"]["inputs"]["seed"])
                event = server.sent[0][1]
                self.assertEqual(expected_applied, event["applied_seed"])
                self.assertEqual(expected_next, event["next_value"])

    def test_all_action_timing_distribution_combinations_are_bounded(self):
        module = self.module()
        for width in ("uint32", "uint64"):
            maximum = module.SEED_WIDTH_MAXIMA[width]
            for timing in module.TIMINGS:
                for action in module.QUEUE_ACTIONS:
                    for distribution in module.DISTRIBUTIONS:
                        with self.subTest(
                            width=width,
                            timing=timing,
                            action=action,
                            distribution=distribution,
                        ):
                            random_values = [maximum, 0, maximum, 1, 2, 3]
                            data = _envelope(
                                {
                                    "1": _controller(
                                        value=str(maximum),
                                        seed_width=width,
                                        timing=timing,
                                        queue_action=action,
                                        distribution=distribution,
                                    ),
                                    "2": {"class_type": "A", "inputs": {"seed": 0}},
                                    "3": {"class_type": "B", "inputs": {"noise_seed": 0}},
                                }
                            )
                            result, _server = self.run_hook(
                                data, random_source=_SequenceRandom(random_values)
                            )
                            for node_id, field in (("2", "seed"), ("3", "noise_seed")):
                                assigned = result["prompt"][node_id]["inputs"][field]
                                self.assertTrue(0 <= assigned <= maximum)

    def test_stable_order_one_seed_per_node_and_allowlisted_literals_only(self):
        data = _envelope(
            {
                "10": _controller(value="100", distribution="increment"),
                "11": {
                    "class_type": "Target",
                    "inputs": {"seed": 1, "noise_seed": 2, "other": 3},
                },
                "2": {
                    "class_type": "Target",
                    "inputs": {
                        "seed": 1,
                        "noise_seed": True,
                        "seed_num": ["5", 0],
                    },
                },
                "alpha": {
                    "class_type": "Target",
                    "inputs": {"seed_num": 4, "seed": "5", "other": 6.0},
                },
            }
        )
        result, server = self.run_hook(data)
        self.assertEqual(100, result["prompt"]["2"]["inputs"]["seed"])
        self.assertIs(True, result["prompt"]["2"]["inputs"]["noise_seed"])
        self.assertEqual(["5", 0], result["prompt"]["2"]["inputs"]["seed_num"])
        self.assertEqual(101, result["prompt"]["11"]["inputs"]["seed"])
        self.assertEqual(101, result["prompt"]["11"]["inputs"]["noise_seed"])
        self.assertEqual(3, result["prompt"]["11"]["inputs"]["other"])
        self.assertEqual(102, result["prompt"]["alpha"]["inputs"]["seed_num"])
        self.assertEqual("5", result["prompt"]["alpha"]["inputs"]["seed"])
        targets = server.sent[0][1]["targets"]
        self.assertEqual(["2", "11", "alpha"], [target["node_id"] for target in targets])

    def test_lowest_controller_is_deterministic_and_all_controllers_are_skipped(self):
        data = _envelope(
            {
                "10": _controller(value="10"),
                "3": _controller(value="3"),
                "2": {"class_type": "Target", "inputs": {"seed": 0}},
            }
        )
        result, server = self.run_hook(data)
        self.assertEqual(3, result["prompt"]["2"]["inputs"]["seed"])
        self.assertEqual("3", server.sent[0][1]["controller_id"])
        self.assertEqual("10", result["prompt"]["10"]["inputs"]["value"])

    def test_atomic_rollback_on_derivation_failure(self):
        original = _envelope(
            {
                "1": _controller(distribution="randomize"),
                "2": {"class_type": "A", "inputs": {"seed": 0}},
                "3": {"class_type": "B", "inputs": {"seed": 0}},
            }
        )
        before = copy.deepcopy(original)
        result, server = self.run_hook(original, random_source=_FailingRandom())
        self.assertIs(result, original)
        self.assertEqual(before, original)
        self.assertEqual([], server.sent)

    def test_anonymous_api_prompt_mutates_without_event_or_global_state(self):
        data = _envelope(
            {
                "1": _controller(value="4294967296"),
                "2": {"class_type": "Target", "inputs": {"seed": 0}},
            },
            client_id=None,
        )
        result, server = self.run_hook(data)
        self.assertEqual(0, result["prompt"]["2"]["inputs"]["seed"])
        self.assertEqual([], server.sent)
        module = self.module()
        forbidden = {"client_states", "last_seeds", "seed_by_client"}
        self.assertTrue(forbidden.isdisjoint(vars(module)))

    def test_client_scoped_minimal_event_and_full_uint64_json_exactness(self):
        maximum = "18446744073709551615"
        data = _envelope(
            {
                "1": _controller(value=maximum, seed_width="uint64"),
                "2": {"class_type": "Target", "inputs": {"seed": 0}},
            },
            client_id="client-b",
        )
        result, server = self.run_hook(data)
        self.assertEqual(18446744073709551615, result["prompt"]["2"]["inputs"]["seed"])
        self.assertEqual(1, len(server.sent))
        event_name, payload, sid = server.sent[0]
        self.assertEqual("text-processor-global-random-seed", event_name)
        self.assertEqual("client-b", sid)
        self.assertEqual(
            {
                "controller_id",
                "seed_width",
                "timing",
                "queue_action",
                "distribution",
                "applied_seed",
                "next_value",
                "targets",
            },
            set(payload),
        )
        encoded = json.dumps(payload)
        decoded = json.loads(encoded)
        self.assertEqual(maximum, decoded["applied_seed"])
        self.assertNotIn("client-b", encoded)
        for forbidden in ("prompt", "workflow", "path", "credential", "cookie"):
            self.assertNotIn(forbidden, encoded.lower())

    def test_real_host_queue_shape_routes_top_level_client_id(self):
        data = {
            "prompt": {
                "1": _controller(
                    value="9",
                    timing="before_generation",
                    queue_action="increment",
                ),
                "2": {"class_type": "Target", "inputs": {"seed": 0}},
            },
            "client_id": "browser-client",
        }
        result, server = self.run_hook(data)
        self.assertEqual(10, result["prompt"]["2"]["inputs"]["seed"])
        self.assertEqual(1, len(server.sent))
        self.assertEqual("browser-client", server.sent[0][2])
        self.assertEqual("10", server.sent[0][1]["applied_seed"])

    def test_hook_registration_is_idempotent(self):
        module = self.module()
        server = _FakePromptServer()
        first = module.register_prompt_server_hook(server)
        second = module.register_prompt_server_hook(server)
        self.assertIs(first, second)
        self.assertEqual(1, len(server.on_prompt_handlers))
        self.assertTrue(
            getattr(server.on_prompt_handlers[0], module.PROMPT_HANDLER_MARKER, False)
        )

    def test_hook_registration_remains_idempotent_across_module_reload(self):
        module = self.module()
        server = _FakePromptServer()
        first = module.register_prompt_server_hook(server)
        reloaded = importlib.reload(module)
        second = reloaded.register_prompt_server_hook(server)
        self.assertIs(first, second)
        self.assertEqual(1, len(server.on_prompt_handlers))

    def test_same_server_routes_consecutive_clients_without_cross_talk(self):
        module = self.module()
        server = _FakePromptServer()
        handler = module.build_prompt_handler(server)
        for client_id, value in (("client-a", "7"), ("client-b", "19")):
            handler(
                _envelope(
                    {
                        "1": _controller(value=value),
                        "2": {"class_type": "Target", "inputs": {"seed": 0}},
                    },
                    client_id=client_id,
                )
            )
        self.assertEqual(["client-a", "client-b"], [entry[2] for entry in server.sent])
        self.assertEqual(
            ["7", "19"], [entry[1]["applied_seed"] for entry in server.sent]
        )
        self.assertNotEqual(server.sent[0][1], server.sent[1][1])


class GlobalRandomSeedHostTierTests(unittest.TestCase):
    def test_real_package_registers_and_runs_on_both_pinned_host_seams(self):
        tiers = json.loads(HOST_TIERS_PATH.read_text(encoding="utf-8"))["tiers"]
        self.assertEqual(
            [
                ("desktop_floor", "0.22.3", "1.43.18"),
                ("current_host", "0.29.0", "1.49.1"),
            ],
            [
                (
                    tier["id"],
                    tier["core_version"],
                    tier["frontend_version"],
                )
                for tier in tiers
            ],
        )
        for tier in tiers:
            self.assertEqual(
                "add_on_prompt_handler(handler)", tier["prompt_handler_api"]
            )
            self.assertEqual("send_sync(event, data, sid)", tier["event_api"])
            self.assertEqual("app.registerExtension", tier["extension_api"])
            self.assertEqual("api.addEventListener", tier["client_event_api"])

        for tier in tiers:
            with self.subTest(tier=tier["id"]):
                fake_server = _FakePromptServer()
                server_module = types.ModuleType("server")
                server_module.PromptServer = type(
                    "PromptServer", (), {"instance": fake_server}
                )
                previous_server = sys.modules.get("server")
                sys.modules["server"] = server_module
                try:
                    for name in list(sys.modules):
                        if name == "ComfyUI_Text_Processor" or name.startswith(
                            "ComfyUI_Text_Processor."
                        ):
                            sys.modules.pop(name)
                    with PackageImportContext() as package:
                        self.assertIn(
                            "Global_RandomSeed", package.NODE_CLASS_MAPPINGS
                        )
                        self.assertEqual(1, len(fake_server.on_prompt_handlers))
                        result = fake_server.on_prompt_handlers[0](
                            _envelope(
                                {
                                    "1": _controller(value="12"),
                                    "2": {
                                        "class_type": "Sampler",
                                        "inputs": {"seed": 0},
                                    },
                                },
                                client_id=f"{tier['id']}-client",
                            )
                        )
                        self.assertEqual(
                            12, result["prompt"]["2"]["inputs"]["seed"]
                        )
                        self.assertEqual(
                            f"{tier['id']}-client", fake_server.sent[0][2]
                        )
                finally:
                    if previous_server is None:
                        sys.modules.pop("server", None)
                    else:
                        sys.modules["server"] = previous_server


if __name__ == "__main__":
    unittest.main()

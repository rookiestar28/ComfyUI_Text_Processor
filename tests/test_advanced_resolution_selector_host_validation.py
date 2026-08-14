import inspect
import unittest

try:
    import advanced_resolution_selector as adapter
except ModuleNotFoundError:
    from .. import advanced_resolution_selector as adapter


PUBLIC_OPTIONS = ["1:1", "9:7", "4:3", "19:13", "3:2", "7:4", "16:9", "custom"]
EXECUTABLE_OPTIONS = PUBLIC_OPTIONS + ["21:9"]
SUPPORTED_HOST_TIERS = ("current_core_0.29.0", "desktop_floor_core_0.22.3")


def _values(**overrides):
    values = {
        "output_mode": "fixed",
        "aspect_ratio": "1:1",
        "direction": "landscape",
        "custom_ratio_width": 1,
        "custom_ratio_height": 1,
        "megapixels": 1.0,
        "multiple": 8,
        "seed": 0,
    }
    values.update(overrides)
    return values


def _host_preflight(node_class, values):
    """Model the shared V1 host ownership/validation seam without executing Core."""

    inputs = node_class.INPUT_TYPES()["required"]
    validator = getattr(node_class, "VALIDATE_INPUTS", None)
    owned = set(inspect.signature(validator).parameters) if validator is not None else set()

    for input_name, spec in inputs.items():
        if input_name in owned:
            continue
        raw_type, options = spec
        value = values[input_name]
        if isinstance(raw_type, (tuple, list)) and value not in raw_type:
            return False, "value_not_in_list"
        if raw_type == "INT" and not isinstance(value, int):
            return False, "invalid_input_type"
        if raw_type == "FLOAT" and not isinstance(value, (int, float)):
            return False, "invalid_input_type"
        if "min" in options and value < options["min"]:
            return False, "value_smaller_than_min"
        if "max" in options and value > options["max"]:
            return False, "value_bigger_than_max"

    if validator is not None:
        result = validator(**{name: values[name] for name in owned})
        if result is not True:
            return False, str(result)
    return True, None


class AdvancedResolutionSelectorHostValidationTests(unittest.TestCase):
    def test_validator_owns_only_aspect_ratio_on_both_supported_tiers(self):
        validator = getattr(adapter.AdvancedResolutionSelector, "VALIDATE_INPUTS", None)
        self.assertIsNotNone(validator)
        self.assertEqual(["aspect_ratio"], list(inspect.signature(validator).parameters))
        self.assertNotIn("**kwargs", str(inspect.signature(validator)))
        for tier in SUPPORTED_HOST_TIERS:
            with self.subTest(tier=tier):
                self.assertEqual(
                    ["aspect_ratio"], list(inspect.signature(validator).parameters)
                )

    def test_legacy_ratio_passes_host_preflight_and_reaches_fixed_execution(self):
        node = adapter.AdvancedResolutionSelector()
        for tier in SUPPORTED_HOST_TIERS:
            with self.subTest(tier=tier):
                values = _values(aspect_ratio="21:9")
                self.assertEqual((True, None), _host_preflight(type(node), values))
                result = node.select_resolution(**values)
                self.assertEqual("21:9", result["result"][2])

    def test_legacy_ratio_passes_host_preflight_and_reaches_randomize_execution(self):
        node = adapter.AdvancedResolutionSelector()
        for tier in SUPPORTED_HOST_TIERS:
            with self.subTest(tier=tier):
                values = _values(output_mode="randomize", aspect_ratio="21:9")
                self.assertEqual((True, None), _host_preflight(type(node), values))
                result = node.select_resolution(**values)
                self.assertEqual("21:9", result["result"][2])

    def test_host_validator_exact_allowlist_rejects_unknown_content_safely(self):
        validator = getattr(adapter.AdvancedResolutionSelector, "VALIDATE_INPUTS", None)
        self.assertIsNotNone(validator)
        for value in EXECUTABLE_OPTIONS:
            with self.subTest(value=value):
                self.assertIs(validator(value), True)
        unknown = "2:1"
        result = validator(unknown)
        self.assertIsInstance(result, str)
        self.assertNotIn(unknown, result)

    def test_unknown_ratio_fails_before_host_execution_or_rng(self):
        values = _values(output_mode="randomize_all", aspect_ratio="2:1")
        valid, reason = _host_preflight(adapter.AdvancedResolutionSelector, values)
        self.assertFalse(valid)
        self.assertTrue(reason)

    def test_unrelated_inputs_remain_host_owned(self):
        for input_name, invalid_value in (
            ("output_mode", "unsupported"),
            ("direction", "diagonal"),
            ("megapixels", 16.1),
            ("multiple", 129),
            ("seed", 4294967296),
        ):
            values = _values(**{input_name: invalid_value})
            with self.subTest(input_name=input_name):
                valid, reason = _host_preflight(adapter.AdvancedResolutionSelector, values)
                self.assertFalse(valid)
                self.assertIn(reason, {"value_not_in_list", "value_bigger_than_max"})


if __name__ == "__main__":
    unittest.main()

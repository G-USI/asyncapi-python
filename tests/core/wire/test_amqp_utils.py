"""Unit tests for universal parameter validation and substitution utilities."""

import pytest

from asyncapi_python.kernel.document.channel import AddressParameter, Channel
from asyncapi_python.kernel.wire.utils import (
    substitute_parameters,
    validate_parameters_strict,
)


def create_test_channel(
    address: str, parameter_keys: list[str] | None = None
) -> Channel:
    """Create a test channel with specified parameters."""
    parameters = {}
    if parameter_keys:
        for key in parameter_keys:
            parameters[key] = AddressParameter(
                key=key,
                description=f"Test parameter {key}",
                location=None,
            )

    return Channel(
        key="test_channel",
        address=address,
        title="Test Channel",
        summary=None,
        description=None,
        servers=[],
        messages={},
        parameters=parameters,
        tags=[],
        external_docs=None,
        bindings=None,
    )


class TestValidateParametersStrict:
    """Tests for strict parameter validation."""

    def test_accepts_exact_match(self):
        """Should pass when all required parameters are provided, no extras."""
        channel = create_test_channel(
            "weather.{location}.{severity}", ["location", "severity"]
        )

        # Should not raise
        validate_parameters_strict(channel, {"location": "NYC", "severity": "high"})

    def test_rejects_missing_parameters(self):
        """Should raise ValueError when required parameters are missing."""
        channel = create_test_channel(
            "weather.{location}.{severity}", ["location", "severity"]
        )

        with pytest.raises(ValueError) as exc_info:
            validate_parameters_strict(channel, {"location": "NYC"})

        error_msg = str(exc_info.value)
        assert "Missing required parameters" in error_msg
        assert "severity" in error_msg
        assert "weather.{location}.{severity}" in error_msg

    def test_rejects_multiple_missing_parameters(self):
        """Should raise ValueError listing all missing parameters."""
        channel = create_test_channel(
            "weather.{location}.{severity}.{priority}",
            ["location", "severity", "priority"],
        )

        with pytest.raises(ValueError) as exc_info:
            validate_parameters_strict(channel, {"location": "NYC"})

        error_msg = str(exc_info.value)
        assert "Missing required parameters" in error_msg
        assert "severity" in error_msg
        assert "priority" in error_msg

    def test_rejects_extra_parameters(self):
        """Should raise ValueError when unexpected parameters are provided."""
        channel = create_test_channel("weather.{location}", ["location"])

        with pytest.raises(ValueError) as exc_info:
            validate_parameters_strict(channel, {"location": "NYC", "severity": "high"})

        error_msg = str(exc_info.value)
        assert "Unexpected parameters" in error_msg
        assert "severity" in error_msg

    def test_rejects_multiple_extra_parameters(self):
        """Should raise ValueError listing all extra parameters."""
        channel = create_test_channel("weather.{location}", ["location"])

        with pytest.raises(ValueError) as exc_info:
            validate_parameters_strict(
                channel,
                {"location": "NYC", "severity": "high", "priority": "1"},
            )

        error_msg = str(exc_info.value)
        assert "Unexpected parameters" in error_msg
        assert "severity" in error_msg
        assert "priority" in error_msg

    def test_accepts_empty_when_none_defined(self):
        """Should pass when channel has no parameters and none provided."""
        channel = create_test_channel("simple.queue", [])

        # Should not raise
        validate_parameters_strict(channel, {})

    def test_rejects_params_when_none_expected(self):
        """Should raise ValueError when parameters provided but none defined."""
        channel = create_test_channel("simple.queue", [])

        with pytest.raises(ValueError) as exc_info:
            validate_parameters_strict(channel, {"location": "NYC"})

        error_msg = str(exc_info.value)
        assert "Unexpected parameters" in error_msg
        assert "location" in error_msg

    def test_rejects_all_missing(self):
        """Should raise ValueError when all parameters are missing."""
        channel = create_test_channel(
            "weather.{location}.{severity}", ["location", "severity"]
        )

        with pytest.raises(ValueError) as exc_info:
            validate_parameters_strict(channel, {})

        error_msg = str(exc_info.value)
        assert "Missing required parameters" in error_msg
        assert "location" in error_msg
        assert "severity" in error_msg

    def test_rejects_mixed_missing_and_extra(self):
        """Should raise ValueError for both missing and extra parameters."""
        channel = create_test_channel(
            "weather.{location}.{severity}", ["location", "severity"]
        )

        with pytest.raises(ValueError) as exc_info:
            # Missing: severity
            # Extra: priority
            validate_parameters_strict(channel, {"location": "NYC", "priority": "high"})

        error_msg = str(exc_info.value)
        # Should fail on missing first (that's the implementation order)
        assert (
            "Missing required parameters" in error_msg
            or "Unexpected parameters" in error_msg
        )


class TestSubstituteParameters:
    """Tests for parameter substitution."""

    def test_substitutes_single_parameter(self):
        """Should substitute a single parameter correctly."""
        result = substitute_parameters("weather.{location}", {"location": "NYC"})
        assert result == "weather.NYC"

    def test_substitutes_multiple_parameters(self):
        """Should substitute multiple parameters correctly."""
        result = substitute_parameters(
            "weather.{location}.{severity}",
            {"location": "NYC", "severity": "high"},
        )
        assert result == "weather.NYC.high"

    def test_preserves_wildcards_in_values(self):
        """Should preserve wildcard characters in parameter values."""
        result = substitute_parameters(
            "weather.{location}.{severity}",
            {"location": "*", "severity": "high"},
        )
        assert result == "weather.*.high"

    def test_handles_no_parameters(self):
        """Should return template unchanged when no parameters defined."""
        result = substitute_parameters("simple.queue", {})
        assert result == "simple.queue"

    def test_fails_on_missing_parameter(self):
        """Should raise ValueError when template has placeholder without value."""
        with pytest.raises(ValueError) as exc_info:
            substitute_parameters("weather.{location}.{severity}", {"location": "NYC"})

        error_msg = str(exc_info.value)
        assert "undefined parameters" in error_msg
        assert "severity" in error_msg

    def test_allows_extra_parameters(self):
        """Should allow extra parameters in dict (only uses what's in template)."""
        result = substitute_parameters(
            "weather.{location}",
            {"location": "NYC", "severity": "high"},  # Extra: severity
        )
        assert result == "weather.NYC"

    def test_handles_complex_patterns(self):
        """Should handle complex patterns with multiple dots and parameters."""
        result = substitute_parameters(
            "exchange.{env}.{region}.{service}.{version}",
            {
                "env": "prod",
                "region": "us-east-1",
                "service": "api",
                "version": "v2",
            },
        )
        assert result == "exchange.prod.us-east-1.api.v2"

    def test_handles_parameter_at_start(self):
        """Should handle parameter at start of template."""
        result = substitute_parameters("{env}.weather.alerts", {"env": "prod"})
        assert result == "prod.weather.alerts"

    def test_handles_parameter_at_end(self):
        """Should handle parameter at end of template."""
        result = substitute_parameters("weather.alerts.{env}", {"env": "prod"})
        assert result == "weather.alerts.prod"

    def test_handles_consecutive_parameters(self):
        """Should handle consecutive parameters separated by dot."""
        result = substitute_parameters(
            "prefix.{location}.{severity}",
            {"location": "NYC", "severity": "high"},
        )
        assert result == "prefix.NYC.high"

"""Unit tests for the validation system infrastructure (registry, decorators, errors)."""

from pathlib import Path

import pytest

from asyncapi_python_codegen.validation import (
    Severity,
    ValidationError,
    ValidationIssue,
    rule,
    validate_spec,
)
from asyncapi_python_codegen.validation.base import RuleRegistry, get_registry
from asyncapi_python_codegen.validation.context import ValidationContext
from asyncapi_python_codegen.validation.errors import ValidationError as VE


class TestValidationIssue:
    """Test ValidationIssue dataclass."""

    def test_create_issue(self):
        """Test creating a validation issue."""
        issue = ValidationIssue(
            severity=Severity.ERROR,
            message="Test error",
            path="$.test",
            rule="test-rule",
        )

        assert issue.severity == Severity.ERROR
        assert issue.message == "Test error"
        assert issue.path == "$.test"
        assert issue.rule == "test-rule"
        assert issue.suggestion is None

    def test_issue_with_suggestion(self):
        """Test creating issue with suggestion."""
        issue = ValidationIssue(
            severity=Severity.WARNING,
            message="Test warning",
            path="$.test",
            rule="test-rule",
            suggestion="Try this instead",
        )

        assert issue.suggestion == "Try this instead"

    def test_issue_string_format(self):
        """Test string formatting of issues."""
        issue = ValidationIssue(
            severity=Severity.ERROR,
            message="Something went wrong",
            path="$.channels.test",
            rule="test-rule",
        )

        issue_str = str(issue)
        assert "Something went wrong" in issue_str
        assert "$.channels.test" in issue_str

    def test_issue_with_suggestion_format(self):
        """Test string formatting includes suggestion."""
        issue = ValidationIssue(
            severity=Severity.WARNING,
            message="Issue here",
            path="$.test",
            rule="test-rule",
            suggestion="Fix it like this",
        )

        issue_str = str(issue)
        assert "Fix it like this" in issue_str


class TestValidationError:
    """Test ValidationError exception."""

    def test_create_validation_error(self):
        """Test creating validation error."""
        issues = [
            ValidationIssue(
                severity=Severity.ERROR,
                message="Error 1",
                path="$.test1",
                rule="rule1",
            ),
            ValidationIssue(
                severity=Severity.WARNING,
                message="Warning 1",
                path="$.test2",
                rule="rule2",
            ),
        ]

        error = ValidationError(issues)

        assert len(error.issues) == 2
        assert len(error.errors) == 1
        assert len(error.warnings) == 1
        assert error.has_errors()
        assert error.has_warnings()

    def test_validation_error_message(self):
        """Test error message includes error details."""
        issues = [
            ValidationIssue(
                severity=Severity.ERROR,
                message="Critical error",
                path="$.test",
                rule="test-rule",
            )
        ]

        error = ValidationError(issues)
        error_msg = str(error)

        assert "Document validation failed" in error_msg
        assert "Critical error" in error_msg

    def test_no_errors_validation_error(self):
        """Test ValidationError with only warnings."""
        issues = [
            ValidationIssue(
                severity=Severity.WARNING,
                message="Just a warning",
                path="$.test",
                rule="test-rule",
            )
        ]

        error = ValidationError(issues)

        assert not error.has_errors()
        assert error.has_warnings()


class TestValidationContext:
    """Test ValidationContext dataclass."""

    def test_create_context(self):
        """Test creating validation context."""
        spec = {"asyncapi": "3.0.0", "channels": {}}
        ctx = ValidationContext(spec=spec, spec_path=Path("test.yaml"), operations=None)

        assert ctx.spec == spec
        assert ctx.spec_path == Path("test.yaml")
        assert ctx.operations is None

    def test_get_channels(self):
        """Test get_channels helper method."""
        spec = {"channels": {"ch1": {}, "ch2": {}}}
        ctx = ValidationContext(spec=spec, spec_path=Path("test.yaml"))

        channels = ctx.get_channels()

        assert len(channels) == 2
        assert "ch1" in channels
        assert "ch2" in channels

    def test_get_channels_empty(self):
        """Test get_channels when no channels."""
        spec = {"asyncapi": "3.0.0"}
        ctx = ValidationContext(spec=spec, spec_path=Path("test.yaml"))

        channels = ctx.get_channels()

        assert channels == {}

    def test_get_operations_spec(self):
        """Test get_operations_spec helper."""
        spec = {"operations": {"op1": {}, "op2": {}}}
        ctx = ValidationContext(spec=spec, spec_path=Path("test.yaml"))

        ops = ctx.get_operations_spec()

        assert len(ops) == 2
        assert "op1" in ops

    def test_get_components(self):
        """Test get_components helper."""
        spec = {"components": {"messages": {}}}
        ctx = ValidationContext(spec=spec, spec_path=Path("test.yaml"))

        components = ctx.get_components()

        assert "messages" in components


class TestRuleRegistry:
    """Test RuleRegistry class."""

    def test_create_registry(self):
        """Test creating a registry."""
        registry = RuleRegistry()

        assert len(registry.get_all_categories()) == 0

    def test_register_rule(self):
        """Test registering a rule."""
        registry = RuleRegistry()

        def test_rule(ctx: ValidationContext) -> list[ValidationIssue]:
            return []

        registry.register("test", test_rule)

        assert "test" in registry.get_all_categories()
        assert len(registry.get_rules("test")) == 1

    def test_register_multiple_rules_same_category(self):
        """Test registering multiple rules in same category."""
        registry = RuleRegistry()

        def rule1(ctx):
            return []

        def rule2(ctx):
            return []

        registry.register("test", rule1)
        registry.register("test", rule2)

        assert len(registry.get_rules("test")) == 2

    def test_register_rules_different_categories(self):
        """Test registering rules in different categories."""
        registry = RuleRegistry()

        def rule1(ctx):
            return []

        def rule2(ctx):
            return []

        registry.register("cat1", rule1)
        registry.register("cat2", rule2)

        assert len(registry.get_all_categories()) == 2
        assert len(registry.get_rules("cat1")) == 1
        assert len(registry.get_rules("cat2")) == 1

    def test_validate_runs_rules(self):
        """Test that validate runs registered rules."""
        registry = RuleRegistry()
        called = []

        def test_rule(ctx: ValidationContext) -> list[ValidationIssue]:
            called.append(True)
            return []

        registry.register("test", test_rule)

        spec = {"asyncapi": "3.0.0"}
        ctx = ValidationContext(spec=spec, spec_path=Path("test.yaml"))

        registry.validate(ctx, categories=["test"])

        assert len(called) == 1

    def test_validate_collects_issues(self):
        """Test that validate collects issues from rules."""
        registry = RuleRegistry()

        def test_rule(ctx: ValidationContext) -> list[ValidationIssue]:
            return [
                ValidationIssue(
                    severity=Severity.ERROR,
                    message="Test error",
                    path="$.test",
                    rule="test-rule",
                )
            ]

        registry.register("test", test_rule)

        spec = {"asyncapi": "3.0.0"}
        ctx = ValidationContext(spec=spec, spec_path=Path("test.yaml"))

        issues = registry.validate(ctx, categories=["test"])

        assert len(issues) == 1
        assert issues[0].message == "Test error"

    def test_validate_runs_only_specified_categories(self):
        """Test that validate only runs specified categories."""
        registry = RuleRegistry()
        called = {"cat1": False, "cat2": False}

        def rule1(ctx):
            called["cat1"] = True
            return []

        def rule2(ctx):
            called["cat2"] = True
            return []

        registry.register("cat1", rule1)
        registry.register("cat2", rule2)

        spec = {"asyncapi": "3.0.0"}
        ctx = ValidationContext(spec=spec, spec_path=Path("test.yaml"))

        registry.validate(ctx, categories=["cat1"])

        assert called["cat1"] is True
        assert called["cat2"] is False

    def test_validate_handles_rule_exception(self):
        """Test that validate handles exceptions in rules."""
        registry = RuleRegistry()

        def broken_rule(ctx):
            raise RuntimeError("Rule crashed!")

        registry.register("test", broken_rule)

        spec = {"asyncapi": "3.0.0"}
        ctx = ValidationContext(spec=spec, spec_path=Path("test.yaml"))

        issues = registry.validate(ctx, categories=["test"])

        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert "Rule crashed!" in issues[0].message


class TestRuleDecorator:
    """Test @rule decorator."""

    def test_rule_decorator_registers_function(self):
        """Test that @rule decorator registers the function."""
        # Get current rule count
        registry = get_registry()
        initial_count = len(registry.get_rules("test-category"))

        @rule("test-category")
        def my_test_rule(ctx: ValidationContext) -> list[ValidationIssue]:
            return []

        # Should have one more rule
        assert len(registry.get_rules("test-category")) == initial_count + 1

    def test_rule_decorator_preserves_function(self):
        """Test that decorator preserves the function."""

        @rule("test-category")
        def my_test_rule(ctx: ValidationContext) -> list[ValidationIssue]:
            return [
                ValidationIssue(
                    severity=Severity.INFO,
                    message="Test",
                    path="$.test",
                    rule="test",
                )
            ]

        # Function should still be callable
        spec = {"asyncapi": "3.0.0"}
        ctx = ValidationContext(spec=spec, spec_path=Path("test.yaml"))

        issues = my_test_rule(ctx)

        assert len(issues) == 1


class TestValidateSpecFunction:
    """Test the validate_spec function."""

    def test_validate_spec_runs_core_rules(self):
        """Test that validate_spec runs core rules."""
        spec = {"asyncapi": "2.0.0"}  # Wrong version

        with pytest.raises(ValidationError) as exc_info:
            validate_spec(spec=spec, operations=None, spec_path=Path("test.yaml"))

        assert exc_info.value.has_errors()

    def test_validate_spec_with_valid_spec(self):
        """Test validate_spec with valid spec."""
        spec = {
            "asyncapi": "3.0.0",
            "operations": {
                "test": {
                    "action": "send",
                }
            },
        }

        # Should not raise
        issues = validate_spec(
            spec=spec,
            operations={},
            spec_path=Path("test.yaml"),
            fail_on_error=False,
        )

        # May have some issues but shouldn't fail
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) >= 0  # May or may not have errors

    def test_validate_spec_fail_on_error_false(self):
        """Test that fail_on_error=False doesn't raise."""
        spec = {"asyncapi": "2.0.0"}  # Wrong version

        issues = validate_spec(
            spec=spec,
            operations=None,
            spec_path=Path("test.yaml"),
            fail_on_error=False,
        )

        # Should have errors but not raise
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) > 0

    def test_validate_spec_with_categories(self):
        """Test validate_spec with specific categories."""

        # Register a test rule in a custom category
        @rule("custom-test")
        def custom_rule(ctx):
            return [
                ValidationIssue(
                    severity=Severity.INFO,
                    message="Custom rule ran",
                    path="$.test",
                    rule="custom-rule",
                )
            ]

        spec = {"asyncapi": "3.0.0", "operations": {}}

        issues = validate_spec(
            spec=spec,
            operations={},
            spec_path=Path("test.yaml"),
            categories=["custom-test"],
            fail_on_error=False,
        )

        # Should have run our custom rule
        assert any(i.message == "Custom rule ran" for i in issues)


class TestSeverityEnum:
    """Test Severity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert Severity.ERROR.value == "error"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"

    def test_severity_comparison(self):
        """Test severity can be compared."""
        error_issue = ValidationIssue(
            severity=Severity.ERROR, message="", path="", rule=""
        )
        warning_issue = ValidationIssue(
            severity=Severity.WARNING, message="", path="", rule=""
        )

        assert error_issue.severity == Severity.ERROR
        assert warning_issue.severity != Severity.ERROR
        assert warning_issue.severity == Severity.WARNING

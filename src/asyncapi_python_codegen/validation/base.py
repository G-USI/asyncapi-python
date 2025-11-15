"""Base validation infrastructure: registry and decorators."""

from typing import Callable

from .context import ValidationContext
from .errors import Severity, ValidationIssue

# Type alias for validation rule functions
RuleFunction = Callable[[ValidationContext], list[ValidationIssue]]


class RuleRegistry:
    """Registry for validation rules organized by category."""

    def __init__(self):
        """Initialize empty registry."""
        self._rules: dict[str, list[RuleFunction]] = {}

    def register(self, category: str, rule_func: RuleFunction) -> RuleFunction:
        """
        Register a validation rule in a category.

        Args:
            category: Category name (e.g., "core", "protocol.amqp", "codegen")
            rule_func: Function that validates and returns issues

        Returns:
            The rule function (for decorator pattern)
        """
        if category not in self._rules:
            self._rules[category] = []

        self._rules[category].append(rule_func)
        return rule_func

    def get_rules(self, category: str) -> list[RuleFunction]:
        """Get all rules in a category."""
        return self._rules.get(category, [])

    def get_all_categories(self) -> list[str]:
        """Get list of all registered categories."""
        return list(self._rules.keys())

    def validate(
        self, context: ValidationContext, categories: list[str] | None = None
    ) -> list[ValidationIssue]:
        """
        Run validation rules and collect issues.

        Args:
            context: Validation context with document data
            categories: List of categories to validate (None = default: ["core", "protocol.amqp"])

        Returns:
            List of all validation issues found
        """
        issues: list[ValidationIssue] = []

        # Determine which categories to run
        if categories is None:
            # Default: validate core rules + AMQP protocol rules
            categories = ["core", "protocol.amqp"]

        # Run all rules in specified categories
        for category in categories:
            for rule_func in self.get_rules(category):
                try:
                    rule_issues = rule_func(context)
                    issues.extend(rule_issues)
                except Exception as e:
                    # If a rule crashes, report it as a validation issue
                    issues.append(
                        ValidationIssue(
                            severity=Severity.ERROR,
                            message=f"Validation rule '{rule_func.__name__}' failed: {e}",
                            path="$",
                            rule="rule-execution-error",
                        )
                    )

        return issues


# Global registry instance
_global_registry = RuleRegistry()


def rule(*tags: str) -> Callable[[RuleFunction], RuleFunction]:
    """
    Decorator to register a validation rule with one or more tags.

    Args:
        *tags: One or more tag names (e.g., "core", "protocol.amqp", "requires-amqp")

    Returns:
        Decorator function

    Example:
        @rule("core")
        def my_rule(ctx: ValidationContext) -> list[ValidationIssue]:
            if "asyncapi" not in ctx.spec:
                return [ValidationIssue(...)]
            return []

        @rule("core", "protocol.amqp")
        def amqp_rule(ctx: ValidationContext) -> list[ValidationIssue]:
            # AMQP-specific validation
            return []
    """

    def decorator(func: RuleFunction) -> RuleFunction:
        # Register function under ALL provided tags
        for tag in tags:
            _global_registry.register(tag, func)
        return func

    return decorator


def get_registry() -> RuleRegistry:
    """Get the global rule registry."""
    return _global_registry

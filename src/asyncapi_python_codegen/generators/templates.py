"""Template rendering and code formatting."""

import subprocess
import sys
from pathlib import Path
from typing import Any

from black import FileMode, format_str
from jinja2 import Environment, FileSystemLoader

from .routers import RouterInfo


class TemplateRenderer:
    """Handles Jinja2 template rendering and code formatting."""

    def __init__(self, template_dir: Path):
        """Initialize the template renderer."""
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Add custom filters
        self.env.filters["repr"] = repr
        self.env.filters["json_prefix"] = self._json_prefix_filter

        # Add custom functions for template
        self.env.globals.update(
            {  # type: ignore[arg-type]
                "generate_nested_routers": self._generate_nested_routers,
                "is_router_info": lambda x: isinstance(x, RouterInfo),  # type: ignore[misc]
            }
        )

    def render_file(
        self, template_name: str, output_path: Path, context: dict[str, Any]
    ) -> None:
        """Generate a file from template."""
        template = self.env.get_template(template_name)
        content = template.render(**context)

        # Always format with black - retry with different modes if needed
        formatted_content = self._format_with_black(content, template_name)

        output_path.write_text(formatted_content)
        print(f"  Generated: {output_path}")

    def _generate_nested_routers(
        self, routers_dict: dict[str, Any], indent: int = 2, router_type: str = ""
    ) -> str:
        """Generate nested router initialization code for templates with full path context."""
        return self._generate_nested_routers_with_prefix(
            routers_dict, indent, router_type, ""
        )

    def _generate_nested_routers_with_prefix(
        self,
        routers_dict: dict[str, Any],
        indent: int = 2,
        router_type: str = "",
        prefix: str = "",
    ) -> str:
        """Generate nested router initialization code with prefix tracking."""
        lines: list[str] = []
        indent_str = " " * indent

        for key, value in routers_dict.items():
            if isinstance(value, RouterInfo):
                # This is a router endpoint
                lines.append(
                    f"{indent_str}self.{key} = {value.class_name}(wire_factory, codec_factory)"
                )
            else:
                # This is a nested router level - create a sub-router class
                full_prefix = f"{prefix}.{key}" if prefix else key
                path_parts = full_prefix.split(".")
                class_name_parts = (
                    [router_type] + [part.title() for part in path_parts] + ["Router"]
                )
                subclass_name = "__".join(class_name_parts)
                lines.append(
                    f"{indent_str}self.{key} = {subclass_name}(wire_factory, codec_factory)"
                )

        return "\n".join(lines)

    def _json_prefix_filter(self, type_str: str) -> str:
        """Add json. prefix to message types, handling union types with | syntax."""
        if " | " in type_str:
            # Handle union types: "MarketTick | MarketDepth" -> "json.MarketTick | json.MarketDepth"
            types = [t.strip() for t in type_str.split(" | ")]
            return " | ".join(f"json.{t}" for t in types)
        else:
            # Handle single type: "MarketTick" -> "json.MarketTick"
            return f"json.{type_str}"

    def _format_with_black(self, content: str, filename: str) -> str:
        """Format content with Black, with fallback strategies."""
        # Try standard formatting first
        try:
            return format_str(content, mode=FileMode())
        except Exception as e1:
            print(f"  Warning: Standard Black formatting failed for {filename}: {e1}")

            # Try with different line length
            try:
                mode = FileMode(line_length=120)
                return format_str(content, mode=mode)
            except Exception as e2:
                print(
                    f"  Warning: Extended line Black formatting failed for {filename}: {e2}"
                )

                # Try to fix common syntax issues and retry
                try:
                    fixed_content = self._fix_common_syntax_issues(content)
                    return format_str(fixed_content, mode=FileMode())
                except Exception as e3:
                    print(
                        f"  Error: All Black formatting attempts failed for {filename}: {e3}"
                    )
                    print(f"  Raw content preview: {content[:200]}...")
                    # Return unformatted content rather than crash
                    return content

    def _fix_common_syntax_issues(self, content: str) -> str:
        """Fix common syntax issues that prevent Black from formatting."""
        lines = content.split("\n")
        fixed_lines: list[str] = []

        for line in lines:
            # Fix missing newlines between fields
            if (
                line.strip()
                and not line.startswith(" ")
                and not line.startswith('"""')
                and not line.startswith("class ")
                and not line.startswith("def ")
                and not line.startswith("from ")
                and not line.startswith("import ")
                and ":" in line
                and "=" not in line
                and len(fixed_lines) > 0
                and fixed_lines[-1].strip()
                and not fixed_lines[-1].strip().endswith(":")
            ):
                # This looks like a field without proper indentation/separation
                # Add proper indentation if missing
                if not line.startswith("    "):
                    line = "    " + line.strip()

            fixed_lines.append(line)

        return "\n".join(fixed_lines)

    def run_mypy(self, output_dir: Path) -> None:
        """Run mypy on generated code."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "mypy", str(output_dir)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("✅ Type checking passed")
            else:
                print(f"⚠️ Type checking warnings:\\n{result.stdout}")
        except Exception as e:
            print(f"⚠️ Could not run mypy: {e}")

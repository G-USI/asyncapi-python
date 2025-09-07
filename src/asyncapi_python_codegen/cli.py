#!/usr/bin/env python3
"""Command-line interface for AsyncAPI code generation."""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typer
else:
    try:
        import typer
    except ImportError:
        typer = None  # type: ignore[assignment]

from .generators import CodeGenerator

# Use try-catch to determine if typer is available
try:
    import typer  # noqa: F401 - imported for availability check

    _has_typer = True
except ImportError:
    _has_typer = False

if _has_typer:
    app = typer.Typer(help="AsyncAPI Python Code Generator")

    @app.command()
    def generate(
        spec_file: Path = typer.Argument(
            ..., help="Path to AsyncAPI YAML specification"
        ),
        output_dir: Path = typer.Argument(
            ..., help="Output directory for generated code"
        ),
        force: bool = typer.Option(False, "--force", help="Overwrite existing files"),
    ):
        """Generate Python code from AsyncAPI specification."""
        if not spec_file.exists():
            typer.echo(f"Error: Spec file {spec_file} does not exist", err=True)
            raise typer.Exit(1)

        typer.echo(f"Generating code from {spec_file} to {output_dir}...")

        try:
            generator = CodeGenerator()
            generator.generate(spec_file, output_dir, force=force)
            typer.echo("✅ Code generation complete!")
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

    def main():
        app()

else:
    # Fallback CLI without typer
    def main():
        if len(sys.argv) != 3:
            print("Usage: asyncapi-python-codegen <spec-file> <output-dir>")
            sys.exit(1)

        spec_file = Path(sys.argv[1])
        output_dir = Path(sys.argv[2])

        if not spec_file.exists():
            print(f"Error: Spec file {spec_file} does not exist")
            sys.exit(1)

        print(f"Generating code from {spec_file} to {output_dir}...")

        try:
            generator = CodeGenerator()
            generator.generate(spec_file, output_dir)
            print("✅ Code generation complete!")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()

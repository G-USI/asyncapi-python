"""Main code generator orchestrating all sub-generators."""

from pathlib import Path
from typing import Dict, Any

from ..parser import extract_all_operations, load_document_info
from .messages import MessageGenerator
from .routers import RouterGenerator
from .templates import TemplateRenderer


class CodeGenerator:
    """Generate Python code from AsyncAPI specifications using SRP."""

    def __init__(self):
        """Initialize the code generator with sub-generators."""
        template_dir = Path(__file__).parent.parent / "templates"
        self.template_renderer = TemplateRenderer(template_dir)
        self.message_generator = MessageGenerator()
        self.router_generator = RouterGenerator()

    def generate(self, spec_path: Path, output_dir: Path, force: bool = False) -> None:
        """Generate code from AsyncAPI spec.

        Args:
            spec_path: Path to AsyncAPI YAML file
            output_dir: Output directory for generated code
            force: If True, overwrite existing directory. If False, fail if directory exists.
        """
        # Check if output directory exists and handle force flag
        if output_dir.exists() and not force:
            raise ValueError(
                f"Output directory {output_dir} already exists. Use --force to overwrite."
            )
        elif output_dir.exists() and force:
            print(f"Warning: Overwriting existing directory {output_dir}")

        # Parse the spec
        print(f"Parsing {spec_path}...")
        operations = extract_all_operations(spec_path)
        doc_info = load_document_info(spec_path)

        # Build router information using SRP
        routers = self.router_generator.build_routers(operations)
        producer_routers, consumer_routers = self.router_generator.split_routers(routers)

        # Extract and generate message models using SRP
        messages = self.message_generator.extract_messages(operations)

        # Generate nested classes using SRP
        producer_nested_classes = self.router_generator.collect_nested_classes(producer_routers, router_type="Producer")
        consumer_nested_classes = self.router_generator.collect_nested_classes(consumer_routers, router_type="Consumer")

        # Prepare template context
        context = {
            # Document info
            "app_title": doc_info["title"],
            "app_description": doc_info["description"],
            "app_version": doc_info["version"],
            "asyncapi_version": doc_info["asyncapi_version"],
            # Routers
            "routers": routers,
            "producer_routers": producer_routers,
            "consumer_routers": consumer_routers,
            "producer_nested_classes": producer_nested_classes,
            "consumer_nested_classes": consumer_nested_classes,
            # Messages
            "messages": messages,
        }

        # Generate files using SRP
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate router.py
        self.template_renderer.render_file("router.py.j2", output_dir / "router.py", context)

        # Generate application.py
        self.template_renderer.render_file("application.py.j2", output_dir / "application.py", context)

        # Generate messages/json/__init__.py (for CodecRegistry compatibility)
        messages_json_dir = output_dir / "messages" / "json"
        messages_json_dir.mkdir(parents=True, exist_ok=True)
        self.template_renderer.render_file(
            "messages.py.j2", messages_json_dir / "__init__.py", context
        )

        # Generate __init__.py
        self.template_renderer.render_file("__init__.py.j2", output_dir / "__init__.py", context)

        print(f"✅ Generated code in {output_dir}")

        # Run mypy for validation using SRP
        self.template_renderer.run_mypy(output_dir)
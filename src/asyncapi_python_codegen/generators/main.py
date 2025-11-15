"""Main code generator orchestrating all sub-generators."""

from pathlib import Path

from ..parser import extract_all_operations, load_document_info
from .messages import MessageGenerator
from .parameters import ParameterGenerator
from .routers import RouterGenerator
from .templates import TemplateRenderer

# Type annotations removed - this module deals with dynamic YAML/JSON parsing


class CodeGenerator:
    """Generate Python code from AsyncAPI specifications using SRP."""

    def __init__(self):
        """Initialize the code generator with sub-generators."""
        template_dir = Path(__file__).parent.parent / "templates"
        self.template_renderer = TemplateRenderer(template_dir)
        self.message_generator = MessageGenerator()
        self.router_generator = RouterGenerator()
        self.parameter_generator = ParameterGenerator()

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
        producer_routers, consumer_routers = self.router_generator.split_routers(
            routers
        )

        # Generate message models using datamodel-code-generator
        message_models_code = self.message_generator.generate_message_models(
            operations, spec_path
        )

        # Generate parameter TypedDicts for parameterized channels
        parameter_models_code = self.parameter_generator.generate_parameter_models(
            list(operations.values())
        )

        # Legacy compatibility - extract messages for router generation
        messages = self.message_generator.extract_messages(operations)

        # Generate nested classes using SRP
        producer_nested_classes = self.router_generator.collect_nested_classes(
            producer_routers, router_type="Producer"
        )
        consumer_nested_classes = self.router_generator.collect_nested_classes(
            consumer_routers, router_type="Consumer"
        )

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
            "message_models_code": message_models_code,
            # Parameters
            "parameter_models_code": parameter_models_code,
        }

        # Generate files using SRP
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate router.py
        self.template_renderer.render_file(
            "router.py.j2", output_dir / "router.py", context
        )

        # Generate application.py
        self.template_renderer.render_file(
            "application.py.j2", output_dir / "application.py", context
        )

        # Generate messages/__init__.py for module structure
        messages_dir = output_dir / "messages"
        messages_dir.mkdir(parents=True, exist_ok=True)
        self.template_renderer.render_file(
            "messages_init.py.j2", messages_dir / "__init__.py", context
        )

        # Generate messages/json/__init__.py using datamodel-code-generator
        messages_json_dir = output_dir / "messages" / "json"
        messages_json_dir.mkdir(parents=True, exist_ok=True)
        self.template_renderer.render_file(
            "messages_datamodel.py.j2", messages_json_dir / "__init__.py", context
        )

        # Generate parameters/__init__.py with TypedDicts
        parameters_dir = output_dir / "parameters"
        parameters_dir.mkdir(parents=True, exist_ok=True)
        self.template_renderer.render_file(
            "parameters.py.j2", parameters_dir / "__init__.py", context
        )

        # Generate __init__.py
        self.template_renderer.render_file(
            "__init__.py.j2", output_dir / "__init__.py", context
        )

        print(f"✅ Generated code in {output_dir}")

        # Run mypy for validation using SRP
        self.template_renderer.run_mypy(output_dir)

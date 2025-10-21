from pants.backend.python.target_types import (
    InterpreterConstraintsField,
    PythonResolveField,
    PythonSourceField,
)
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    AsyncFieldMixin,
    Dependencies,
    GenerateSourcesRequest,
    MultipleSourcesField,
    StringField,
    Target,
)


class AsyncapiPythonInterpreterConstraints(InterpreterConstraintsField): ...


class AsyncapiPythonResolveField(PythonResolveField): ...


class AsyncapiServiceField(StringField):
    alias = "service"


class AsyncapiSourcesField(MultipleSourcesField, AsyncFieldMixin):
    expected_file_extensions = (".yaml", ".asyncapi.yaml")


class AsyncapiDependencies(Dependencies): ...


class AsyncapiServiceTarget(Target):
    alias = "asyncapi_python_service"
    help = "A single AsyncAPI file."
    core_fields = (
        *COMMON_TARGET_FIELDS,
        AsyncapiDependencies,
        AsyncapiSourcesField,
        AsyncapiServiceField,
        AsyncapiPythonInterpreterConstraints,
        AsyncapiPythonResolveField,
    )


class InjectAsyncapiDependencies(Target):
    inject_for = AsyncapiDependencies


class GeneratePythonFromAsyncapiRequest(GenerateSourcesRequest):
    input = AsyncapiSourcesField
    output = PythonSourceField

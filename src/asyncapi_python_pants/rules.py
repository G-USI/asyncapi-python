from pants.engine.internals.native_engine import (
    Digest,
    MergeDigests,
    RemovePrefix,
    AddPrefix,
    Snapshot,
)
from pants.core.util_rules.stripped_source_files import StrippedSourceFiles
from pants.core.util_rules.source_files import SourceFilesRequest
from pants.engine.target import (
    GeneratedSources,
    TransitiveTargets,
    TransitiveTargetsRequest,
)
from pants.engine.rules import rule, Get, MultiGet
from pants.engine.process import ProcessResult, Process
from pants.source.source_root import SourceRoot, SourceRootRequest
from pants.backend.python.util_rules.interpreter_constraints import (
    InterpreterConstraints,
)
from pants.backend.python.util_rules.pex import (
    Pex,
    PexRequest,
    PexRequirements,
)
from .targets import *


@rule
async def generate_python_from_asyncapi(
    request: GeneratePythonFromAsyncapiRequest,
) -> GeneratedSources:
    pex = await Get(
        Pex,
        PexRequest(
            output_filename="asyncapi-python-codegen.pex",
            internal_only=True,
            requirements=PexRequirements(
                [
                    # Include your plugin as a requirement so it's available in the PEX
                    "asyncapi_python_codegen",  # or whatever your package is called
                ]
            ),
            interpreter_constraints=InterpreterConstraints([">=3.9"]),
            # Make it executable by specifying the main module
            main="-m asyncapi_python_codegen",  # This makes it executable
        ),
    )
    transitive_targets = await Get(
        TransitiveTargets,
        TransitiveTargetsRequest([request.protocol_target.address]),
    )
    all_sources_stripped = await Get(
        StrippedSourceFiles,
        SourceFilesRequest(
            (tgt.get(AsyncapiSourcesField) for tgt in transitive_targets.closure),
            for_sources_types=(AsyncapiSourcesField,),
        ),
    )
    input_digest = await Get(
        Digest,
        MergeDigests(
            (
                all_sources_stripped.snapshot.digest,
                pex.digest,
            )
        ),
    )
    output_dir = "_generated_files"
    module_name = request.protocol_target.address.target_name

    # Now use Process with the executable PEX
    result = await Get(
        ProcessResult,
        Process(
            argv=[
                "./asyncapi-python-codegen.pex",  # Executable PEX
                "generate",  # Your CLI command
                request.protocol_target[AsyncapiServiceField].value or "",
                f"{output_dir}/{module_name}",
            ],
            description=f"Generating Python sources from {request.protocol_target.address}.",
            output_directories=(output_dir,),
            input_digest=input_digest,
        ),
    )
    source_root_request = SourceRootRequest.for_target(request.protocol_target)
    normalized_digest, source_root = await MultiGet(
        Get(Digest, RemovePrefix(result.output_digest, output_dir)),
        Get(SourceRoot, SourceRootRequest, source_root_request),
    )
    source_root_restored = (
        await Get(Snapshot, AddPrefix(normalized_digest, source_root.path))
        if source_root.path != "."
        else await Get(Snapshot, Digest, normalized_digest)
    )
    return GeneratedSources(source_root_restored)

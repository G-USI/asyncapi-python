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
    pex_filename = "asyncapi-python-codegen.pex"
    pex = await Get(
        Pex,
        PexRequest(
            output_filename=pex_filename,
            internal_only=True,
            requirements=PexRequirements(
                [
                    "asyncapi_python_codegen",
                ]
            ),
            interpreter_constraints=InterpreterConstraints([">=3.9"]),
            # Don't specify main - we'll handle execution manually
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

    # Execute the PEX with python and -m flag
    result = await Get(
        ProcessResult,
        Process(
            argv=[
                "python",  # Use python interpreter
                pex_filename,  # PEX file
                "-m",
                "asyncapi_python_codegen",  # Module execution
                "generate",  # CLI command
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

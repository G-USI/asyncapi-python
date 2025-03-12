from pants.core.util_rules.external_tool import (
    ExternalTool,
    ExternalToolRequest,
    DownloadedExternalTool,
)
from pants.engine.platform import Platform


class AsyncapiPython(ExternalTool):
    options_scope = "asyncapi-python-codegen"
    help = "The AsyncAPI 3 python compiler"
    default_version = "0.2.2"
    default_known_versions = [
        "0.1.2|linux_x86_64|6f433d87f3b509a94c20f98c686d4fcfc11902439f18b8660dc2a0f4bdb8e2de|37810935",
        "0.1.3|linux_x86_64|52cf1fdc09c98b795721ae09e09333b39324d96fe62ac074d96c782f175d0d7b|38031993",
        "0.1.4|linux_x86_64|cd192131d0df3cdbde4c140cbaa3e72a6344c66729c1148bcd61cf2c936d4a5f|38032009",
        "0.1.5|linux_x86_64|9d07e7ce9f9c006e5599825b791211a7c4974cce043e1fd6cb80081376fbcd89|38032262",
        "0.1.6|linux_x86_64|5d28a43f2e931a8954fefb906ee3fcb96a832639ee3160b40caa8c4e7a8a5dae|38032267",
        "0.2.0|linux_x86_64|a4e0aefd8d636b4ddf75768b891c29c8d99ca08c7018a1e53136784f1fc29794|38273562",
        "0.2.1|linux_x86_64|1206d8efd31cd007fbe582b0f47f0a0d5d8b406f7c30e040634c512d858e5bd6|38273228",
        "0.2.2|linux_x86_64|a36ad6609cd466bfb95880dd0656a5cc51bdcc5c4408cff68121482d32d3c338|38273219",
    ]

    def generate_url(self, _: Platform) -> str:
        return (
            "https://github.com/G-USI/asyncapi-python/releases/"
            f"download/v{self.version}/asyncapi-python-codegen-{self.version}.pex"
        )

    def generate_exe(self, _: Platform) -> str:
        return f"./asyncapi-python-codegen-{self.version}.pex"

{
  description = "AsyncAPI Python Code Generator - type-safe async Python from AsyncAPI 3 specs";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python310;
      in
      {
        devShells.default = pkgs.mkShell {
          name = "asyncapi-python";

          packages = with pkgs; [
            python
            uv
          ];

          shellHook = ''
            export UV_PYTHON_PREFERENCE=only-system

            if [ ! -d .venv ]; then
              echo "Creating virtual environment..."
              uv venv
            fi

            source .venv/bin/activate

            echo "AsyncAPI Python development environment"
            echo "Python: $(python --version)"
            echo "uv: $(uv --version)"
          '';
        };
      }
    );
}

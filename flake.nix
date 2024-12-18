{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };

  outputs = { self, nixpkgs }: let 
  pkgs = nixpkgs.legacyPackages.x86_64-linux; 
  pynetworktables = pkgs.python312Packages.buildPythonPackage rec {
      pname = "pynetworktables";
      version = "2021.0.0";
      src = pkgs.python312Packages.fetchPypi {
        inherit pname version;
        sha256 = "sha256-kRZ5SOZsKdXJD4Xz4klAP00uvxE2i5P5uWjvMVOIxzw=";
      };
  };
  in {
    devShells.x86_64-linux.default = pkgs.mkShell {
      buildInputs = with pkgs; [ python312 python312Packages.pygame pynetworktables ]; 
    };
  };
}

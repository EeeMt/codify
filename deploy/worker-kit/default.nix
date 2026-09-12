let
  nixpkgsLock = builtins.fromJSON (builtins.readFile ./nixpkgs.json);
  pinnedNixpkgs = builtins.fetchTarball {
    inherit (nixpkgsLock) url sha256;
  };
in
{ pkgs ? import pinnedNixpkgs {} }:

let
  codegraphPlatformPackage =
    if pkgs.stdenv.hostPlatform.isAarch64
    then "@colbymchenry/codegraph-linux-arm64"
    else "@colbymchenry/codegraph-linux-x64";
  nodeTools = pkgs.buildNpmPackage {
    pname = "codify-worker-kit-node-tools";
    version = "0.1.0";
    src = ./npm;
    npmDepsHash = "sha256-SyEIa/P9gxRbYjpMGxwNhOvSjIIdmGHEbGqJLGxcyNw=";
    dontNpmBuild = true;
    installPhase = ''
      runHook preInstall
      mkdir -p $out/lib/codify-node-tools
      cp -R node_modules $out/lib/codify-node-tools/
      rm -f $out/lib/codify-node-tools/node_modules/${codegraphPlatformPackage}/node
      cp ${./validate_mermaid_summary.mjs} \
        $out/lib/codify-node-tools/validate_mermaid_summary.mjs
      # Audited upstream Pi extension (MIT, pinned by package-lock). Its runtime
      # closure ships beside it so `-e` resolves without any network access at
      # Task time; Codify's own ceiling/agents are copied from
      # deploy/worker-cli/pi-subagents (open-harness-v2-subagent-adaptation.md
      # §6.4).
      mkdir -p $out/lib/codify-pi-subagents
      cp -R node_modules $out/lib/codify-pi-subagents/
      cp -R ${./pi-subagents-policy}/. $out/lib/codify-pi-subagents/
      chmod -R u+w $out/lib/codify-pi-subagents
      # Minimal, auditable vendor patch: pin depth-0 delegation launches to the
      # foreground path, because only a foreground launch returns the child
      # inventory (native run ids, usage, tool trace, final output) in its tool
      # result. Everything else about the upstream plugin is untouched.
      patch -p2 -d $out/lib/codify-pi-subagents/node_modules/pi-subagents \
        < ${./pi-subagents-policy/vendor/force-foreground.patch}
      runHook postInstall
    '';
  };
in
pkgs.symlinkJoin {
  name = "codify-worker-kit-runtime";
  passthru = {
    nixpkgsRevision = nixpkgsLock.rev;
    nixpkgsVersion = pkgs.lib.version;
  };
  paths = [
    pkgs.bashInteractive
    pkgs.cacert
    pkgs.coreutils
    pkgs.curl
    pkgs.findutils
    pkgs.gawk
    pkgs.git
    pkgs.gnugrep
    pkgs.gnused
    pkgs.gnutar
    pkgs.gzip
    pkgs.jq
    pkgs.nodejs_22
    pkgs.openssh
    pkgs.python312
    pkgs.ripgrep
    pkgs.which
    nodeTools
  ];
  nativeBuildInputs = [ pkgs.makeWrapper ];
  postBuild = ''
    rm -f $out/bin/codegraph
    makeWrapper ${pkgs.nodejs_22}/bin/node $out/bin/codegraph \
      --add-flags "$out/lib/codify-node-tools/node_modules/${codegraphPlatformPackage}/lib/dist/bin/codegraph.js"
    makeWrapper ${pkgs.nodejs_22}/bin/node $out/bin/codify-validate-mermaid \
      --add-flags "$out/lib/codify-node-tools/validate_mermaid_summary.mjs"
    # The Pi extension is loaded by absolute path (`pi -e <dir>`); the wrapper
    # keeps that path out of the Kit manifest so only the directory contents
    # (and therefore the adapter digest) matter.
    ln -sfn $out/lib/codify-pi-subagents "$out/bin/codify-pi-subagents"
  '';
}

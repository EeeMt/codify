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
    npmDepsHash = "sha256-wBQu/JeC6FufnssBBg69CqxjFsmhbWIbZPli15YQb2s=";
    npmInstallFlags = [ "--legacy-peer-deps" ];
    dontNpmBuild = true;
    nativeBuildInputs = [ pkgs.jq ];
    installPhase = ''
      runHook preInstall
      mkdir -p $out/lib/codify-node-tools
      cp -R node_modules $out/lib/codify-node-tools/
      rm -f $out/lib/codify-node-tools/node_modules/${codegraphPlatformPackage}/node
      cp ${./validate_mermaid_summary.mjs} \
        $out/lib/codify-node-tools/validate_mermaid_summary.mjs
      # Audited upstream Pi extensions (MIT, pinned by package-lock). Their
      # runtime closure ships beside them so `-e` resolves without any network
      # access at Task time; Codify's subagent ceiling and Todo pin are copied
      # from deploy/worker-cli/pi-subagents (open-harness-v2-subagent-
      # adaptation.md §6.4).
      mkdir -p $out/lib/codify-pi-subagents
      cp -R node_modules $out/lib/codify-pi-subagents/
      cp -R ${./pi-subagents-policy}/. $out/lib/codify-pi-subagents/
      chmod -R u+w $out/lib/codify-pi-subagents
      test -f $out/lib/codify-pi-subagents/node_modules/@juicesharp/rpiv-todo/index.ts
      # Minimal, auditable vendor patch: pin depth-0 delegation launches to the
      # foreground path, because only a foreground launch returns the child
      # inventory (native run ids, usage, tool trace, final output) in its tool
      # result. Everything else about the upstream plugin is untouched.
      patch -p2 -d $out/lib/codify-pi-subagents/node_modules/pi-subagents \
        < ${./pi-subagents-policy/vendor/force-foreground.patch}
      # pi-subagents publishes TypeScript source only. Compile the exact,
      # patched source tree at Kit build time while preserving its directory
      # layout: the extension resolves prompts, agents, and child runners via
      # import.meta.url, so a single-file bundle would break those paths.
      pi_source=$out/lib/codify-pi-subagents/node_modules/pi-subagents
      pi_compiled=$pi_source/compiled
      mkdir -p "$pi_compiled"
      find "$pi_source" -type f -name '*.ts' ! -name '*.d.ts' -print0 \
        | xargs -0 ./node_modules/.bin/esbuild \
            --format=esm --platform=node --target=node22 \
            --outdir="$pi_compiled" --outbase="$pi_source" --log-level=warning
      for asset in agents docs prompts skills async-retention-discovery-worker.mjs \
          inspector-runner.mjs runner-peer-preload.mjs; do
        if [ -e "$pi_source/$asset" ]; then
          cp -R "$pi_source/$asset" "$pi_compiled/$asset"
        fi
      done
      # Rewrite only module specifiers and the known child-script paths. Other
      # `.ts` strings are data (for example LSP language IDs and examples) and
      # must remain unchanged in the compiled runtime.
      PI_COMPILED="$pi_compiled" node --input-type=module <<'NODE'
      import { readdir, readFile, writeFile } from "node:fs/promises";
      import path from "node:path";

      const root = process.env.PI_COMPILED;
      const moduleSpecifier = /((?:\bfrom\s+|\bimport\s*\(\s*|\.import\s*\(\s*|\bimport\s+)["'][^"']+)\.ts(["'])/g;
      const childScriptPath = /\b(subagent-prompt-runtime|fanout-child|fast-mode-extension|subagent-runner|binary-bootstrap)\.ts\b/g;

      async function compiledFiles(directory) {
        const entries = await readdir(directory, { withFileTypes: true });
        const files = [];
        for (const entry of entries) {
          const file = path.join(directory, entry.name);
          if (entry.isDirectory()) {
            files.push(...await compiledFiles(file));
          } else if (entry.name.endsWith(".js") || entry.name.endsWith(".mjs")) {
            files.push(file);
          }
        }
        return files;
      }

      for (const file of await compiledFiles(root)) {
        const source = await readFile(file, "utf8");
        const updated = source
          .replace(moduleSpecifier, "$1.js$2")
          .replace(childScriptPath, "$1.js");
        if (updated !== source) {
          await writeFile(file, updated);
        }
      }
      NODE
      jq '
        .main = "./index.js" |
        .exports |= with_entries(.value |= sub("\\.ts$"; ".js")) |
        .pi.extensions = ["./index.js"] |
        .pi.skills = ["./skills"] |
        .pi.prompts = ["./prompts"]
      ' "$pi_source/package.json" > "$pi_compiled/package.json"
      test -f "$pi_compiled/index.js"
      test -f "$pi_compiled/src/inspectors/inspector-runner.js"
      test -f "$pi_compiled/package.json"
      ! grep -Fq 'inspector-runner.ts' "$pi_compiled/inspector-runner.mjs"
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

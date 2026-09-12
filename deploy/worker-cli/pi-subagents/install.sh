#!/bin/bash
# Install the audited upstream pi-subagents extension into a Kit payload root.
#
# Runs at Kit build time only: the task container never reaches the network for
# this payload. The closure is pinned by package-lock.json; a mismatch fails.
set -euo pipefail

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target_dir="${1:?usage: install.sh <target payload dir>}"
npm_bin="${NPM:-npm}"

: "${PI_SUBAGENTS_EXPECTED_VERSION:=0.67.0}"
: "${PI_SUBAGENTS_EXPECTED_SHA256:=1b4d7b0677289f84bb7ab2d8c45651ca0f833e65814c30f2a22b8c86b95aadfc}"

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

cp "${source_dir}/package.json" "${source_dir}/package-lock.json" "${work_dir}/"
# --ignore-scripts: the extension ships no build step and Kit builds never run
# third-party lifecycle scripts.
(cd "${work_dir}" && "${npm_bin}" ci --omit=dev --no-audit --no-fund --ignore-scripts)

installed_version="$(jq -r '.version' "${work_dir}/node_modules/pi-subagents/package.json")"
if [ "${installed_version}" != "${PI_SUBAGENTS_EXPECTED_VERSION}" ]; then
    echo "pi-subagents version mismatch: ${installed_version} != ${PI_SUBAGENTS_EXPECTED_VERSION}" >&2
    exit 1
fi

mkdir -p "${target_dir}"
cp -R "${work_dir}/node_modules/pi-subagents" "${target_dir}/pi-subagents"
cp -R "${work_dir}/node_modules" "${target_dir}/pi-subagents/node_modules"
cp "${source_dir}/config.json" "${target_dir}/pi-subagents/config.json"
cp "${source_dir}/settings.json" "${target_dir}/pi-subagents/settings.json"
cp "${source_dir}/pin.json" "${target_dir}/pi-subagents/pin.json"
cp "${source_dir}/LICENSE.pi-subagents" "${target_dir}/pi-subagents/LICENSE"
mkdir -p "${target_dir}/pi-subagents/agents"
cp "${source_dir}/agents/"*.md "${target_dir}/pi-subagents/agents/"

# The extension entry is index.ts and must not be swapped for a mutable
# dist/ build; record the upstream tarball digest alongside the extracted tree.
echo "pi-subagents ${installed_version} staged at ${target_dir}/pi-subagents (tarball sha256 ${PI_SUBAGENTS_EXPECTED_SHA256})"

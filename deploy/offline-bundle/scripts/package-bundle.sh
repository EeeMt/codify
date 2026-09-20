#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$(cd "${ROOT_DIR}/.." && pwd)"
OUTPUT_ARCHIVE="${DEPLOY_DIR}/codify-offline-bundle.tar.gz"
TMP_ARCHIVE="${DEPLOY_DIR}/.codify-offline-bundle.tar.gz.tmp"
STAGING_DIR=""

# Kit trees extract with read-only directories (0555) and files (0444). A
# non-root cleanup cannot unlink entries from a read-only directory, so grant
# write permission first; this only touches a temporary copy.
remove_tree() {
    chmod -R u+w "$1" 2>/dev/null || true
    rm -rf "$1"
}

# Keep archives that must not ship (other releases, legacy names) out of the
# staged bundle while leaving them in kits/ on the build machine.
drop_from_staging() {
    local archive
    for archive in "$@"; do
        rm -f "${STAGING_DIR}/offline-bundle/kits/${archive}" \
            "${STAGING_DIR}/offline-bundle/kits/${archive}.sha256"
    done
}

cleanup() {
    if [[ -n "${STAGING_DIR}" ]]; then
        remove_tree "${STAGING_DIR}"
    fi
}
trap cleanup EXIT

if ! compgen -G "${ROOT_DIR}/images/codify-offline-images-*.tar.gz" >/dev/null; then
  echo "No per-architecture image archive found. Run ./scripts/export-images.sh first." >&2
  exit 1
fi
# Every declared platform must have its own archive: the bundle has to be
# loadable on each target host architecture. `IMAGE_PLATFORMS` is also what
# keeps undeclared archives out of the staged bundle below.
IMAGE_PLATFORMS="${IMAGE_PLATFORMS:-}"
for platform in ${IMAGE_PLATFORMS}; do
  platform_arch="${platform#linux/}"
  platform_arch="${platform_arch%%/*}"
  if [[ ! -f "${ROOT_DIR}/images/codify-offline-images-${platform_arch}.tar.gz" ]]; then
    echo "Image archive for ${platform} is missing: images/codify-offline-images-${platform_arch}.tar.gz" >&2
    exit 1
  fi
done
if [[ ! -x "${DEPLOY_DIR}/worker-kit/verify-runtime.sh" || ! -f "${DEPLOY_DIR}/worker-kit/validate-runtime-manifest.py" || ! -f "${DEPLOY_DIR}/worker-kit/verify-kit-content.py" ]]; then
  echo "Worker Kit portable verifier/validator is missing; refusing to package" >&2
  exit 1
fi
KIT_CHECK_DIR="$(mktemp -d "${DEPLOY_DIR}/.worker-kit-package-check.XXXXXX")"
trap 'remove_tree "${KIT_CHECK_DIR}"; cleanup' EXIT

# Nix closures contain paths that differ only by case (ncurses terminfo A/a,
# P/p). A case-insensitive host filesystem (the default APFS/HFS+ layout)
# cannot represent them, so the extracted-tree cross-check below would report
# a false mismatch. The case-preserving archive verification stays
# authoritative here, and install-worker-kit.sh repeats the extracted-tree
# check on the target host, where the Kit is actually installed.
FS_CASE_INSENSITIVE=0
FS_PROBE_DIR="$(mktemp -d "${DEPLOY_DIR}/.worker-kit-fs-probe.XXXXXX")"
if : > "${FS_PROBE_DIR}/CaseProbe" && [[ -e "${FS_PROBE_DIR}/caseprobe" ]]; then
    FS_CASE_INSENSITIVE=1
fi
remove_tree "${FS_PROBE_DIR}"
if ! compgen -G "${ROOT_DIR}/kits/codify-worker-kit-*.tar.gz" >/dev/null; then
    echo "Worker kit archive not found. Run deploy/worker-kit/export.sh first." >&2
    exit 1
fi
verified_kit_count=0
legacy_kit_archives=()
skipped_kit_archives=()
# Only the release version's Kit archives ship in the bundle. Older archives
# stay in kits/ as rollback coordinates and must not double the bundle size
# (they share their payloads with the current release). WORKER_KIT_VERSION
# selects the release; the Makefile passes the same value it exports with.
KIT_VERSION="${WORKER_KIT_VERSION:-}"
for kit_archive in "${ROOT_DIR}"/kits/codify-worker-kit-*.tar.gz; do
    kit_name="$(basename "${kit_archive}" .tar.gz)"
    if [[ -n "${KIT_VERSION}" && "${kit_name}" != "codify-worker-kit-${KIT_VERSION}-"* ]]; then
        echo "Skipping Worker Kit archive for another release: ${kit_archive}" >&2
        skipped_kit_archives+=("$(basename "${kit_archive}")")
        continue
    fi
    # Archives produced before the immutable Kit release contract do not carry
    # a manifest digest in their name and cannot be safely mixed into a new
    # offline bundle. Keep them out of the staged bundle while allowing a
    # freshly exported archive to coexist during migration.
    if [[ ! "${kit_name}" =~ ^codify-worker-kit-.+-linux-[A-Za-z0-9_.-]+-[0-9a-f]{12}$ ]]; then
        echo "Skipping legacy Worker Kit archive (regenerate it for this bundle): ${kit_archive}" >&2
        legacy_kit_archives+=("$(basename "${kit_archive}")")
        continue
    fi
    if [[ ! -f "${kit_archive}.sha256" ]]; then
        echo "Worker kit checksum not found: ${kit_archive}.sha256" >&2
        exit 1
    fi
    if command -v sha256sum >/dev/null 2>&1; then
        (cd "$(dirname "${kit_archive}")" && sha256sum -c "$(basename "${kit_archive}").sha256")
    else
        (cd "$(dirname "${kit_archive}")" && shasum -a 256 -c "$(basename "${kit_archive}").sha256")
    fi
    kit_extract="${KIT_CHECK_DIR}/${kit_name}"
    mkdir -p "${kit_extract}"
    python3 "${ROOT_DIR}/scripts/validate-kit-archive.py" "${kit_archive}" "${kit_name#codify-worker-kit-}"
    tar -C "${kit_extract}" -xzf "${kit_archive}"
    kit_root="${kit_extract}/${kit_name#codify-worker-kit-}"
    [[ -x "${kit_root}/launcher" && -s "${kit_root}/manifest.json" && -d "${kit_root}/nix/store" ]] || {
        echo "Worker Kit archive has an invalid launcher/manifest/store contract: ${kit_archive}" >&2
        exit 1
    }
    [[ -x "${kit_root}/verify-runtime.sh" ]] || {
        echo "Worker Kit archive is missing executable verify-runtime.sh: ${kit_archive}" >&2
        exit 1
    }
    [[ -f "${kit_root}/validate-runtime-manifest.py" ]] || {
        echo "Worker Kit archive is missing validate-runtime-manifest.py: ${kit_archive}" >&2
        exit 1
    }
    [[ -f "${kit_root}/verify-kit-content.py" ]] || {
        echo "Worker Kit archive is missing verify-kit-content.py: ${kit_archive}" >&2
        exit 1
    }
    archive_content_digest="$(python3 "${DEPLOY_DIR}/worker-kit/verify-kit-content.py" \
        --archive "${kit_archive}" --root-name "${kit_name#codify-worker-kit-}")" || {
        echo "Worker Kit archive content inventory does not match its bytes: ${kit_archive}" >&2
        exit 1
    }
    if [[ "${FS_CASE_INSENSITIVE}" == 1 ]]; then
        echo "Skipping extracted-tree cross-check on a case-insensitive filesystem: ${kit_archive}" >&2
    else
        embedded_content_digest="$(python3 "${DEPLOY_DIR}/worker-kit/verify-kit-content.py" \
            --root "${kit_root}")" || {
            echo "Worker Kit extracted content inventory does not match its bytes: ${kit_archive}" >&2
            exit 1
        }
        [[ "${archive_content_digest}" == "${embedded_content_digest}" ]] || {
            echo "Worker Kit archive embedded verifier disagrees with release verifier: ${kit_archive}" >&2
            exit 1
        }
    fi
    verified_kit_count=$((verified_kit_count + 1))
done
if [[ "${verified_kit_count}" -eq 0 ]]; then
    echo "No content-addressed Worker Kit archive is available; regenerate the Kit before packaging." >&2
    exit 1
fi

rm -f "${TMP_ARCHIVE}"

STAGING_DIR="$(mktemp -d "${DEPLOY_DIR}/.codify-offline-bundle-staging.XXXXXX")"
cp -R "${ROOT_DIR}" "${STAGING_DIR}/offline-bundle"
cp "${DEPLOY_DIR}/worker-kit/verify-kit-content.py" \
    "${STAGING_DIR}/offline-bundle/scripts/verify-kit-content.py"
if [[ "${#legacy_kit_archives[@]}" -gt 0 ]]; then
    drop_from_staging "${legacy_kit_archives[@]}"
fi
if [[ "${#skipped_kit_archives[@]}" -gt 0 ]]; then
    drop_from_staging "${skipped_kit_archives[@]}"
fi

# Ship exactly the declared platforms: drop any other image archive and keep
# the staged images/SHA256SUMS listing only the archives that actually ship.
if [[ -n "${IMAGE_PLATFORMS}" ]]; then
    for staged_archive in "${STAGING_DIR}"/offline-bundle/images/codify-offline-images-*.tar.gz; do
        [[ -f "${staged_archive}" ]] || continue
        staged_arch="$(basename "${staged_archive}" .tar.gz)"
        staged_arch="${staged_arch#codify-offline-images-}"
        keep_archive=0
        for platform in ${IMAGE_PLATFORMS}; do
            platform_arch="${platform#linux/}"
            platform_arch="${platform_arch%%/*}"
            [[ "${platform_arch}" == "${staged_arch}" ]] && keep_archive=1
        done
        if [[ "${keep_archive}" -eq 0 ]]; then
            echo "Skipping image archive for an undeclared platform: ${staged_archive}" >&2
            rm -f "${staged_archive}"
        fi
    done
    : > "${STAGING_DIR}/offline-bundle/images/SHA256SUMS"
    for staged_archive in "${STAGING_DIR}"/offline-bundle/images/codify-offline-images-*.tar.gz; do
        [[ -f "${staged_archive}" ]] || continue
        if command -v sha256sum >/dev/null 2>&1; then
            (cd "$(dirname "${staged_archive}")" && sha256sum "$(basename "${staged_archive}")") \
                >> "${STAGING_DIR}/offline-bundle/images/SHA256SUMS"
        else
            (cd "$(dirname "${staged_archive}")" && shasum -a 256 "$(basename "${staged_archive}")") \
                >> "${STAGING_DIR}/offline-bundle/images/SHA256SUMS"
        fi
    done
fi

echo "Packaging offline bundle to ${OUTPUT_ARCHIVE}..."
tar -C "${STAGING_DIR}" -czf "${TMP_ARCHIVE}" offline-bundle
mv "${TMP_ARCHIVE}" "${OUTPUT_ARCHIVE}"
if command -v sha256sum >/dev/null 2>&1; then
    (cd "$(dirname "${OUTPUT_ARCHIVE}")" && sha256sum "$(basename "${OUTPUT_ARCHIVE}")") > "${OUTPUT_ARCHIVE}.sha256"
else
    (cd "$(dirname "${OUTPUT_ARCHIVE}")" && shasum -a 256 "$(basename "${OUTPUT_ARCHIVE}")") > "${OUTPUT_ARCHIVE}.sha256"
fi

echo "Done. Before extracting or executing the bundle, verify it with one platform command:"
echo "  Linux:  sha256sum -c ${OUTPUT_ARCHIVE}.sha256"
echo "  macOS:  shasum -a 256 -c ${OUTPUT_ARCHIVE}.sha256"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# One archive per CPU architecture: a single `docker save` stream cannot carry
# two platforms, and each target host loads the archive matching its own
# architecture (see load-images.sh).
PLATFORM="${IMAGE_PLATFORM:-linux/amd64}"
ARCH="${PLATFORM#linux/}"
ARCH="${ARCH%%/*}"
ARCHIVE="${ROOT_DIR}/images/codify-offline-images-${ARCH}.tar.gz"

daemon_arch() {
    local raw
    raw="$(docker info --format '{{.Architecture}}' 2>/dev/null)" || return 1
    case "${raw}" in
        x86_64|amd64) printf 'amd64\n' ;;
        aarch64|arm64) printf 'arm64\n' ;;
        *) return 1 ;;
    esac
}

DAEMON_ARCH="$(daemon_arch)" || {
    echo "Cannot determine the Docker daemon CPU architecture." >&2
    exit 2
}
if [[ "${DAEMON_ARCH}" != "${ARCH}" ]]; then
    cat >&2 <<EOF

The active Docker daemon is ${DAEMON_ARCH}; it cannot produce the ${ARCH} image archive
(the saved images would be the wrong architecture).

Point the export at a ${ARCH} builder — e.g. DOCKER_CONTEXT=<context> with
IMAGE_PLATFORM=${PLATFORM} — and re-run. `make offline-bundle-export` does this for every
platform in IMAGE_PLATFORMS.

Aborting; no image archive was produced for ${PLATFORM}.
EOF
    exit 2
fi

IMAGES=(
  "codify-backend:latest"
  "codify-nginx:latest"
  "postgres:16-alpine"
)

EXTRA_IMAGES_FILE="${ROOT_DIR}/config/worker-images.txt"
if [[ -f "${EXTRA_IMAGES_FILE}" ]]; then
  while IFS= read -r image; do
    image="${image%%#*}"
    image="${image//[[:space:]]/}"
    [[ -n "${image}" ]] && IMAGES+=("${image}")
  done < "${EXTRA_IMAGES_FILE}"
fi

# A third-party image may be absent on this builder (the app images themselves
# are built by `make offline-bundle-export` before this script runs).
for image in "${IMAGES[@]}"; do
    if ! docker image inspect "${image}" >/dev/null 2>&1; then
        echo "Pulling ${image} for ${ARCH}..."
        docker pull --platform "${PLATFORM}" "${image}" >/dev/null
    fi
    image_arch="$(docker image inspect "${image}" --format '{{.Architecture}}' 2>/dev/null)"
    if [[ "${image_arch}" != "${ARCH}" ]]; then
        echo "Image ${image} is ${image_arch:-unknown}, but this archive is for ${ARCH}." >&2
        echo "Build or pull it on a ${ARCH} builder (see IMAGE_PLATFORMS in the Makefile)." >&2
        exit 2
    fi
done

# Superseded single-architecture archive: leaving it next to the per-platform
# archives would ship a stale image set of an unknown architecture.
LEGACY_ARCHIVE="${ROOT_DIR}/images/codify-offline-images.tar.gz"
if [[ -f "${LEGACY_ARCHIVE}" ]]; then
    echo "Removing superseded image archive: ${LEGACY_ARCHIVE}" >&2
    rm -f "${LEGACY_ARCHIVE}"
fi

mkdir -p "$(dirname "${ARCHIVE}")"
echo "Exporting ${ARCH} images to ${ARCHIVE}..."
docker save "${IMAGES[@]}" | gzip -1 > "${ARCHIVE}"

SHA256SUMS="${ROOT_DIR}/images/SHA256SUMS"
: > "${SHA256SUMS}"
for existing in "${ROOT_DIR}"/images/codify-offline-images-*.tar.gz; do
    [[ -f "${existing}" ]] || continue
    if command -v sha256sum >/dev/null 2>&1; then
        (cd "$(dirname "${existing}")" && sha256sum "$(basename "${existing}")") >> "${SHA256SUMS}"
    else
        (cd "$(dirname "${existing}")" && shasum -a 256 "$(basename "${existing}")") >> "${SHA256SUMS}"
    fi
done
echo "Done."

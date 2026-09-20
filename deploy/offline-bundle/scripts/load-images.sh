#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Image archives are per architecture; load the one matching this host.
ARCH="${IMAGE_ARCH:-}"
if [[ -z "${ARCH}" ]]; then
    case "$(uname -m)" in
        x86_64|amd64) ARCH=amd64 ;;
        aarch64|arm64) ARCH=arm64 ;;
        *)
            echo "Unsupported host architecture: $(uname -m). Set IMAGE_ARCH=amd64|arm64." >&2
            exit 2
            ;;
    esac
fi

IMAGE_ARCHIVE="${ROOT_DIR}/images/codify-offline-images-${ARCH}.tar.gz"
if [[ ! -f "${IMAGE_ARCHIVE}" ]]; then
    echo "Image archive not found: ${IMAGE_ARCHIVE}" >&2
    echo "Available: $(ls "${ROOT_DIR}"/images/codify-offline-images-*.tar.gz 2>/dev/null || echo none)" >&2
    exit 1
fi

echo "Loading ${ARCH} Docker images from ${IMAGE_ARCHIVE}..."
gunzip -c "${IMAGE_ARCHIVE}" | docker load
echo "Done."

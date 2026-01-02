#!/usr/bin/env bash
#
# Build script for Munich Glance Docker image
#
# Usage:
#   ./build.sh [command] [options]
#
# Commands:
#   build             Build image locally (current arch only)
#   push              Build and push multi-arch image to registry
#   list              Show current configuration
#
# Options:
#   --registry=URL    Registry prefix (e.g., ghcr.io/myorg)
#   --tag=TAG         Image tag (default: latest)
#   --arch=ARCH       Architecture: amd64, arm64, or both (default: both for push)
#   --name=NAME       Image name (default: munich-glance)
#
# Environment Variables (override defaults):
#   REGISTRY          Registry prefix
#   TAG               Image tag (default: latest)
#   IMAGE_NAME        Image name (default: munich-glance)
#   ARCH              Architecture (default: current for build, both for push)
#
# Examples:
#   ./build.sh build                              # Build for current arch
#   ./build.sh build --arch=arm64                 # Build for arm64 only
#   ./build.sh push --registry=ghcr.io/myorg      # Build & push both archs
#   ./build.sh push --registry=ghcr.io/myorg --arch=amd64  # Push amd64 only
#   ./build.sh list                               # Show config
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Default settings
REGISTRY="${REGISTRY:-}"
TAG="${TAG:-latest}"
IMAGE_NAME="${IMAGE_NAME:-munich-glance}"
ARCH="${ARCH:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get full image name with optional registry prefix
get_image_name() {
    if [[ -n "$REGISTRY" ]]; then
        echo "${REGISTRY}/${IMAGE_NAME}:${TAG}"
    else
        echo "${IMAGE_NAME}:${TAG}"
    fi
}

# Get current architecture
get_current_arch() {
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64)
            echo "amd64"
            ;;
        aarch64|arm64)
            echo "arm64"
            ;;
        *)
            echo "$arch"
            ;;
    esac
}

# Build image for current architecture (local build)
build_local() {
    local image_tag
    image_tag=$(get_image_name)
    local target_arch="${ARCH:-$(get_current_arch)}"

    log_info "Building ${image_tag} for ${target_arch}"

    docker build \
        --platform "linux/${target_arch}" \
        -t "${image_tag}" \
        -f Dockerfile \
        .

    log_success "Built: ${image_tag} (${target_arch})"
}

# Build and push multi-arch image
build_and_push() {
    local image_tag
    image_tag=$(get_image_name)
    local target_arch="${ARCH:-both}"

    if [[ -z "$REGISTRY" ]]; then
        log_error "Registry not specified. Use --registry=URL or REGISTRY env var"
        exit 1
    fi

    # Determine platforms
    local platforms=""
    case "$target_arch" in
        amd64)
            platforms="linux/amd64"
            ;;
        arm64)
            platforms="linux/arm64"
            ;;
        both)
            platforms="linux/amd64,linux/arm64"
            ;;
        *)
            log_error "Unknown architecture: ${target_arch}. Use amd64, arm64, or both"
            exit 1
            ;;
    esac

    log_info "Building and pushing ${image_tag} for ${platforms}"

    # Check if buildx builder exists, create if needed
    if ! docker buildx inspect multiarch-builder &>/dev/null; then
        log_info "Creating buildx builder: multiarch-builder"
        docker buildx create --name multiarch-builder --use
    else
        docker buildx use multiarch-builder
    fi

    docker buildx build \
        --platform "${platforms}" \
        -t "${image_tag}" \
        -f Dockerfile \
        --push \
        .

    log_success "Pushed: ${image_tag} (${platforms})"
}

# List configuration
list_config() {
    local image_tag
    image_tag=$(get_image_name)
    local current_arch
    current_arch=$(get_current_arch)

    echo ""
    echo "Munich Glance Docker Build"
    echo "=========================="
    echo ""
    echo "Image:        ${image_tag}"
    echo "Tag:          ${TAG}"
    echo "Current arch: ${current_arch}"
    echo ""
    if [[ -n "$REGISTRY" ]]; then
        echo "Registry:     ${REGISTRY}"
    else
        echo "Registry:     (not set - local build only)"
    fi
    echo ""
    echo "Dockerfile:   ${PROJECT_DIR}/Dockerfile"
    echo ""
}

# Show usage
usage() {
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  build             Build image locally"
    echo "  push              Build and push multi-arch image to registry"
    echo "  list              Show current configuration"
    echo ""
    echo "Options:"
    echo "  --registry=URL    Registry prefix (e.g., ghcr.io/myorg)"
    echo "  --tag=TAG         Image tag (default: latest)"
    echo "  --arch=ARCH       Architecture: amd64, arm64, or both (default: current/both)"
    echo "  --name=NAME       Image name (default: munich-glance)"
    echo ""
    echo "Examples:"
    echo "  $0 build                                    # Build for current arch"
    echo "  $0 build --arch=arm64                       # Build for arm64"
    echo "  $0 push --registry=ghcr.io/myorg            # Build & push both archs"
    echo "  $0 push --registry=ghcr.io/myorg --arch=amd64  # Push amd64 only"
    echo "  $0 list --registry=ghcr.io/myorg --tag=v1.0    # Show config"
}

# Parse arguments
COMMAND=""

for arg in "$@"; do
    case "$arg" in
        --registry=*)
            REGISTRY="${arg#*=}"
            ;;
        --tag=*)
            TAG="${arg#*=}"
            ;;
        --arch=*)
            ARCH="${arg#*=}"
            ;;
        --name=*)
            IMAGE_NAME="${arg#*=}"
            ;;
        build|push|list|help|-h|--help)
            COMMAND="$arg"
            ;;
        *)
            log_error "Unknown argument: $arg"
            usage
            exit 1
            ;;
    esac
done

# Execute command
case "$COMMAND" in
    build)
        build_local
        ;;
    push)
        build_and_push
        ;;
    list)
        list_config
        ;;
    help|-h|--help|"")
        usage
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac

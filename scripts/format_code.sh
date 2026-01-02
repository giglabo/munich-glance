#!/bin/bash
# Code formatting script for Munich Glance
# Formats Python code using black (formatting) and ruff (linting + import sorting)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Define Python packages to format
PACKAGES=(
    "trmnl_server"
    "tests"
)

echo "Formatting Munich Glance Python code..."
echo ""

# Check if tools are available
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo "Warning: $1 not found. Install with: pip install $1"
        return 1
    fi
    return 0
}

# Build list of existing directories
DIRS_TO_FORMAT=()
for pkg in "${PACKAGES[@]}"; do
    if [ -d "$ROOT_DIR/$pkg" ]; then
        DIRS_TO_FORMAT+=("$ROOT_DIR/$pkg")
    fi
done

if [ ${#DIRS_TO_FORMAT[@]} -eq 0 ]; then
    echo "No directories found to format."
    exit 1
fi

echo "Directories to format:"
for dir in "${DIRS_TO_FORMAT[@]}"; do
    echo "  - $dir"
done
echo ""

CONFIG_FILE="$ROOT_DIR/pyproject.toml"

# Run ruff with auto-fix first (includes import sorting with I rules)
if check_tool ruff; then
    echo "Running ruff format (import sorting + linting fixes)..."
    ruff check "${DIRS_TO_FORMAT[@]}" --fix --config "$CONFIG_FILE" || true
    ruff format "${DIRS_TO_FORMAT[@]}" --config "$CONFIG_FILE" || true
    echo "Ruff complete"
    echo ""
fi

# Format with black (final formatting pass)
if check_tool black; then
    echo "Running black..."
    black "${DIRS_TO_FORMAT[@]}" --config "$CONFIG_FILE"
    echo "Black formatting complete"
    echo ""
fi

echo "Code formatting complete!"
echo ""
echo "Next steps:"
echo "  - Review changes: git diff"
echo "  - Run checks: ./scripts/check_code.sh"
echo "  - Commit changes: git add . && git commit -m 'style: format code'"

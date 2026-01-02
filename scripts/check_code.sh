#!/bin/bash
# Code quality check script for Munich Glance
# Runs linting and type checking across all Python packages

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Define Python packages to check
PACKAGES=(
    "trmnl_server"
    "tests"
)

echo "Checking code quality for Munich Glance..."
echo ""

# Build list of existing directories
DIRS_TO_CHECK=()
for pkg in "${PACKAGES[@]}"; do
    if [ -d "$ROOT_DIR/$pkg" ]; then
        DIRS_TO_CHECK+=("$ROOT_DIR/$pkg")
    fi
done

if [ ${#DIRS_TO_CHECK[@]} -eq 0 ]; then
    echo "No directories found to check."
    exit 1
fi

echo "Directories to check:"
for dir in "${DIRS_TO_CHECK[@]}"; do
    echo "  - $dir"
done
echo ""

EXIT_CODE=0
CONFIG_FILE="$ROOT_DIR/pyproject.toml"

# Run ruff (includes import sorting check with I rules)
if command -v ruff &> /dev/null; then
    echo "Running ruff (linting + import sorting)..."
    if ruff check "${DIRS_TO_CHECK[@]}" --config "$CONFIG_FILE"; then
        echo "Ruff check passed"
    else
        echo "Ruff check failed - run './scripts/format_code.sh' to auto-fix"
        EXIT_CODE=1
    fi
    echo ""

    echo "Checking ruff formatting..."
    if ruff format --check "${DIRS_TO_CHECK[@]}" --config "$CONFIG_FILE"; then
        echo "Ruff format check passed"
    else
        echo "Ruff format check failed - run './scripts/format_code.sh' to fix"
        EXIT_CODE=1
    fi
    echo ""
else
    echo "Warning: ruff not found, skipping ruff check"
    echo ""
fi

# Check formatting with black
if command -v black &> /dev/null; then
    echo "Checking black formatting..."
    if black --check "${DIRS_TO_CHECK[@]}" --config "$CONFIG_FILE"; then
        echo "Black check passed"
    else
        echo "Black check failed - run './scripts/format_code.sh' to fix"
        EXIT_CODE=1
    fi
    echo ""
else
    echo "Warning: black not found, skipping format check"
    echo ""
fi

# Run flake8 if available (optional, as ruff covers most rules)
if command -v flake8 &> /dev/null; then
    echo "Running flake8..."
    if flake8 "${DIRS_TO_CHECK[@]}" --max-line-length=100 --extend-ignore=E203,W503,E501; then
        echo "Flake8 check passed"
    else
        echo "Flake8 check failed"
        EXIT_CODE=1
    fi
    echo ""
fi

# Run mypy if available (non-blocking)
if command -v mypy &> /dev/null; then
    echo "Running mypy..."
    for dir in "${DIRS_TO_CHECK[@]}"; do
        if [[ "$dir" != *"/tests"* ]]; then
            if mypy "$dir" --ignore-missing-imports; then
                echo "Mypy check passed for $dir"
            else
                echo "Warning: Mypy check failed for $dir (non-blocking)"
            fi
        fi
    done
    echo ""
fi

# Run bandit security check if available (non-blocking)
if command -v bandit &> /dev/null; then
    echo "Running bandit security check..."
    for dir in "${DIRS_TO_CHECK[@]}"; do
        if [[ "$dir" != *"/tests"* ]]; then
            if bandit -r "$dir" -q; then
                echo "Bandit check passed for $dir"
            else
                echo "Warning: Bandit found security issues in $dir (non-blocking)"
            fi
        fi
    done
    echo ""
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo "All code quality checks passed!"
else
    echo "Some checks failed. Please fix the issues above."
    echo "Run './scripts/format_code.sh' to auto-fix formatting issues."
fi

exit $EXIT_CODE

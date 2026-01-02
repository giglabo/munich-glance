#!/bin/bash
# Download DejaVu fonts for MunichGlance renderer

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FONTS_DIR="$PROJECT_ROOT/assets/fonts"

# DejaVu fonts version and download URL
DEJAVU_VERSION="2.37"
DEJAVU_URL="https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_${DEJAVU_VERSION}/dejavu-fonts-ttf-${DEJAVU_VERSION}.tar.bz2"

echo "=== MunichGlance Font Setup ==="
echo ""

# Check if fonts already exist
if [ -f "$FONTS_DIR/DejaVuSans.ttf" ]; then
    echo "Fonts already exist in $FONTS_DIR"
    echo "To re-download, remove the fonts directory first:"
    echo "  rm -rf $FONTS_DIR"
    exit 0
fi

# Create fonts directory
mkdir -p "$FONTS_DIR"

echo "Downloading DejaVu fonts v${DEJAVU_VERSION}..."
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Download and extract
if command -v curl &> /dev/null; then
    curl -sL "$DEJAVU_URL" -o "$TEMP_DIR/dejavu.tar.bz2"
elif command -v wget &> /dev/null; then
    wget -q "$DEJAVU_URL" -O "$TEMP_DIR/dejavu.tar.bz2"
else
    echo "Error: Neither curl nor wget found. Please install one of them."
    exit 1
fi

echo "Extracting fonts..."
tar -xjf "$TEMP_DIR/dejavu.tar.bz2" -C "$TEMP_DIR"

# Copy TTF files
cp "$TEMP_DIR/dejavu-fonts-ttf-${DEJAVU_VERSION}/ttf/"*.ttf "$FONTS_DIR/"

echo ""
echo "Fonts installed to: $FONTS_DIR"
echo ""
ls -la "$FONTS_DIR"
echo ""
echo "Setup complete!"

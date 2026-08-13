#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv
if [ ! -d "venv" ]; then
    echo "Creating venv..."
    python3 -m venv venv
fi
source venv/bin/activate

# Ensure build/upload tools are installed
pip install --quiet flit twine build

# Read current version
VERSION_FILE="upwellfuel/__init__.py"
CURRENT_VERSION=$(grep -oP '__version__\s*=\s*"\K[^"]+' "$VERSION_FILE")
echo "Deploying version: $CURRENT_VERSION"

# Clean old build artifacts
rm -rf dist/ build/ *.egg-info

# Build
python -m build

# Upload to PyPI prod
echo "Uploading to PyPI..."
twine upload dist/*

echo "Done! Version $CURRENT_VERSION deployed to PyPI."

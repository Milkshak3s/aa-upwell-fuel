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
echo "Current version: $CURRENT_VERSION"

# Parse and bump build (patch) number
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"
NEW_PATCH=$((PATCH + 1))
NEW_VERSION="${MAJOR}.${MINOR}.${NEW_PATCH}"
echo "Bumping to: $NEW_VERSION"

# Update version in __init__.py
sed -i "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" "$VERSION_FILE"

# Clean old build artifacts
rm -rf dist/ build/ *.egg-info

# Build
python -m build

# Upload to PyPI Test
echo "Uploading to TestPyPI..."
twine upload --repository testpypi dist/*

# Git commit and push
git add "$VERSION_FILE"
git commit -m "Bump version to $NEW_VERSION"
git push

echo "Done! Version $NEW_VERSION deployed to TestPyPI and pushed to git."

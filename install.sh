#!/usr/bin/env bash
# Install GitRef from GitHub releases (Linux/macOS)
# Usage: curl -fsSL https://raw.githubusercontent.com/CGutt-hub/gitref/main/install.sh | bash
set -euo pipefail

REPO="CGutt-hub/gitref"
BIN_DIR="${HOME}/.local/bin"

echo "Installing GitRef..."

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64|amd64) ASSET="GitRef-x86_64.AppImage" ;;
    *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

# Get latest release URL
LATEST=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
    | grep -o "\"browser_download_url\": \"[^\"]*${ASSET}\"" \
    | cut -d'"' -f4)

if [ -z "$LATEST" ]; then
    echo "Could not find release asset: $ASSET"
    echo "Falling back to pip install..."
    pip install "git+https://github.com/${REPO}.git"
    echo "Installed via pip. Run: gitref"
    exit 0
fi

# Download and install
mkdir -p "$BIN_DIR"
curl -fsSL "$LATEST" -o "${BIN_DIR}/gitref"
chmod +x "${BIN_DIR}/gitref"

# Check if BIN_DIR is on PATH
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
    SHELL_RC=""
    case "$SHELL" in
        */bash) SHELL_RC="$HOME/.bashrc" ;;
        */zsh)  SHELL_RC="$HOME/.zshrc" ;;
        */fish) SHELL_RC="$HOME/.config/fish/config.fish" ;;
    esac
    if [ -n "$SHELL_RC" ]; then
        echo "export PATH=\"${BIN_DIR}:\$PATH\"" >> "$SHELL_RC"
        echo "Added ${BIN_DIR} to PATH in ${SHELL_RC}"
        echo "Run: source ${SHELL_RC}"
    else
        echo "Add ${BIN_DIR} to your PATH manually."
    fi
fi

echo "GitRef installed to ${BIN_DIR}/gitref"
echo "Run: gitref"

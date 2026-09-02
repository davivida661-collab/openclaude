#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# OpenClaude — Automated Termux + proot Ubuntu Setup Script
#
# Run this from Termux (not proot) to install everything automatically:
#   curl -fsSL https://raw.githubusercontent.com/Gitlawb/openclaude/main/scripts/setup-termux.sh | bash
#
# Or save it locally and run:
#   bash setup-termux.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }
step()  { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }

# ── Preflight ────────────────────────────────────────────────────────────────

step "OpenClaude Termux Setup"
info "This script installs OpenClaude on Android via Termux + proot Ubuntu."
echo ""

# Check if running in Termux
if [ -z "${TERMUX_VERSION:-}" ] && [ ! -d "/data/data/com.termux" ]; then
    err "This script must be run in Termux (not proot, not a regular Linux)."
    exit 1
fi

# ── Step 1: Update Termux ───────────────────────────────────────────────────

step "1/7 — Updating Termux packages"
pkg update -y && pkg upgrade -y
ok "Termux packages updated."

# ── Step 2: Install dependencies ─────────────────────────────────────────────

step "2/7 — Installing dependencies"
pkg install -y nodejs-lts git proot-distro openssh
ok "Dependencies installed."

# Verify Node.js
NODE_VER=$(node --version 2>/dev/null || echo "v0")
info "Node.js: $NODE_VER"

# ── Step 3: Install proot Ubuntu ────────────────────────────────────────────

step "3/7 — Installing proot Ubuntu"
if proot-distro list 2>/dev/null | grep -q ubuntu; then
    warn "Ubuntu already installed, skipping."
else
    proot-distro install ubuntu
    ok "Ubuntu installed."
fi

# ── Step 4: Enter proot, install Bun + build ─────────────────────────────────

step "4/7 — Setting up inside proot Ubuntu"

# Create the setup script that runs inside proot
PROOT_SETUP=$(cat << 'PROOT_EOF'
#!/bin/bash
set -euo pipefail

echo "[proot] Updating Ubuntu..."
apt update -qq && apt install -y -qq curl git ca-certificates > /dev/null 2>&1

# Install Bun if not present or outdated
BUN_VER=$(bun --version 2>/dev/null || echo "0")
if [ "$BUN_VER" = "0" ] || [ "$(printf '%s\n' "1.3.13" "$BUN_VER" | sort -V | head -1)" != "1.3.13" ]; then
    echo "[proot] Installing Bun..."
    curl -fsSL https://bun.sh/install | bash > /dev/null 2>&1
    export BUN_INSTALL="$HOME/.bun"
    export PATH="$BUN_INSTALL/bin:$PATH"
    source ~/.bashrc 2>/dev/null || true
fi

echo "[proot] Bun: $(bun --version)"

# Clone or update OpenClaude
REPO_DIR="/data/data/com.termux/files/home/openclaude"
if [ -d "$REPO_DIR/.git" ]; then
    echo "[proot] Updating existing OpenClaude..."
    cd "$REPO_DIR"
    git pull --ff-only || true
else
    echo "[proot] Cloning OpenClaude..."
    cd /data/data/com.termux/files/home
    git clone https://github.com/Gitlawb/openclaude.git
    cd openclaude
fi

# Install and build
echo "[proot] Installing dependencies..."
bun install --no-optional 2>&1 | tail -1

echo "[proot] Building OpenClaude..."
bun run build

echo "[proot] Build complete!"
PROOT_EOF
)

# Write and execute inside proot
TMPFILE=$(mktemp)
echo "$PROOT_SETUP" > "$TMPFILE"
chmod +x "$TMPFILE"
proot-distro login ubuntu -- bash "$TMPFILE"
rm -f "$TMPFILE"

ok "OpenClaude built successfully inside proot."

# ── Step 5: Configure provider ──────────────────────────────────────────────

step "5/7 — Configuring provider"

CONFIG_DIR="$HOME/.config/openclaude"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

PROVIDER_FILE="$CONFIG_DIR/provider.env"

if [ -f "$PROVIDER_FILE" ]; then
    warn "Provider config already exists at $PROVIDER_FILE — skipping."
    info "Edit it manually: nano $PROVIDER_FILE"
else
    cat > "$PROVIDER_FILE" << 'ENV_EOF'
# OpenClaude Provider Configuration
# Edit this file with your actual API key, then run: source ~/.config/openclaude/provider.env

# ── OpenRouter (free models) ───────────────────────────────────────────────
export CLAUDE_CODE_USE_OPENAI=1
export OPENAI_API_KEY=YOUR_KEY_HERE
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
export OPENAI_MODEL=qwen/qwen3.6-plus-preview:free
ENV_EOF

    chmod 600 "$PROVIDER_FILE"
    ok "Provider config created at $PROVIDER_FILE"
    warn ">>> EDIT THIS FILE with your API key: nano $PROVIDER_FILE <<<"
fi

# Source in .bashrc if not already added
if ! grep -q "provider.env" "$HOME/.bashrc" 2>/dev/null; then
    echo 'source ~/.config/openclaude/provider.env 2>/dev/null' >> "$HOME/.bashrc"
    info "Added provider sourcing to ~/.bashrc"
fi

# ── Step 6: Install GitHub CLI ──────────────────────────────────────────────

step "6/7 — Installing GitHub CLI (gh)"

GH_SETUP=$(cat << 'GH_EOF'
#!/bin/bash
if command -v gh &>/dev/null; then
    echo "[proot] GitHub CLI already installed: $(gh --version | head -1)"
else
    echo "[proot] Installing GitHub CLI..."
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg 2>/dev/null
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        | tee /etc/apt/sources.list.d/github-cli.list > /dev/null
    apt update -qq && apt install -y -qq gh 2>/dev/null
    echo "[proot] GitHub CLI installed: $(gh --version | head -1)"
fi
GH_EOF
)

GHFILE=$(mktemp)
echo "$GH_SETUP" > "$GHFILE"
chmod +x "$GHFILE"
proot-distro login ubuntu -- bash "$GHFILE"
rm -f "$GHFILE"

ok "GitHub CLI ready."

# ── Step 7: Create launch script ────────────────────────────────────────────

step "7/7 — Creating launch script"

LAUNCH_SCRIPT="$HOME/launch-openclaude.sh"
cat > "$LAUNCH_SCRIPT" << 'LAUNCH_EOF'
#!/bin/bash
# OpenClaude launcher for Termux
# Usage: bash ~/launch-openclaude.sh [args...]

proot-distro login ubuntu -- bash -c '
    export BUN_INSTALL="$HOME/.bun"
    export PATH="$BUN_INSTALL/bin:$PATH"
    source ~/.config/openclaude/provider.env 2>/dev/null
    cd /data/data/com.termux/files/home/openclaude
    node dist/cli.mjs "$@"
' -- "$@"
LAUNCH_EOF

chmod 700 "$LAUNCH_SCRIPT"
ok "Launch script created: $LAUNCH_SCRIPT"

# Also create a Termux widget shortcut
SHORTCUTS_DIR="$HOME/.shortcuts"
mkdir -p "$SHORTCUTS_DIR"
cp "$LAUNCH_SCRIPT" "$SHORTCUTS_DIR/launch-openclaude.sh"
chmod 700 "$SHORTCUTS_DIR/launch-openclaude.sh"
info "Termux widget shortcut created."

# ── Done ────────────────────────────────────────────────────────────────────

step "✅ Setup Complete!"
echo ""
echo -e "${GREEN}OpenClaude is ready to use.${NC}"
echo ""
echo "To run OpenClaude:"
echo -e "  ${CYAN}bash ~/launch-openclaude.sh${NC}"
echo ""
echo "Or manually:"
echo -e "  ${CYAN}proot-distro login ubuntu${NC}"
echo -e "  ${CYAN}cd /data/data/com.termux/files/home/openclaude${NC}"
echo -e "  ${CYAN}node dist/cli.mjs${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit your provider config: nano ~/.config/openclaude/provider.env"
echo "  2. Add your API key (OpenRouter, GitHub, or Anthropic)"
echo "  3. Run: bash ~/launch-openclaude.sh"
echo "  4. Inside OpenClaude, use /provider to switch providers"
echo ""
echo "GitHub CLI: proot-distro login ubuntu -- gh auth login"
echo ""
echo -e "${YELLOW}Security reminder:${NC} Never share your API keys. Rotate them regularly."
echo ""

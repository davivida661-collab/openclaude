# OpenClaude on Android (Termux)

A complete guide to running OpenClaude on Android using Termux + proot Ubuntu.

---

## Prerequisites

- Android phone with ~1 GB free storage
- [Termux](https://f-droid.org/en/packages/com.termux/) installed from **F-Droid** (not Play Store — the Play Store version is outdated and lacks critical features)
- An [OpenRouter](https://openrouter.ai) API key (free, no credit card required)

> **Why F-Droid?** The Google Play Store version of Termux is frozen at an old release
> that lacks `proot-distro` support, has broken `pkg` updates, and ships with
> deprecated bundled binaries. Always use the F-Droid build.

---

## Why This Setup?

OpenClaude requires [Bun](https://bun.sh) ≥ 1.3.13 to build, and Bun does not
support Android natively. The workaround is running a real Ubuntu environment
inside Termux via `proot-distro`, where Bun's Linux binary works correctly.

---

## Installation

### Step 1 — Update Termux

```bash
pkg update && pkg upgrade
```

Press `N` or Enter for any config file conflict prompts.

### Step 2 — Install dependencies

```bash
pkg install nodejs-lts git proot-distro
```

Verify Node.js (requires ≥ 22.0.0 at runtime):
```bash
node --version  # should be v22+
```

### Step 3 — Install Ubuntu via proot

```bash
proot-distro install ubuntu
```

This downloads ~200–400 MB. Wait for it to complete.

### Step 4 — Enter Ubuntu and install Bun

```bash
proot-distro login ubuntu
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc
bun --version  # should show 1.3.13+
```

### Step 5 — Clone and build OpenClaude

```bash
cd /data/data/com.termux/files/home
git clone https://github.com/Gitlawb/openclaude.git
cd openclaude
bun install
bun run build
```

You should see a build success message like:
```
✓ Built openclaude → dist/cli.mjs
```

> **Why inside proot?** The `npm install` and `npm link` steps that older guides
> ran outside proot are unnecessary — the build depends on Bun and native
> dependencies that only work inside the Ubuntu environment.

### Step 6 — Configure your provider

Still inside Ubuntu, create a secure environment file:

```bash
# Create a private config directory
mkdir -p ~/.config/openclaude
chmod 700 ~/.config/openclaude

# Create the provider config file with restricted permissions
cat > ~/.config/openclaude/provider.env << 'EOF'
export CLAUDE_CODE_USE_OPENAI=1
export OPENAI_API_KEY=YOUR_OPENROUTER_KEY_HERE
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
export OPENAI_MODEL=qwen/qwen3.6-plus-preview:free
EOF

chmod 600 ~/.config/openclaude/provider.env
```

Replace `YOUR_OPENROUTER_KEY_HERE` with your actual key from
[openrouter.ai/keys](https://openrouter.ai/keys).

> ⚠️ **Security**: Never store API keys in `~/.bashrc` where other processes or
> users can read them. The dedicated file with `chmod 600` ensures only your
> user can access the key.

Then source it in your Ubuntu `.bashrc`:

```bash
echo 'source ~/.config/openclaude/provider.env' >> ~/.bashrc
source ~/.bashrc
```

### Step 7 — Run OpenClaude

```bash
cd /data/data/com.termux/files/home/openclaude
node dist/cli.mjs
```

Your env vars will be detected automatically. Use `/provider` inside OpenClaude
to switch providers at any time.

---

## Creating a Launch Script

Create a convenience script to avoid typing the full path every time:

```bash
cat > ~/launch-openclaude.sh << 'SCRIPT'
#!/bin/bash
cd /data/data/com.termux/files/home/openclaude
source ~/.config/openclaude/provider.env 2>/dev/null
node dist/cli.mjs "$@"
SCRIPT
chmod 700 ~/launch-openclaude.sh
```

Then run it with:
```bash
bash ~/launch-openclaude.sh
```

Or create a Termux shortcut (long-press home screen → widget → Termux widget)
by creating `~/.shortcuts/launch-openclaude.sh` with the same content.

---

## Restarting After Closing Termux

Every time you reopen Termux, run:

```bash
proot-distro login ubuntu
cd /data/data/com.termux/files/home/openclaude
node dist/cli.mjs
```

Or use your launch script if you created one:
```bash
proot-distro login ubuntu
bash ~/launch-openclaude.sh
```

> **Tip:** Don't swipe Termux away from recent apps mid-session — use the home
> button to minimize instead. Swiping kills the process and loses your session.

---

## Recommended Free Model

**`qwen/qwen3.6-plus-preview:free`** — Best free model on OpenRouter.

- 1M token context window
- Built-in chain-of-thought reasoning
- Native tool use and function calling
- $0/M tokens (preview period — check for current pricing)

### Alternative Free Models

| Model ID | Context | Notes |
|---|---|---|
| `qwen/qwen3-coder:free` | 262K | Best for pure coding tasks |
| `openai/gpt-oss-120b:free` | 131K | OpenAI open model, strong tool calling |
| `nvidia/nemotron-3-super-120b-a12b:free` | 262K | Hybrid MoE, good general use |
| `meta-llama/llama-3.3-70b-instruct:free` | 66K | Reliable, widely tested |

Switch models inside OpenClaude with `/model`, or update your env file:
```bash
sed -i 's/OPENAI_MODEL=.*/OPENAI_MODEL=qwen\/qwen3-coder:free/' ~/.config/openclaude/provider.env
```

---

## Updating OpenClaude

When you pull updates to the repository:

```bash
proot-distro login ubuntu
cd /data/data/com.termux/files/home/openclaude
git pull
bun install
bun run build
```

---

## Security Hardening

### API Key Protection

1. **Restrict config file permissions** (already done in setup):
   ```bash
   chmod 600 ~/.config/openclaude/provider.env
   ```

2. **Restrict config directory**:
   ```bash
   chmod 700 ~/.config/openclaude
   ```

3. **Never commit API keys** — the `.env.example` file is safe (keys are
   placeholders), but never create a `.env` file with real keys inside the
   repo.

4. **Rotate keys periodically** — if you suspect a key is exposed, revoke it
   immediately at [openrouter.ai/keys](https://openrouter.ai/keys) and
   generate a new one.

### proot Environment Security

- proot provides **filesystem isolation only**, not full container isolation.
  Processes share the Android kernel. Treat the proot environment as a
  convenience sandbox, not a security boundary.
- Do not run OpenClaude as root inside proot. The default `proot-distro login`
  runs as your user, which is correct.
- Be aware that proot processes can see Termux's filesystem at
  `/data/data/com.termux/files/home/`. Avoid storing sensitive files outside
  the proot Ubuntu root unless you understand this.

### Network Security

- OpenRouter traffic uses HTTPS by default — your API key is encrypted in
  transit.
- If you use a custom `OPENAI_BASE_URL`, ensure it uses HTTPS. HTTP endpoints
  transmit your API key in plaintext.

---

## Troubleshooting

### "bun: command not found" inside proot

Bun was installed but `.bashrc` wasn't sourced. Run:
```bash
source ~/.bashrc
```
Or install Bun again:
```bash
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc
```

### Build fails with "out of memory"

Termux on devices with ≤ 3 GB RAM may run out of memory during build. Try:
```bash
# Increase swap temporarily
fallocate -l 512M /tmp/swapfile
chmod 600 /tmp/swapfile
mkswap /tmp/swapfile
swapon /tmp/swapfile

# Build
bun run build

# Clean up swap after build
swapoff /tmp/swapfile
rm /tmp/swapfile
```

### "error: script not found" or wrong Bun version

Ensure Bun ≥ 1.3.13 is installed inside proot:
```bash
bun --version
```
If outdated, reinstall:
```bash
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc
```

### OpenClaude exits immediately with no output

The Node.js version may be too old. Check:
```bash
node --version  # must be v22+
```
If it's v20 or older, update inside proot:
```bash
# Re-install from the Ubuntu package manager inside proot
apt update && apt install -y nodejs
```
Or reinstall Node.js LTS from Termux's `pkg` and ensure proot picks it up.

### "EPERM: operation not permitted" errors

This usually means a permission issue with the proot filesystem. Ensure you're
running as your user (not root):
```bash
whoami  # should show your Termux UID, not root
```
If you accidentally ran commands as root inside proot, fix ownership:
```bash
# Exit proot first, then reset the proot filesystem
proot-distro reset ubuntu
# You'll need to re-do Steps 4–6
```

### "CERT_HAS_EXPIRED" or SSL errors

Termux's CA certificates may be outdated:
```bash
# Inside proot Ubuntu
apt update && apt install -y ca-certificates
update-ca-certificates
```

### Keyboard issues (Enter/Backspace not working)

Termux sometimes has keyboard mapping issues. Try:
- `/terminal-setup` inside OpenClaude to configure paste behavior
- Install the [Termux:API](https://f-droid.org/en/packages/com.termux.api/) add-on for better clipboard support

### API key not detected

Ensure the env file is sourced:
```bash
source ~/.config/openclaude/provider.env
echo $OPENAI_API_KEY  # should show your key (first few chars only)
```

If using the launch script, ensure it sources the env file before starting.

### "npm warn" or "ERR!" during bun install

This can happen with native dependencies on ARM. Try:
```bash
bun install --no-optional
```
If the build still fails, the specific dependency may not support Android ARM.
Check the OpenClaude issues for known ARM compatibility problems.

### proot-distro login hangs

If `proot-distro login ubuntu` hangs or crashes:
```bash
proot-distro reset ubuntu
```
Then redo the setup from Step 4.

---

## Performance Tips

1. **Use a device with ≥ 4 GB RAM** — OpenClaude's build process and runtime
   are memory-intensive. 3 GB devices work but may experience slowdowns.

2. **Keep Termux in the foreground** during builds — Android may kill background
   Termux processes to reclaim memory.

3. **Close unnecessary apps** before running OpenClaude to free RAM.

4. **Use `--no-optional` for faster installs** if you don't need all optional
   native dependencies:
   ```bash
   bun install --no-optional
   ```

5. **Set Ollama context explicitly** if running local models to avoid
   auto-compact overhead:
   ```bash
   export OPENCLAUDE_OLLAMA_NUM_CTX=32768
   ```

6. **Reduce context window** for smaller devices if the model supports it:
   ```bash
   export CLAUDE_CODE_OPENAI_FALLBACK_CONTEXT_WINDOW=16384
   ```

7. **Use background sessions** for long tasks to avoid blocking the UI:
   ```bash
   node dist/cli.mjs --bg "fix failing tests"
   ```

---

## Storage Management

The proot Ubuntu environment and OpenClaude dependencies can use significant
space. To check usage:

```bash
# Inside proot
du -sh /data/data/com.termux/files/home/openclaude
du -sh ~
df -h /data
```

To reclaim space after a successful build:
```bash
# Remove build cache
rm -rf /data/data/com.termux/files/home/openclaude/node_modules/.cache
```

To remove the proot environment entirely:
```bash
# From Termux (outside proot)
proot-distro remove ubuntu
```

---

## Why Not Groq or Cerebras?

Both were tested and fail due to OpenClaude's large system prompt (~50K tokens):

- **Groq free tier**: TPM limits too low (6K–12K tokens/min)
- **Cerebras free tier**: TPM limits exceeded, even on `llama3.1-8b`

OpenRouter free models have no TPM restrictions — only 20 req/min and 200
req/day.

---

## FAQ

**Q: Can I use OpenClaude without proot?**
A: Not for building. Bun's Linux binary requires a glibc environment, which
Termux's bionic-based system doesn't provide. However, if you install from npm
(`npm install -g @gitlawb/openclaude@latest`), the pre-built bundle may work
directly in Termux without proot. This is untested and not officially
supported.

**Q: Can I use the Anthropic provider on Android?**
A: Yes — set `ANTHROPIC_API_KEY` instead of the OpenAI vars. Anthropic's API
works from any network. Use `/provider` to switch.

**Q: Does the buddy/companion work in Termux?**
A: The pixel-art companion requires a terminal ≥ 100 columns wide. Most modern
phone terminals support this in landscape mode. In portrait, the buddy degrades
gracefully to line art.

**Q: How do I update OpenClaude?**
A: Run `git pull` then `bun run build` inside the proot Ubuntu environment.
See the Updating section above.

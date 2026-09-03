# OpenClaude Lite (Python)

A **lightweight coding assistant in pure Python** for phones and low-power
devices. It speaks the OpenAI-compatible `/chat/completions` API, so it works
with OpenRouter, GitHub Models, OpenAI, DeepSeek, Gemini (OpenAI-compat mode),
and Ollama (local).

> **Why this exists:** the full OpenClaude CLI is a ~700k-line TypeScript app
> that must be compiled with Bun — and **Bun is 64-bit only**, so 32-bit
> (armv7) phones cannot build it. OpenClaude Lite uses **only the Python
> standard library**: no pip, no venv, no proot needed. It runs in native
> Termux on any architecture, including 32-bit.

## Quick start (Termux)

```bash
pkg update && pkg upgrade
pkg install python

# Download the tool (or clone this repo and cd into python/)
curl -fsSL -o openclaude_lite.py \
  https://raw.githubusercontent.com/davivida661-collab/openclaude/main/python/openclaude_lite.py

# Configure a free provider (OpenRouter example — get a key at openrouter.ai/keys)
mkdir -p ~/.config
cat > ~/.config/openclaude-lite.env << 'EOF'
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-XXXXXX
OPENAI_MODEL=qwen/qwen3.6-plus-preview:free
EOF
chmod 600 ~/.config/openclaude-lite.env

# Chat
python3 openclaude_lite.py
```

## Usage

```bash
python3 openclaude_lite.py                 # interactive chat
python3 openclaude_lite.py "explique este código"   # one-shot question
python3 openclaude_lite.py --yes           # auto-approve shell commands
python3 openclaude_lite.py -m gpt-4o-mini  # switch model
python3 openclaude_lite.py --provider ollama  # local models via Ollama
python3 openclaude_lite.py --setup         # print full config instructions
```

### In-chat commands

| Command | What it does |
|---|---|
| `/help` | show help |
| `/clear` | start a fresh conversation |
| `/model <id>` | switch model on the fly |
| `/tools on\|off` | enable/disable file & shell tools |
| `/quit`, `/exit` | leave |

## Configuration

The tool reads `~/.config/openclaude-lite.env` (simple `KEY=VALUE` lines,
`chmod 600`) and falls back to exported environment variables.

| Variable | Meaning |
|---|---|
| `OPENAI_BASE_URL` | endpoint base (provider-specific, see below) |
| `OPENAI_API_KEY` | API key (`GEMINI_API_KEY` is also accepted) |
| `OPENAI_MODEL` | model id |
| `OPENAI_MAX_TOKENS` | max output tokens (default 4096) |

### Provider presets (`--provider`)

| Provider | Base URL | Default model | Key |
|---|---|---|---|
| `openrouter` | `https://openrouter.ai/api/v1` | `qwen/qwen3.6-plus-preview:free` | `sk-or-…` |
| `github` | `https://models.inference.ai.azure.com/v1` | `gpt-4o-mini` | GitHub PAT |
| `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` | `sk-…` |
| `deepseek` | `https://api.deepseek.com/v1` | `deepseek-chat` | DeepSeek key |
| `gemini` | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.0-flash` | Gemini key |
| `ollama` | `http://localhost:11434/v1` | `qwen2.5-coder:7b` | any value (`ollama`) |
| `custom` | set `OPENAI_BASE_URL` yourself | via `OPENAI_MODEL` | your key |

## Tools & permissions

OpenClaude Lite can read/write files and run shell commands to do real work.

- File tools (`read_file`, `write_file`, `list_dir`) run automatically.
- **Shell commands always ask for approval first** unless you start with
  `--yes`. Denied commands are reported back to the model as denied — it will
  not silently run anything.
- Destructive actions (deleting files, `git push`) are left to you: approve
  them only when you intend them.
- Tool steps are capped (12 per turn) so a confused model cannot loop forever.

## Security notes

- Never store keys in `~/.bashrc` or commit them. The config file above is
  `chmod 600` (readable only by you).
- The API key is sent only to the `OPENAI_BASE_URL` you configure — check the
  base URL when using third-party gateways.
- Code the assistant writes is yours to review; files are written to the
  current directory (or paths the model requests), and the tool confirms
  writes by reporting bytes written.

## 32-bit (armv7) devices

Python runs natively in Termux on 32-bit ARM — **no proot Ubuntu, no Bun, no
Node.js needed**:

```bash
pkg install python
python3 openclaude_lite.py
```

Check your architecture with `uname -m` (`armv7l`/`armv8l` = 32-bit). Native
Termux Python is the lightest path on old phones.

## Running the tests

```bash
python3 test_openclaude_lite.py
```

Tests spin up a local mock server, so no network or API key is needed. They
verify chat parsing, the tool-call loop (a real file is read and its content
is fed back to the model), config validation, and the CLI entry points.

## Relationship to OpenClaude

This is a deliberately small companion tool for constrained devices — not a
port of the ~700k-line TypeScript OpenClaude. For the full experience on
64-bit machines, follow the main [`ANDROID_INSTALL.md`](../ANDROID_INSTALL.md)
guide. The Lite tool and the full CLI can coexist in the same Termux setup.

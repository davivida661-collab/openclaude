#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaude Lite — a lightweight coding assistant for phones / Termux.

Pure Python standard library: no pip installs, no venv, works on 32-bit
(armv7) Termux and inside proot Ubuntu alike.

It speaks the OpenAI-compatible /chat/completions API, so it works with
OpenRouter, GitHub Models, OpenAI, DeepSeek, Gemini (OpenAI-compat mode),
Ollama (local), and any other OpenAI-compatible endpoint.

This is intentionally tiny next to the full TypeScript OpenClaude. It gives
you the core experience on hardware where Bun cannot run:
    chat REPL  +  file tools  +  safe shell execution  +  provider switching

Run:
    python3 openclaude_lite.py                # interactive chat
    python3 openclaude_lite.py "question"     # one-shot
    python3 openclaude_lite.py --setup        # show configuration template
    python3 openclaude_lite.py --provider github models/gpt-4o-mini
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

VERSION = "0.1.0"
CONFIG_FILE = os.path.expanduser("~/.config/openclaude-lite.env")

# --------------------------------------------------------------------------
# Provider presets (endpoint base; "/chat/completions" is appended)
# --------------------------------------------------------------------------
PROVIDERS = {
    "openrouter": {
        "base": "https://openrouter.ai/api/v1",
        "model": "qwen/qwen3.6-plus-preview:free",
        "note": "Free tier; get a key at https://openrouter.ai/keys",
    },
    "github": {
        "base": "https://models.inference.ai.azure.com/v1",
        "model": "gpt-4o-mini",
        "note": "GitHub Models; use a GitHub PAT as the key",
    },
    "openai": {
        "base": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "note": "Standard OpenAI key",
    },
    "deepseek": {
        "base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "note": "https://platform.deepseek.com",
    },
    "gemini": {
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
        "note": "OpenAI-compatible endpoint; needs GEMINI_API_KEY or OPENAI_API_KEY",
    },
    "ollama": {
        "base": "http://localhost:11434/v1",
        "model": "qwen2.5-coder:7b",
        "note": "Local models; key can be any dummy value",
    },
}

SYSTEM_PROMPT = (
    "You are OpenClaude Lite, a coding assistant running in a terminal "
    "(often Termux on Android). You can read and write files and run shell "
    "commands through tools to help the user with real work. Be concise, "
    "precise and practical. Reply in the same language the user writes in. "
    "Never invent tool results: if a tool errors, report the error. "
    "When asked to write code, write complete working code and say where to "
    "put it. Ask before destructive actions (deleting files, git push)."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file. Returns the content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (absolute or relative)."},
                    "limit": {"type": "integer", "description": "Max lines to read (optional)."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with text content. Creates parent directories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path."},
                    "content": {"type": "string", "description": "Full file content."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories under a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default '.')."},
                    "max_items": {"type": "integer", "description": "Limit entries shown."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the current directory. The user is asked before the first execution unless --yes is used. Prefer read-only commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run."},
                },
                "required": ["command"],
            },
        },
    },
]

# --------------------------------------------------------------------------
# Color helpers (auto-disabled when not a TTY)
# --------------------------------------------------------------------------
_COLORS = sys.stdout.isatty()


def paint(code: str, text: str) -> str:
    if not _COLORS:
        return text
    return f"\033[{code}m{text}\033[0m"


def err(msg: str) -> None:
    print(paint("31", f"error: {msg}"), file=sys.stderr)


def ok(msg: str) -> None:
    print(paint("32", msg))


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
def load_config_file() -> None:
    """Load simple KEY=VALUE lines from ~/.config/openclaude-lite.env (if present)."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass
    except OSError as exc:
        err(f"could not read {CONFIG_FILE}: {exc}")


def guess_provider_from_key(key: str) -> str:
    if key.startswith("sk-or-"):
        return "openrouter"
    if key.startswith("sk-ant-"):
        return "anthropic"  # not OpenAI-compatible; handled as error below
    return "openai"


def build_config(args: argparse.Namespace) -> dict:
    load_config_file()

    provider = (args.provider or "").lower()
    if not provider:
        key_hint = os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
        if key_hint and os.environ.get("OPENAI_BASE_URL"):
            provider = "custom"
        else:
            provider = guess_provider_from_key(key_hint) if key_hint else "openrouter"

    preset = PROVIDERS.get(provider)
    if preset is None:
        if provider == "custom":
            preset = {"base": "", "model": "", "note": ""}
        else:
            err(f"unknown provider {provider!r}. Known: {', '.join(sorted(PROVIDERS))}, custom")
            sys.exit(2)

    base = (
        os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
        or preset["base"]
    )
    if not base:
        err("OPENAI_BASE_URL is required for --provider custom")
        sys.exit(2)

    model = args.model or os.environ.get("OPENAI_MODEL") or preset["model"]
    if not model:
        err("no model selected — set OPENAI_MODEL or pass --model")
        sys.exit(2)

    api_key = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    )
    if provider == "ollama":
        api_key = api_key or "ollama"
    if not api_key and "localhost" not in base and "127.0.0.1" not in base:
        err(
            f"no API key found. Export OPENAI_API_KEY (provider: {provider}).\n"
            f"    {preset.get('note', '')}\n"
            f"Or store it securely in {CONFIG_FILE} (chmod 600) — see --setup."
        )
        sys.exit(2)

    return {
        "provider": provider,
        "base": base,
        "model": model,
        "api_key": api_key,
        "auto_yes": args.yes,
        "max_tokens": int(os.environ.get("OPENAI_MAX_TOKENS", "4096")),
        "max_agent_steps": 12,
    }


# --------------------------------------------------------------------------
# HTTP client (stdlib only)
# --------------------------------------------------------------------------
def chat_request(cfg: dict, messages: list, tools=None) -> dict:
    url = cfg["base"] + "/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "max_tokens": cfg["max_tokens"],
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    body = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
    }
    if cfg["provider"] == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/davivida661-collab/openclaude"
        headers["X-Title"] = "OpenClaude Lite (Termux)"

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        hint = ""
        if exc.code in (401, 403):
            hint = " — the API key was rejected; check OPENAI_API_KEY"
        elif exc.code == 402:
            hint = " — the provider says the account has no credit / the model is paid"
        elif exc.code == 404:
            hint = " — the model id or endpoint was not found; check OPENAI_MODEL"
        elif exc.code == 429:
            hint = " — rate limit; wait a moment and retry"
        err(f"HTTP {exc.code} from {cfg['provider']}{hint}\n{detail}")
        raise
    except urllib.error.URLError as exc:
        err(f"network error: {exc.reason}")
        raise


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
def tool_read_file(args: dict) -> str:
    path = args.get("path", "")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        limit = args.get("limit")
        if limit and int(limit) > 0:
            lines = lines[: int(limit)]
        return "".join(lines) or "(empty file)"
    except OSError as exc:
        return f"error: {exc}"


def tool_write_file(args: dict) -> str:
    path = args.get("path", "")
    content = args.get("content", "")
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return f"wrote {len(content)} bytes to {path}"
    except OSError as exc:
        return f"error: {exc}"


def tool_list_dir(args: dict) -> str:
    path = args.get("path") or "."
    try:
        entries = sorted(os.listdir(path))
    except OSError as exc:
        return f"error: {exc}"
    max_items = args.get("max_items") or 200
    shown = entries[: max_items]
    lines = []
    for name in shown:
        full = os.path.join(path, name)
        try:
            kind = "dir " if os.path.isdir(full) else "file"
        except OSError:
            kind = "    "
        lines.append(f"{kind}  {name}")
    if len(entries) > len(shown):
        lines.append(f"... {len(entries) - len(shown)} more entries")
    return "\n".join(lines) if lines else "(empty directory)"


def tool_run_command(args: dict, cfg: dict) -> str:
    command = args.get("command", "")
    if not command:
        return "error: empty command"
    if not cfg["auto_yes"] and sys.stdin.isatty():
        print(paint("33", f"Run command? (y/N)  $ {command}"))
        try:
            answer = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        if answer not in ("y", "yes"):
            return "denied by user (shell execution requires approval)"
    elif not cfg["auto_yes"]:
        return "denied by user (non-interactive; pass --yes to allow shell commands)"
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        out = proc.stdout or ""
        if proc.stderr:
            out += "\n[stderr]\n" + proc.stderr
        out = out.strip()
        if not out:
            out = f"(exit code {proc.returncode}, no output)"
        return out + f"\n[exit code {proc.returncode}]"
    except subprocess.TimeoutExpired:
        return "error: command timed out after 180s"
    except OSError as exc:
        return f"error: {exc}"


def execute_tool(name: str, raw_args: str, cfg: dict) -> str:
    try:
        args = json.loads(raw_args) if raw_args.strip() else {}
        if not isinstance(args, dict):
            args = {}
    except json.JSONDecodeError:
        return f"error: tool arguments were not valid JSON: {raw_args[:200]}"
    if name == "read_file":
        return tool_read_file(args)
    if name == "write_file":
        return tool_write_file(args)
    if name == "list_dir":
        return tool_list_dir(args)
    if name == "run_command":
        return tool_run_command(args, cfg)
    return f"error: unknown tool {name!r}"


# --------------------------------------------------------------------------
# Agent loop
# --------------------------------------------------------------------------
def trim_messages(messages: list, max_messages: int = 40) -> list:
    """Keep the system prompt and the most recent turns (context budget)."""
    if len(messages) <= max_messages:
        return messages
    head = [m for m in messages if m.get("role") == "system"][:1]
    tail = [m for m in messages if m.get("role") != "system"][-(max_messages - len(head)):]
    return head + tail


def agent_turn(cfg: dict, messages: list, tools_enabled: bool) -> str:
    """Run one model call plus any tool calls it requests. Returns the final text."""
    tools = TOOLS if tools_enabled else None
    for _ in range(cfg["max_agent_steps"]):
        response = chat_request(cfg, messages, tools=tools)
        try:
            choice = response["choices"][0]
            message = choice.get("message", {})
        except (KeyError, IndexError):
            err(f"unexpected response shape: {json.dumps(response)[:300]}")
            return ""

        tool_calls = message.get("tool_calls")
        content = message.get("content") or ""

        messages.append(
            {
                "role": "assistant",
                "content": content,
                **({"tool_calls": tool_calls} if tool_calls else {}),
            }
        )

        if not tool_calls:
            return content

        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            raw_args = fn.get("arguments", "")
            print(paint("36", f"• tool: {name}"))
            result = execute_tool(name, raw_args, cfg)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": result[:16000],
                }
            )

        # Some providers reject tool-call turns after too many iterations; stop politely.
        print(paint("90", "  (thinking…)"))

    return "(stopped after too many tool steps — ask me to continue)"


# --------------------------------------------------------------------------
# Chat sessions
# --------------------------------------------------------------------------
def one_shot(cfg: dict, prompt: str, tools_enabled: bool) -> None:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    print(agent_turn(cfg, messages, tools_enabled))


def repl(cfg: dict, tools_enabled: bool) -> None:
    import readline  # noqa: F401  (line editing on Termux)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    tools_on = tools_enabled

    print(paint("36", f"OpenClaude Lite {VERSION} — provider: {cfg['provider']} — model: {cfg['model']}"))
    print(paint("90", "Type /help for commands. Ctrl+D exits."))
    if not cfg["auto_yes"]:
        print(paint("33", "Shell commands need your approval (use --yes to auto-approve)."))

    while True:
        try:
            prompt_text = input(paint("32", "\n❯ "))
        except (EOFError, KeyboardInterrupt):
            print()
            return
        prompt_text = prompt_text.strip()
        if not prompt_text:
            continue

        if prompt_text.startswith("/"):
            if prompt_text in ("/quit", "/exit", "/q"):
                return
            if prompt_text in ("/help", "/h"):
                print(
                    "  /help            this help\n"
                    "  /clear           start a fresh conversation\n"
                    "  /model <id>      switch model (e.g. /model gpt-4o-mini)\n"
                    "  /tools on|off    enable/disable file & shell tools\n"
                    "  /quit, /exit     leave\n"
                    "  /version         show version"
                )
                continue
            if prompt_text in ("/clear", "/new"):
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                ok("conversation cleared")
                continue
            if prompt_text in ("/version", "/v"):
                print(f"OpenClaude Lite {VERSION} (provider {cfg['provider']}, model {cfg['model']})")
                continue
            if prompt_text.startswith("/model "):
                cfg["model"] = prompt_text.split(None, 1)[1].strip()
                ok(f"model switched to {cfg['model']}")
                continue
            if prompt_text.startswith("/tools"):
                value = prompt_text.split(None, 1)[1].strip().lower() if " " in prompt_text else "on"
                tools_on = value in ("on", "1", "yes", "true")
                ok(f"tools {'enabled' if tools_on else 'disabled'}")
                continue
            print(paint("33", "unknown command — try /help"))
            continue

        messages.append({"role": "user", "content": prompt_text})
        messages = trim_messages(messages)
        try:
            answer = agent_turn(cfg, messages, tools_on)
        except (urllib.error.HTTPError, urllib.error.URLError):
            messages.pop()  # drop the failed user turn so retry is clean
            continue
        if answer:
            print()
            print(paint("90", "───"))
            print(answer)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def setup_help() -> None:
    print("""OpenClaude Lite configuration
============================

1) Create a private config file (recommended):

   mkdir -p ~/.config
   cat > ~/.config/openclaude-lite.env << 'EOF'
   OPENAI_BASE_URL=https://openrouter.ai/api/v1
   OPENAI_API_KEY=sk-or-xxxxxxxx
   OPENAI_MODEL=qwen/qwen3.6-plus-preview:free
   EOF
   chmod 600 ~/.config/openclaude-lite.env

   Available providers (--provider): openrouter, github, openai,
   deepseek, gemini, ollama, custom.

   Ollama (local models):
   OPENAI_BASE_URL=http://localhost:11434/v1
   OPENAI_API_KEY=ollama
   OPENAI_MODEL=qwen2.5-coder:7b

   GitHub Models:
   OPENAI_BASE_URL=https://models.inference.ai.azure.com/v1
   OPENAI_API_KEY=github_pat_xxxx   (or GITHUB_TOKEN)
   OPENAI_MODEL=gpt-4o-mini

2) Run:

   python3 openclaude_lite.py            # interactive chat
   python3 openclaude_lite.py "fix this" # one-shot
   python3 openclaude_lite.py --yes      # auto-approve shell commands
""")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="openclaude_lite",
        description="OpenClaude Lite — lightweight coding assistant (Python, stdlib-only).",
    )
    parser.add_argument("prompt", nargs="?", help="one-shot question (omit for interactive chat)")
    parser.add_argument("-m", "--model", help="model id (overrides OPENAI_MODEL)")
    parser.add_argument("-p", "--provider", help="openrouter | github | openai | deepseek | gemini | ollama | custom")
    parser.add_argument("--yes", action="store_true", help="auto-approve shell commands")
    parser.add_argument("--no-tools", action="store_true", help="disable file/shell tools")
    parser.add_argument("--setup", action="store_true", help="print configuration instructions")
    parser.add_argument("--version", action="version", version=f"OpenClaude Lite {VERSION}")
    args = parser.parse_args()

    if args.setup:
        setup_help()
        return

    cfg = build_config(args)
    tools_enabled = not args.no_tools

    if args.prompt:
        one_shot(cfg, args.prompt, tools_enabled)
    else:
        repl(cfg, tools_enabled)


if __name__ == "__main__":
    main()

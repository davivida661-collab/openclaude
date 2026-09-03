#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-end smoke tests for OpenClaude Lite.

Runs the agent against a local mock OpenAI-compatible server (stdlib http.server)
so no network or API key is needed. Verifies:
  1. plain chat responses are parsed and returned,
  2. the tool-call loop executes a real tool (read_file) and feeds the result
     back to the model,
  3. config validation rejects a missing API key.
"""

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import openclaude_lite as lite  # noqa: E402


class MockState:
    def __init__(self):
        self.calls = []
        self.tool_file = None
        self.final_text = "O arquivo existe e a leitura funcionou."

    def response_for(self, payload):
        self.calls.append(payload)
        if len(self.calls) == 1:
            # Ask the model loop to read a file.
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": json.dumps({"path": self.tool_file}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        return {"choices": [{"message": {"role": "assistant", "content": self.final_text}}]}


state = MockState()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        response = state.response_for(body)
        data = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # keep test output clean
        pass


def run_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_plain_chat():
    server = run_server()
    try:
        cfg = {
            "provider": "custom",
            "base": f"http://127.0.0.1:{server.server_address[1]}",
            "model": "mock-model",
            "api_key": "sk-mock",
            "auto_yes": True,
            "max_tokens": 512,
            "max_agent_steps": 6,
        }
        messages = [{"role": "user", "content": "hello"}]
        # First call triggers a tool call; prime the file.
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            fh.write("conteudo do arquivo de teste\n")
            state.tool_file = fh.name
        text = lite.agent_turn(cfg, messages, tools_enabled=True)
        assert state.final_text in text, f"expected final text in {text!r}"
        # The second request must contain the tool result from read_file.
        second = state.calls[1]
        roles = [m.get("role") for m in second["messages"]]
        assert "tool" in roles, f"expected a tool result message in {roles}"
        tool_msg = next(m for m in second["messages"] if m.get("role") == "tool")
        assert "conteudo do arquivo de teste" in tool_msg["content"], tool_msg["content"]
        os.unlink(state.tool_file)
        print("PASS plain chat + tool loop (read_file executed, result fed back)")
    finally:
        server.shutdown()


def test_config_rejects_missing_key():
    old = {k: os.environ.get(k) for k in ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL")}
    try:
        for k in old:
            os.environ.pop(k, None)
        os.environ["OPENAI_MODEL"] = "mock-model"
        parser = lite.argparse.ArgumentParser()
        args = parser.parse_args([])  # noqa: S — bare Namespace shim below
        # argparse would exit on --setup etc.; craft Namespace manually instead.
        import types

        args = types.SimpleNamespace(prompt=None, model=None, provider=None, yes=False, no_tools=False, setup=False)
        try:
            lite.build_config(args)
            raise AssertionError("expected SystemExit for missing API key")
        except SystemExit as code:
            assert code.code == 2, f"expected exit code 2, got {code.code}"
        print("PASS missing API key is rejected with exit code 2")
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_cli_setup_and_version():
    code = os.system(f"{sys.executable} {os.path.abspath(lite.__file__)} --setup > /dev/null 2>&1")
    assert code == 0, "openclaude_lite.py --setup failed"
    code = os.system(f"{sys.executable} {os.path.abspath(lite.__file__)} --version > /dev/null 2>&1")
    assert code == 0, "openclaude_lite.py --version failed"
    print("PASS --setup and --version exit cleanly")


if __name__ == "__main__":
    test_plain_chat()
    test_config_rejects_missing_key()
    test_cli_setup_and_version()
    print("\nAll OpenClaude Lite tests passed.")

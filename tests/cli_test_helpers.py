from __future__ import annotations

import json

from paperclip_cli.cli import cli

BASE_URL = "http://localhost:3100"


def run_cli(runner, *args: str, **kwargs):
    return runner.invoke(cli, ["--url", BASE_URL, *args], **kwargs)


def request_json(call) -> dict:
    body = call.request.body
    if isinstance(body, bytes):
        body = body.decode()
    return json.loads(body) if body else {}

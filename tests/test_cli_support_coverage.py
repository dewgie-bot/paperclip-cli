from __future__ import annotations

import json

import pytest
import responses as rsps

from paperclip_cli import cli as cli_module
from paperclip_cli import client as client_module
from paperclip_cli.cli import cli
from paperclip_cli.client import PaperclipClient, PaperclipError

from .cli_test_helpers import BASE_URL, request_json, run_cli


@pytest.mark.parametrize(
    "command",
    ["agent", "company", "goal", "heartbeat", "issue", "plugin", "project", "routine", "secret"],
)
def test_group_without_subcommand_shows_help(runner, command):
    result = run_cli(runner, command)
    assert result.exit_code == 0
    assert "Usage:" in result.output

def test_cli_configure_writes_config_and_client_reads_it(runner, monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(client_module, "CONFIG_PATH", config_path)

    result = runner.invoke(cli, ["configure", "--url", f"{BASE_URL}/", "--token", "secret-token"])
    assert result.exit_code == 0
    assert "Configuration saved" in result.output
    assert "Token: ****" in result.output

    saved = json.loads(config_path.read_text())
    assert saved == {"base_url": BASE_URL, "token": "secret-token"}

    client = PaperclipClient()
    assert client.base_url == BASE_URL
    assert client.token == "secret-token"

def test_configure_ignores_invalid_existing_config(runner, monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{invalid json")
    monkeypatch.setattr(cli_module, "CONFIG_PATH", config_path)

    result = runner.invoke(cli, ["configure", "--url", f"{BASE_URL}/"])
    assert result.exit_code == 0

    saved = json.loads(config_path.read_text())
    assert saved == {"base_url": BASE_URL}

def test_client_defaults_when_config_is_invalid(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{broken")
    monkeypatch.setattr(client_module, "CONFIG_PATH", config_path)

    client = PaperclipClient()
    assert client.base_url == client_module.DEFAULT_URL
    assert client.token == ""
    assert client._headers() == {"Content-Type": "application/json"}

@rsps.activate
def test_client_handles_204_and_text_errors(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"base_url": BASE_URL, "token": "cfg-token"}))
    monkeypatch.setattr(client_module, "CONFIG_PATH", config_path)

    client = PaperclipClient()

    rsps.add(rsps.POST, f"{BASE_URL}/api/plugins/install", status=204)
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", status=204)
    rsps.add(rsps.DELETE, f"{BASE_URL}/api/issues/i1", status=204)
    rsps.add(rsps.GET, f"{BASE_URL}/api/plugins", body="boom", status=500)

    assert client.post("/plugins/install", {"name": "x"}) == {}
    assert client.patch("/projects/p1", {"name": "x"}) == {}
    assert client.delete("/issues/i1") == {}
    assert rsps.calls[0].request.headers["Authorization"] == "Bearer cfg-token"

    with pytest.raises(PaperclipError) as exc_info:
        client.get("/plugins")
    assert exc_info.value.status_code == 500
    assert str(exc_info.value) == "HTTP 500: boom"

@rsps.activate
def test_status_success_and_paperclip_error_output(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/health", json={"version": "1.2.3"})
    rsps.add(rsps.GET, f"{BASE_URL}/api/health", json={"error": "down"}, status=503)

    ok_result = run_cli(runner, "status")
    assert ok_result.exit_code == 0
    assert "Paperclip is running" in ok_result.output
    assert '"version": "1.2.3"' in ok_result.output

    error_result = run_cli(runner, "status")
    assert error_result.exit_code == 1
    assert "Paperclip is not reachable" in error_result.output
    assert "HTTP 503: down" in error_result.output

def test_status_handles_unexpected_exceptions_in_json_and_text(runner, monkeypatch):
    monkeypatch.setattr(PaperclipClient, "health", lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

    json_result = run_cli(runner, "status", "--json")
    assert json_result.exit_code == 1
    assert json.loads(json_result.output)["error"] == "boom"

    text_result = run_cli(runner, "status")
    assert text_result.exit_code == 1
    assert "Could not connect" in text_result.output
    assert "boom" in text_result.output

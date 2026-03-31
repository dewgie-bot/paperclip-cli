from __future__ import annotations

import pytest
import responses as rsps

from .cli_test_helpers import BASE_URL, run_cli


ERROR_CASES = [
    (["company", "list"], rsps.GET, f"{BASE_URL}/api/companies"),
    (["company", "create", "--name", "Acme"], rsps.POST, f"{BASE_URL}/api/companies"),
    (["company", "get", "c1"], rsps.GET, f"{BASE_URL}/api/companies/c1"),
    (["company", "update", "c1", "--name", "Renamed"], rsps.PATCH, f"{BASE_URL}/api/companies/c1"),
    (["company", "delete", "c1", "--yes", "--force"], rsps.DELETE, f"{BASE_URL}/api/companies/c1"),
    (["company", "archive", "c1"], rsps.POST, f"{BASE_URL}/api/companies/c1/archive"),
    (["company", "unarchive", "c1"], rsps.PATCH, f"{BASE_URL}/api/companies/c1"),
    (["agent", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/agents"),
    (["agent", "create", "--company", "co1", "--name", "Alice"], rsps.POST, f"{BASE_URL}/api/companies/co1/agents"),
    (["agent", "get", "a1"], rsps.GET, f"{BASE_URL}/api/agents/a1"),
    (["agent", "update", "a1", "--name", "Alice"], rsps.PATCH, f"{BASE_URL}/api/agents/a1"),
    (["agent", "delete", "a1", "--yes"], rsps.DELETE, f"{BASE_URL}/api/agents/a1"),
    (["agent", "wakeup", "a1"], rsps.POST, f"{BASE_URL}/api/agents/a1/wakeup"),
    (["agent", "set-instructions", "a1", "--path", "/tmp/AGENTS.md"], rsps.PATCH, f"{BASE_URL}/api/agents/a1/instructions-path"),
    (["goal", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/goals"),
    (["goal", "create", "--company", "co1", "--title", "Launch"], rsps.POST, f"{BASE_URL}/api/companies/co1/goals"),
    (["goal", "update", "g1", "--title", "Launch"], rsps.PATCH, f"{BASE_URL}/api/goals/g1"),
    (["goal", "delete", "g1", "--yes"], rsps.DELETE, f"{BASE_URL}/api/goals/g1"),
    (["goal", "get", "g1"], rsps.GET, f"{BASE_URL}/api/goals/g1"),
    (["issue", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/issues"),
    (["issue", "create", "--company", "co1", "--title", "Bug"], rsps.POST, f"{BASE_URL}/api/companies/co1/issues"),
    (["issue", "update", "i1", "--title", "Bug"], rsps.PATCH, f"{BASE_URL}/api/issues/i1"),
    (["issue", "delete", "i1", "--yes"], rsps.DELETE, f"{BASE_URL}/api/issues/i1"),
    (["issue", "get", "i1"], rsps.GET, f"{BASE_URL}/api/issues/i1"),
    (["approval", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/approvals"),
    (["approval", "approve", "ap1"], rsps.POST, f"{BASE_URL}/api/approvals/ap1/approve"),
    (["approval", "reject", "ap1"], rsps.POST, f"{BASE_URL}/api/approvals/ap1/reject"),
    (["plugin", "list"], rsps.GET, f"{BASE_URL}/api/plugins"),
    (["plugin", "examples"], rsps.GET, f"{BASE_URL}/api/plugins/examples"),
    (["plugin", "install", "clock"], rsps.POST, f"{BASE_URL}/api/plugins/install"),
    (["project", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/projects"),
    (["project", "create", "--company", "co1", "--name", "Roadmap"], rsps.POST, f"{BASE_URL}/api/companies/co1/projects"),
    (["project", "get", "p1"], rsps.GET, f"{BASE_URL}/api/projects/p1"),
    (["project", "update", "p1", "--name", "Roadmap"], rsps.PATCH, f"{BASE_URL}/api/projects/p1"),
    (["project", "delete", "p1", "--yes", "--force"], rsps.DELETE, f"{BASE_URL}/api/projects/p1"),
    (["project", "archive", "p1"], rsps.PATCH, f"{BASE_URL}/api/projects/p1"),
    (["project", "unarchive", "p1"], rsps.PATCH, f"{BASE_URL}/api/projects/p1"),
    (["routine", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/routines"),
    (["routine", "create", "--company", "co1", "--project", "p1", "--name", "Daily", "--assignee", "a1"], rsps.POST, f"{BASE_URL}/api/companies/co1/routines"),
    (["routine", "get", "r1"], rsps.GET, f"{BASE_URL}/api/routines/r1"),
    (["routine", "update", "r1", "--name", "Daily"], rsps.PATCH, f"{BASE_URL}/api/routines/r1"),
    (["routine", "archive", "r1", "--yes"], rsps.PATCH, f"{BASE_URL}/api/routines/r1"),
    (["routine", "trigger-add", "r1", "--kind", "webhook"], rsps.POST, f"{BASE_URL}/api/routines/r1/triggers"),
    (["routine", "run", "r1"], rsps.POST, f"{BASE_URL}/api/routines/r1/run"),
    (["routine", "runs", "r1"], rsps.GET, f"{BASE_URL}/api/routines/r1/runs"),
    (["routine", "triggers", "r1"], rsps.GET, f"{BASE_URL}/api/routines/r1"),
    (["heartbeat", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/heartbeat-runs"),
    (["secret", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/secrets"),
]


@pytest.mark.parametrize(("args", "method", "url"), ERROR_CASES)
@rsps.activate
def test_commands_render_paperclip_errors(runner, args, method, url):
    rsps.add(method, url, json={"error": "broken"}, status=500)

    result = run_cli(runner, *args)

    assert result.exit_code == 1
    assert "broken" in result.output

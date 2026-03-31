from __future__ import annotations

import json

import responses as rsps

from .cli_test_helpers import BASE_URL, request_json, run_cli


@rsps.activate
def test_project_commands_cover_archive_and_update_validation(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/projects", json={"projects": [{"id": "p1", "name": "Roadmap", "status": "planned", "description": "Quarter"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/projects", json={"projects": []})
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/projects", json={"id": "p2", "name": "Platform"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "name": "Roadmap"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "name": "Platform"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": "2026-03-30T00:00:00.000Z"})
    rsps.add(rsps.DELETE, f"{BASE_URL}/api/projects/p1", status=204)
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": "2026-03-30T00:00:00.000Z"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": None})

    list_result = run_cli(runner, "project", "list", "--company", "co1")
    assert list_result.exit_code == 0
    assert "Roadmap" in list_result.output

    empty_result = run_cli(runner, "project", "list", "--company", "co1")
    assert empty_result.exit_code == 0
    assert "No projects found." in empty_result.output

    create_result = run_cli(
        runner,
        "project",
        "create",
        "--company",
        "co1",
        "--name",
        "Platform",
        "--description",
        "Build it",
        "--goal",
        "g1",
        "--lead",
        "a1",
        "--color",
        "#123456",
    )
    assert create_result.exit_code == 0
    assert request_json(rsps.calls[2]) == {
        "name": "Platform",
        "description": "Build it",
        "goalId": "g1",
        "leadAgentId": "a1",
        "color": "#123456",
    }

    get_result = run_cli(runner, "project", "get", "p1")
    assert get_result.exit_code == 0
    assert '"name": "Roadmap"' in get_result.output

    no_fields = run_cli(runner, "project", "update", "p1")
    assert no_fields.exit_code == 1
    assert "No fields to update" in no_fields.output

    update_result = run_cli(
        runner,
        "project",
        "update",
        "p1",
        "--name",
        "Platform",
        "--description",
        "Fresh",
        "--status",
        "paused",
        "--goal",
        "g2",
        "--lead",
        "a2",
    )
    assert update_result.exit_code == 0
    assert request_json(rsps.calls[4]) == {
        "name": "Platform",
        "description": "Fresh",
        "status": "paused",
        "goalId": "g2",
        "leadAgentId": "a2",
    }

    archive_delete = run_cli(runner, "project", "delete", "p1", "--yes")
    assert archive_delete.exit_code == 0
    archive_payload = request_json(rsps.calls[5])
    assert "archivedAt" in archive_payload

    force_delete = run_cli(runner, "project", "delete", "p1", "--yes", "--force")
    assert force_delete.exit_code == 0
    assert "Deleted project p1" in force_delete.output

    archive_result = run_cli(runner, "project", "archive", "p1")
    assert archive_result.exit_code == 0
    assert "Archived project p1" in archive_result.output

    unarchive_result = run_cli(runner, "project", "unarchive", "p1")
    assert unarchive_result.exit_code == 0
    assert "Unarchived project p1" in unarchive_result.output

@rsps.activate
def test_routine_commands_cover_tables_validation_and_triggers(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/routines", json={"routines": [{
        "id": "r1",
        "title": "Daily sync",
        "status": "active",
        "concurrencyPolicy": "coalesce_if_active",
        "assigneeAgentId": "a1",
    }]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/routines", json={"routines": []})
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/routines", json={"id": "r2", "title": "Reporter"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1", json={"id": "r1", "title": "Daily sync"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/routines/r1", json={"id": "r1", "title": "Updated"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/routines/r1", json={"id": "r1", "status": "archived"})
    rsps.add(rsps.POST, f"{BASE_URL}/api/routines/r1/triggers", json={"trigger": {
        "id": "t1",
        "kind": "schedule",
        "nextRunAt": "2026-03-31T09:00:00.000Z",
    }})
    rsps.add(rsps.POST, f"{BASE_URL}/api/routines/r1/triggers", json={"id": "t2", "kind": "webhook"})
    rsps.add(rsps.POST, f"{BASE_URL}/api/routines/r1/run", json={"runId": "run-1"})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1/runs", json={"runs": [{
        "id": "run-1",
        "status": "success",
        "source": "manual",
        "triggeredAt": "2026-03-30T03:00:00.000Z",
        "linkedIssueId": "i1",
    }]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1", json={"triggers": []})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1", json={"triggers": [{
        "id": "t1",
        "kind": "schedule",
        "enabled": True,
        "cronExpression": "0 9 * * *",
        "nextRunAt": "2026-03-31T09:00:00.000Z",
    }, {
        "id": "t2",
        "kind": "webhook",
        "enabled": False,
        "signingMode": "hmac",
        "nextRunAt": None,
    }]})

    list_result = run_cli(runner, "routine", "list", "--company", "co1")
    assert list_result.exit_code == 0
    assert "Daily sync" in list_result.output

    empty_result = run_cli(runner, "routine", "list", "--company", "co1")
    assert empty_result.exit_code == 0
    assert "No routines found." in empty_result.output

    create_result = run_cli(
        runner,
        "routine",
        "create",
        "--company",
        "co1",
        "--project",
        "p1",
        "--name",
        "Reporter",
        "--assignee",
        "a1",
        "--description",
        "Send report",
        "--goal",
        "g1",
        "--priority",
        "high",
        "--status",
        "paused",
        "--concurrency",
        "always_enqueue",
        "--catchup",
        "enqueue_missed_with_cap",
    )
    assert create_result.exit_code == 0
    assert request_json(rsps.calls[2]) == {
        "title": "Reporter",
        "projectId": "p1",
        "assigneeAgentId": "a1",
        "priority": "high",
        "status": "paused",
        "concurrencyPolicy": "always_enqueue",
        "catchUpPolicy": "enqueue_missed_with_cap",
        "description": "Send report",
        "goalId": "g1",
    }

    get_result = run_cli(runner, "routine", "get", "r1")
    assert get_result.exit_code == 0
    assert '"title": "Daily sync"' in get_result.output

    no_fields = run_cli(runner, "routine", "update", "r1")
    assert no_fields.exit_code == 1
    assert "No fields to update." in no_fields.output

    update_result = run_cli(
        runner,
        "routine",
        "update",
        "r1",
        "--name",
        "Updated",
        "--description",
        "Refined",
        "--status",
        "paused",
        "--assignee",
        "a2",
        "--priority",
        "critical",
        "--concurrency",
        "skip_if_active",
    )
    assert update_result.exit_code == 0
    assert request_json(rsps.calls[4]) == {
        "title": "Updated",
        "description": "Refined",
        "status": "paused",
        "assigneeAgentId": "a2",
        "priority": "critical",
        "concurrencyPolicy": "skip_if_active",
    }

    archive_result = run_cli(runner, "routine", "archive", "r1", input="y\n")
    assert archive_result.exit_code == 0
    assert "Archived routine r1" in archive_result.output

    missing_cron = run_cli(runner, "routine", "trigger-add", "r1", "--kind", "schedule")
    assert missing_cron.exit_code == 1
    assert "--cron is required for schedule triggers" in missing_cron.output

    schedule_trigger = run_cli(
        runner,
        "routine",
        "trigger-add",
        "r1",
        "--kind",
        "schedule",
        "--cron",
        "0 9 * * *",
        "--timezone",
        "America/Chicago",
        "--label",
        "Morning",
    )
    assert schedule_trigger.exit_code == 0
    assert "Added schedule trigger" in schedule_trigger.output
    assert request_json(rsps.calls[6]) == {
        "kind": "schedule",
        "label": "Morning",
        "cronExpression": "0 9 * * *",
        "timezone": "America/Chicago",
    }

    webhook_trigger = run_cli(runner, "routine", "trigger-add", "r1", "--kind", "webhook", "--json")
    assert webhook_trigger.exit_code == 0
    assert json.loads(webhook_trigger.output)["id"] == "t2"

    run_result = run_cli(runner, "routine", "run", "r1")
    assert run_result.exit_code == 0
    assert "Triggered routine r1" in run_result.output

    runs_result = run_cli(runner, "routine", "runs", "r1")
    assert runs_result.exit_code == 0
    assert "success" in runs_result.output
    assert "i1" in runs_result.output

    triggers_empty = run_cli(runner, "routine", "triggers", "r1")
    assert triggers_empty.exit_code == 0
    assert "No triggers configured." in triggers_empty.output

    triggers_result = run_cli(runner, "routine", "triggers", "r1")
    assert triggers_result.exit_code == 0
    assert "0 9 * * *" in triggers_result.output
    assert "hmac" in triggers_result.output

@rsps.activate
def test_project_json_paths_and_delete_confirmation(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/projects", json={"projects": [{"id": "p1", "name": "Roadmap"}]})
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/projects", json={"id": "p2", "name": "Platform"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "name": "Roadmap"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "name": "Updated"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": "2026-03-31T00:00:00.000Z"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": "2026-03-31T00:00:00.000Z"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": None})

    list_result = run_cli(runner, "project", "list", "--company", "co1", "--json")
    assert list_result.exit_code == 0
    assert json.loads(list_result.output)[0]["id"] == "p1"

    create_result = run_cli(runner, "project", "create", "--company", "co1", "--name", "Platform", "--json")
    assert create_result.exit_code == 0
    assert json.loads(create_result.output)["id"] == "p2"

    get_result = run_cli(runner, "project", "get", "p1", "--json")
    assert get_result.exit_code == 0
    assert json.loads(get_result.output)["name"] == "Roadmap"

    update_result = run_cli(runner, "project", "update", "p1", "--name", "Updated", "--json")
    assert update_result.exit_code == 0
    assert json.loads(update_result.output)["name"] == "Updated"

    delete_result = run_cli(runner, "project", "delete", "p1", input="y\n")
    assert delete_result.exit_code == 0
    assert "Archived project p1" in delete_result.output

    archive_result = run_cli(runner, "project", "archive", "p1", "--json")
    assert archive_result.exit_code == 0
    assert json.loads(archive_result.output)["id"] == "p1"

    unarchive_result = run_cli(runner, "project", "unarchive", "p1", "--json")
    assert unarchive_result.exit_code == 0
    assert json.loads(unarchive_result.output)["archivedAt"] is None

@rsps.activate
def test_routine_json_paths_and_empty_runs(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/routines", json={"routines": [{"id": "r1", "title": "Daily sync"}]})
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/routines", json={"id": "r2", "title": "Reporter"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1", json={"id": "r1", "title": "Daily sync"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/routines/r1", json={"id": "r1", "title": "Updated"})
    rsps.add(rsps.POST, f"{BASE_URL}/api/routines/r1/run", json={"runId": "run-1"})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1/runs", json={"runs": [{"id": "run-1", "status": "success"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1/runs", json={"runs": []})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1", json={"triggers": [{"id": "t1", "kind": "api"}]})

    list_result = run_cli(runner, "routine", "list", "--company", "co1", "--json")
    assert list_result.exit_code == 0
    assert json.loads(list_result.output)[0]["id"] == "r1"

    create_result = run_cli(
        runner,
        "routine",
        "create",
        "--company",
        "co1",
        "--project",
        "p1",
        "--name",
        "Reporter",
        "--assignee",
        "a1",
        "--json",
    )
    assert create_result.exit_code == 0
    assert json.loads(create_result.output)["id"] == "r2"

    get_result = run_cli(runner, "routine", "get", "r1", "--json")
    assert get_result.exit_code == 0
    assert json.loads(get_result.output)["title"] == "Daily sync"

    update_result = run_cli(runner, "routine", "update", "r1", "--name", "Updated", "--json")
    assert update_result.exit_code == 0
    assert json.loads(update_result.output)["title"] == "Updated"

    run_result = run_cli(runner, "routine", "run", "r1", "--json")
    assert run_result.exit_code == 0
    assert json.loads(run_result.output)["runId"] == "run-1"

    runs_json_result = run_cli(runner, "routine", "runs", "r1", "--json")
    assert runs_json_result.exit_code == 0
    assert json.loads(runs_json_result.output)[0]["id"] == "run-1"

    runs_empty_result = run_cli(runner, "routine", "runs", "r1")
    assert runs_empty_result.exit_code == 0
    assert "No runs found." in runs_empty_result.output

    triggers_result = run_cli(runner, "routine", "triggers", "r1", "--json")
    assert triggers_result.exit_code == 0
    assert json.loads(triggers_result.output)[0]["kind"] == "api"

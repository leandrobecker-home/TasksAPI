"""End-to-end scenarios shared by the in-process and the real-server tests.

They talk to the API only through HTTP, exactly as a client would, and never
look at the database.
"""

import httpx2

API = "/api/v1"


def walk_through_the_main_flow(client: httpx2.Client) -> None:
    """Create a group and tasks, work on them, then clean everything up.

    The steps are the ones of the release R1 acceptance: create group, create
    tasks, list, complete one, delete the tasks, delete the group.
    """
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}

    # 1. Create a group.
    created = client.post(
        f"{API}/task-groups",
        json={"name": "Work", "description": "Everything for the job"},
    )
    assert created.status_code == 201
    group = created.json()
    group_url = created.headers["location"]
    assert group_url == f"{API}/task-groups/{group['id']}"
    assert client.get(group_url).json() == group

    # 2. Create tasks inside it.
    tasks_url = f"{group_url}/tasks"
    report = client.post(
        tasks_url,
        json={
            "title": "Write report",
            "priority": "high",
            "due_date": "2026-12-31",
            "description": "quarterly numbers",
        },
    ).json()
    notes = client.post(
        tasks_url, json={"title": "Review notes", "status": "in_progress"}
    ).json()
    plan = client.post(tasks_url, json={"title": "Plan the week"}).json()
    for task in (report, notes, plan):
        assert task["task_group_id"] == group["id"]

    # 3. List them: newest first, with the right total.
    listing = client.get(tasks_url).json()
    assert listing["total"] == 3
    assert [item["title"] for item in listing["items"]] == [
        "Plan the week",
        "Review notes",
        "Write report",
    ]
    groups = client.get(f"{API}/task-groups").json()
    assert [item["id"] for item in groups["items"]] == [group["id"]]

    # 4. Complete one task: completed_at is filled by the server.
    report_url = f"{API}/tasks/{report['id']}"
    assert report["completed_at"] is None
    completed = client.patch(report_url, json={"status": "completed"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None
    assert client.get(report_url).json()["completed_at"] is not None

    # 5. A group that still has tasks cannot be deleted.
    refused = client.delete(group_url)
    assert refused.status_code == 409
    assert client.get(group_url).status_code == 200

    # 6. Delete the tasks one by one.
    remaining = 3
    for task in (report, notes, plan):
        assert client.delete(f"{API}/tasks/{task['id']}").status_code == 204
        remaining -= 1
        assert client.get(tasks_url).json()["total"] == remaining
        assert client.get(f"{API}/tasks/{task['id']}").status_code == 404
        if remaining:
            assert client.delete(group_url).status_code == 409

    # 7. Now the group can go, and everything about it is gone.
    assert client.delete(group_url).status_code == 204
    assert client.get(group_url).status_code == 404
    assert client.get(tasks_url).status_code == 404
    assert client.get(f"{API}/task-groups").json()["total"] == 0

    # 8. Its name is free again.
    again = client.post(f"{API}/task-groups", json={"name": "work"})
    assert again.status_code == 201

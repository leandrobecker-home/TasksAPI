"""End-to-end test of the main flow (release R1 acceptance)."""

from fastapi.testclient import TestClient

from tests.flows import walk_through_the_main_flow


def test_main_flow_through_the_application(client: TestClient) -> None:
    walk_through_the_main_flow(client)

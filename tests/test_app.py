from unittest.mock import patch

import pytest
from falcon import testing

from protect_with_atakama.app import get_app


@pytest.fixture
def client():
    return testing.TestClient(get_app())


def test_manifest(client):
    response = client.simulate_get("/manifest")
    with open("protect_with_atakama/assets/manifest.json", "r") as f:
        assert response.text == f.read()


def test_logs(client):
    with patch("protect_with_atakama.resources.LOG_FILE", "protect_with_atakama/assets/fnf"):
        # log file not found - returns empty string
        response = client.simulate_get("/logs")
        assert response.text == ""

    with patch("protect_with_atakama.resources.LOG_FILE", "protect_with_atakama/assets/manifest.json"):
        # log file exists (use manifest.json to simulate) - returns file contents
        response = client.simulate_get("/logs")
        with open("protect_with_atakama/assets/manifest.json", "r") as f:
            assert response.text == f.read()

def test_execute(client):
    response = client.simulate_post("/execute")
    # TODO


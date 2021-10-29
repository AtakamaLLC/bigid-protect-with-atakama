from unittest.mock import patch

import pytest

from protect_with_atakama.bigid_api import BigID, Status

valid_api_params = {
    "bigidToken": "token98765",
    "bigidBaseUrl": "http://bigid-base-url",
    "updateResultCallback": "http://bigid-base-url/update/12345",
    "executionId": "execution-id-012",
    "tpaId": "tpa-id-345"
}


@pytest.fixture(name="bigid_api")
def fixture_bigid_api():
    yield BigID(valid_api_params)


def test_bigid_api_init_fails():
    with pytest.raises(KeyError):
        BigID({})

    for (k, _v) in valid_api_params.items():
        bad_params = valid_api_params.copy()
        bad_params.pop(k)
        with pytest.raises(KeyError):
            BigID(bad_params)


def test_bigid_api_headers(bigid_api):
    assert bigid_api._headers["Authorization"] == valid_api_params["bigidToken"]
    assert bigid_api._headers["Content-Type"] == "application/json; charset=UTF-8"


def test_bigid_api_response(bigid_api):
    response = bigid_api.generate_response(Status.IN_PROGRESS, 0.5, "status-message")
    assert response == {
        "executionId": bigid_api._execution_id,
        "statusEnum": "IN_PROGRESS",
        "progress": 0.5,
        "message": "status-message"
    }


def test_bigid_api_requests(bigid_api):
    url = f"{bigid_api._base_url}/hello"
    data = {"fake": "data"}

    with patch("protect_with_atakama.bigid_api.requests") as mock_requests:
        bigid_api.get("/hello")
        mock_requests.get.assert_called_once_with(url, headers=bigid_api._headers)

        bigid_api.post("/hello", data)
        mock_requests.post.assert_called_once_with(url, headers=bigid_api._headers, data=data)

        bigid_api.put("/hello", data)
        mock_requests.put.assert_called_once_with(url, headers=bigid_api._headers, data=data)

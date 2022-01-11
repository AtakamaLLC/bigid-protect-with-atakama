import json
from unittest.mock import patch

import pytest

from protect_with_atakama.bigid_api import BigID, Status
from protect_with_atakama.config import Config, DataSourceSmb

config = json.dumps({
    "version": 1,
    "data_sources": [
        {
            "name": "prod_file_share",
            "kind": "smb",
            "username": "user",
            "password": "pass",
            "label_filter": ".*",
            "path_filter": ""
        },
        {
            "name": "invalid: missing creds",
            "kind": "smb",
            "password": "pass",
        },
        {
            "name": "invalid: not SMB",
            "kind": "onedrive",
        },

    ]
})

valid_api_params = {
    "actionName": "Encrypt",
    "bigidToken": "token98765",
    "bigidBaseUrl": "http://bigid-base-url",
    "updateResultCallback": "http://bigid-base-url/update/12345",
    "executionId": "execution-id-012",
    "tpaId": "tpa-id-345",
    "globalParams": [{"paramName": "Config", "paramValue": config}],
    "actionParams": [{"paramName": "a-n1", "paramValue": "a-v1"}],
}


@pytest.fixture(name="bigid_api")
def fixture_bigid_api():
    yield BigID(valid_api_params)


def test_bigid_api_init_fails():
    with pytest.raises(KeyError):
        BigID({})

    for k in valid_api_params.keys():
        bad_params = valid_api_params.copy()
        bad_params.pop(k)
        with pytest.raises(KeyError):
            BigID(bad_params)


def test_bigid_api_headers(bigid_api):
    assert bigid_api._headers["Authorization"] == valid_api_params["bigidToken"]
    assert bigid_api._headers["Content-Type"] == "application/json; charset=UTF-8"


def test_bigid_api_params(bigid_api):
    assert bigid_api.global_params["Config"] == config
    assert bigid_api.action_params["a-n1"] == "a-v1"
    assert "a-n1" not in bigid_api.global_params.keys()
    assert "Config" not in bigid_api.action_params.keys()
    assert bigid_api.action_name == valid_api_params["actionName"]


def test_bigid_api_progress(bigid_api):
    response = bigid_api._progress_update(Status.IN_PROGRESS, 0.5, "status-message")
    assert response == {
        "executionId": bigid_api._execution_id,
        "statusEnum": "IN_PROGRESS",
        "progress": 0.5,
        "message": "status-message"
    }

    response = bigid_api.get_progress_completed()
    assert response == json.dumps({
        "executionId": bigid_api._execution_id,
        "statusEnum": "COMPLETED",
        "progress": 1.0,
        "message": "Done"
    })

    with patch("protect_with_atakama.bigid_api.requests") as mock_requests:
        url = valid_api_params["updateResultCallback"]
        data = {
            "executionId": valid_api_params["executionId"],
            "statusEnum": Status.IN_PROGRESS.name,
            "progress": 0.75,
            "message": "three-quarters-done"
        }
        bigid_api.send_progress_update(data["progress"], data["message"])
        mock_requests.put.assert_called_once_with(url, headers=bigid_api._headers, data=data)


def test_bigid_api_requests(bigid_api):
    resource = "/hello"
    base_url = valid_api_params["bigidBaseUrl"]
    data = {"fake": "data"}

    with patch("protect_with_atakama.bigid_api.requests") as mock_requests:
        bigid_api.get(resource)
        mock_requests.get.assert_called_once_with(f"{base_url}{resource}", headers=bigid_api._headers, params=None)

        bigid_api.post(resource, data)
        mock_requests.post.assert_called_once_with(f"{base_url}{resource}", headers=bigid_api._headers, data=data)

        bigid_api.put(resource, data)
        mock_requests.put.assert_called_once_with(f"{base_url}{resource}", headers=bigid_api._headers, data=data)


def test_config():
    cfg = Config(config)
    cfg_dict = json.loads(config)
    assert cfg._version == cfg_dict["version"]
    assert len(cfg.data_sources) == 1
    ds = cfg.data_sources[0]
    assert ds.name == cfg_dict["data_sources"][0]["name"]
    assert isinstance(ds, DataSourceSmb)
    api_info = {"smbServer": "the-server", "domain": "the-domain"}
    ds.add_api_info(api_info)
    assert ds.server == api_info["smbServer"]
    assert ds.domain == api_info["domain"]

    for i in range(cfg.max_warnings + 10):
        cfg.warn(f"warning {i}")

    assert len(cfg.warnings) == cfg.max_warnings + 1

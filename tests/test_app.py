import json
import os
from tempfile import NamedTemporaryFile
from unittest.mock import patch, MagicMock

import falcon
import pytest
from falcon import testing

from protect_with_atakama.app import get_app
from protect_with_atakama.bigid_api import BigID


@pytest.fixture(name="client")
def client():
    return testing.TestClient(get_app())


@pytest.fixture(name="smb_mock")
def fixture_smb_mock():
    with patch("protect_with_atakama.smb_api.SMBConnection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn.connect.return_value = True
        mock_conn_cls.return_value = mock_conn
        yield mock_conn


def test_manifest(client):
    with patch("protect_with_atakama.resources.ManifestResource.manifest_path", "fnf"):
        response = client.simulate_get("/manifest")
        assert response.status == falcon.HTTP_500

    response = client.simulate_get("/manifest")
    with open("protect_with_atakama/assets/manifest.json", "r") as f:
        assert response.text == f.read()


def test_logs(client):
    with patch("protect_with_atakama.resources.LOG_FILE", "fnf"):
        # log file not found - returns empty string
        response = client.simulate_get("/logs")
        assert response.status == falcon.HTTP_500

    try:
        with NamedTemporaryFile(delete=False) as log_file:
            log_file.write(b"log this")
        with patch("protect_with_atakama.resources.LOG_FILE", log_file.name):
            # log file exists - returns file contents
            response = client.simulate_get("/logs")
            assert response.text == "log this"
    finally:
        os.unlink(log_file.name)


class MockBigID(BigID):
    def get(self, endpoint: str):
        if endpoint.startswith("ds-connections"):
            return self._get_data_source_info()
        elif endpoint.startswith("data-catalog"):
            return self._get_scan_results()

    def _get_scan_results(self):
        ds_name = self.action_params["data-source-name"]
        if ds_name == "ds-smb-no-pii":
            return self._mock_response({
                "totalRowsCounter": 0
            })
        elif ds_name == "ds-smb-with-pii":
            return self._mock_response({
                "totalRowsCounter": 2,
                "results": [
                    {
                        "attribute": ["label-1", "label-2"],
                        "objectName": "file.txt",
                        "fullObjectName": "share/path/to/file.txt",
                        "containerName": "share"
                    },
                    {
                        "attribute": ["label-1", "label-2"],
                    }
                ]
            })

    def _get_data_source_info(self):
        ds_name = self.action_params["data-source-name"]
        if ds_name == "ds-not-found":
            return self._mock_response({
                "data": {
                    "totalCount": 0
                }
            })
        elif ds_name == "ds-unsupported":
            return self._mock_response({
                "data": {
                    "totalCount": 1,
                    "ds_connections": [
                        {
                            "type": "unsupported"
                        }
                    ]
                }
            })
        elif ds_name == "ds-smb-malformed":
            # missing smbServer
            return self._mock_response({
                "data": {
                    "totalCount": 1,
                    "ds_connections": [
                        {
                            "type": "smb",
                        }
                    ]
                }
            })
        elif ds_name in ("ds-smb-no-pii", "ds-smb-with-pii"):
            return self._mock_response({
                "data": {
                    "totalCount": 1,
                    "ds_connections": [
                        {
                            "type": "smb",
                            "smbServer": "some-server"
                        }
                    ]
                }
            })

    @staticmethod
    def _mock_response(resp):
        ret = MagicMock()
        ret.json = lambda: resp
        return ret


def execute_body(ds_name: str, label_regex: str = ".*", path: str = ""):
    return json.dumps({
        "actionName": "protect-smb",
        "bigidToken": "token98765",
        "bigidBaseUrl": "http://bigid-base-url",
        "updateResultCallback": "http://bigid-base-url/update/12345",
        "executionId": "execution-id-012",
        "tpaId": "tpa-id-345",
        "globalParams": [],
        "actionParams": [
            {"paramName": "username", "paramValue": "user"},
            {"paramName": "password", "paramValue": "secret"},
            {"paramName": "data-source-name", "paramValue": ds_name},
            {"paramName": "label-regex", "paramValue": label_regex},
            {"paramName": "path", "paramValue": path},
        ],
    })


@patch("protect_with_atakama.resources.BigID", MockBigID)
def test_execute_basic(client, smb_mock):
    files_written = []

    def store_file(*args):
        files_written.append(args)

    smb_mock.storeFile = store_file

    # various error conditions - no .ip-labels written
    response = client.simulate_post("/execute", body=execute_body("ds-not-found"))
    assert response.status == falcon.HTTP_400
    assert not files_written

    response = client.simulate_post("/execute", body=execute_body("ds-unsupported"))
    assert response.status == falcon.HTTP_400
    assert not files_written

    response = client.simulate_post("/execute", body=execute_body("ds-smb-malformed"))
    assert response.status == falcon.HTTP_500
    assert not files_written

    # success, but nothing is labeled - no .ip-labels written
    response = client.simulate_post("/execute", body=execute_body("ds-smb-no-pii"))
    assert response.status == falcon.HTTP_200
    assert not files_written

    # success - 1 .ip-labels file
    response = client.simulate_post("/execute", body=execute_body("ds-smb-with-pii"))
    assert response.status == falcon.HTTP_200
    assert len(files_written) == 1
    assert files_written[0][0] == "share"
    assert files_written[0][1] == "/path/to/.ip-labels"


@patch("protect_with_atakama.resources.BigID", MockBigID)
def test_execute_label_filter(client, smb_mock):
    files_written = []

    def store_file(*args):
        files_written.append(args)

    smb_mock.storeFile = store_file

    # label filter excludes label-1, label-2
    response = client.simulate_post("/execute", body=execute_body("ds-smb-with-pii", label_regex="xyz"))
    assert response.status == falcon.HTTP_200
    assert not files_written

    # label filter includes label-2
    response = client.simulate_post("/execute", body=execute_body("ds-smb-with-pii", label_regex="label-2"))
    assert response.status == falcon.HTTP_200
    assert len(files_written) == 1
    assert files_written[0][0] == "share"
    assert files_written[0][1] == "/path/to/.ip-labels"


@patch("protect_with_atakama.resources.BigID", MockBigID)
def test_execute_smb_write_fails(client, smb_mock):

    def store_file(*args):
        raise RuntimeError("can't store")

    smb_mock.storeFile = store_file

    response = client.simulate_post("/execute", body=execute_body("ds-smb-with-pii"))
    assert response.status == falcon.HTTP_200

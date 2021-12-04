import json
import os
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

import falcon
import pytest
from falcon import testing
from smb.smb_structs import OperationFailure

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
        mock_conn.files_written = []
        mock_conn.files_renamed = []
        mock_conn.files_deleted = []

        def store_file(*args):
            mock_conn.files_written.append(args)

        def rename(*args):
            mock_conn.files_renamed.append(args)

        def delete_files(*args):
            mock_conn.files_deleted.append(args)

        def list_path(_share, path, *_args, **_kwargs):
            if "another" in path:
                raise OperationFailure("msg", "sub-msg")
            return ["something"]

        mock_conn.storeFile = store_file
        mock_conn.rename = rename
        mock_conn.deleteFiles = delete_files
        mock_conn.listPath = list_path

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
    with patch("protect_with_atakama.resources.LOG_DIR", "fnf"):
        # log dir not found
        response = client.simulate_get("/logs")
        assert response.status == falcon.HTTP_500

    with TemporaryDirectory() as log_dir:
        with open(os.path.join(log_dir, "log.txt"), "w") as f:
            f.write("log.txt\n")
        with open(os.path.join(log_dir, "log.txt.1"), "w") as f:
            f.write("log.txt.1\n")
        with open(os.path.join(log_dir, "log.txt.2"), "w") as f:
            f.write("log.txt.2\n")

        with patch("protect_with_atakama.resources.LOG_DIR", log_dir):
            # log file exists - returns file contents
            response = client.simulate_get("/logs")
            assert response.text == "log.txt.2\nlog.txt.1\nlog.txt\n"


def test_icon(client):
    response = client.simulate_get("/assets/icon")
    assert response.status == falcon.HTTP_200
    assert response.headers["content-type"] == "image/svg+xml"

    with patch("protect_with_atakama.resources.IconResource.icon_path", "fnf"):
        response = client.simulate_get("/assets/icon")
        assert response.status == falcon.HTTP_500


class MockBigID(BigID):
    def get(self, endpoint: str, params=None):
        if endpoint.startswith("ds-connections"):
            return self._get_data_source_info()
        elif endpoint.startswith("data-catalog"):
            return self._get_scan_results()

    def _get_scan_results(self):
        test_case = self.global_params["test-case"]
        if test_case == "ds-smb-no-pii":
            return self._mock_response({
                "totalRowsCounter": 0
            })
        elif test_case == "ds-smb-with-pii":
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
                        "attribute": ["label-3", "label-4"],
                        "objectName": "file.txt",
                        "fullObjectName": "share/path/to/another/file.txt",
                        "containerName": "share"
                    },
                    {
                        "attribute": ["label-1", "label-2"],
                    }
                ]
            })

    def _get_data_source_info(self):
        test_case = self.global_params["test-case"]
        if test_case == "ds-not-found":
            return self._mock_response({
                "data": {
                    "totalCount": 0
                }
            })
        elif test_case == "ds-unsupported":
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
        elif test_case == "ds-smb-malformed":
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
        elif test_case in ("ds-smb-no-pii", "ds-smb-with-pii"):
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


def encrypt_body(test_case: str, label_regex: str = ".*", ds_name: str = "", path: str = ""):
    config = {
        "version": 1,
        "data_sources": [
            {
                "name": "prod_file_share",
                "kind": "smb",
                "username": "user",
                "password": "pass",
                "label_filter": ".*",
                "path_filter": path,
            },
        ]
    }

    return json.dumps({
        "actionName": "Encrypt",
        "bigidToken": "token98765",
        "bigidBaseUrl": "http://bigid-base-url",
        "updateResultCallback": "http://bigid-base-url/update/12345",
        "executionId": "execution-id-012",
        "tpaId": "tpa-id-345",
        "globalParams": [
            {"paramName": "Config", "paramValue": config},
            {"paramName": "test-case", "paramValue": test_case},
        ],
        "actionParams": [
            {"paramName": "Label Filter", "paramValue": label_regex},
            {"paramName": "Data Source Name", "paramValue": ds_name},
        ],
    })


def verify_body(test_case: str, action="Verify Config"):
    config = {
        "version": 1,
        "data_sources": [
            {
                "name": "prod_file_share",
                "kind": "smb",
                "username": "user",
                "password": "pass",
                "label_filter": ".*",
                "path_filter": "",
            },
        ]
    }

    return json.dumps({
        "actionName": action,
        "bigidToken": "token12345",
        "bigidBaseUrl": "http://bigid-base-url",
        "updateResultCallback": "http://bigid-base-url/update/01289",
        "executionId": "01289",
        "tpaId": "tpa-id-345",
        "globalParams": [
            {"paramName": "Config", "paramValue": config},
            {"paramName": "test-case", "paramValue": test_case},
        ],
        "actionParams": [],
    })


@patch("protect_with_atakama.executor.BigID", MockBigID)
def test_execute_encrypt_basic(client, smb_mock):
    # various error conditions - no .ip-labels written
    response = client.simulate_post("/execute", body=encrypt_body("ds-not-found"))
    assert response.status == falcon.HTTP_400
    assert not smb_mock.files_written

    response = client.simulate_post("/execute", body=encrypt_body("ds-unsupported"))
    assert response.status == falcon.HTTP_400
    assert not smb_mock.files_written

    response = client.simulate_post("/execute", body=encrypt_body("ds-smb-malformed"))
    assert response.status == falcon.HTTP_400
    assert not smb_mock.files_written

    # success, but nothing is labeled - no .ip-labels written
    response = client.simulate_post("/execute", body=encrypt_body("ds-smb-no-pii"))
    assert response.status == falcon.HTTP_200
    assert not smb_mock.files_written

    # success - 2 .ip-labels files
    response = client.simulate_post("/execute", body=encrypt_body("ds-smb-with-pii"))
    assert response.status == falcon.HTTP_200
    assert len(smb_mock.files_written) == 1
    assert smb_mock.files_written[0][0] == "share"
    assert smb_mock.files_renamed[0][0] == "share"
    assert smb_mock.files_renamed[0][1] == smb_mock.files_written[0][1]
    assert smb_mock.files_renamed[0][2] == "path/to/.ip-labels"


@patch("protect_with_atakama.executor.BigID", MockBigID)
def test_execute_encrypt_label_filter(client, smb_mock):
    # label filter excludes label-1, label-2
    response = client.simulate_post("/execute", body=encrypt_body("ds-smb-with-pii", label_regex="xyz"))
    assert response.status == falcon.HTTP_200
    assert not smb_mock.files_written

    # label filter includes label-2
    response = client.simulate_post("/execute", body=encrypt_body("ds-smb-with-pii", label_regex="label-2"))
    assert response.status == falcon.HTTP_200
    assert len(smb_mock.files_written) == 1
    assert smb_mock.files_written[0][0] == "share"
    assert smb_mock.files_renamed[0][0] == "share"
    assert smb_mock.files_renamed[0][1] == smb_mock.files_written[0][1]
    assert smb_mock.files_renamed[0][2] == "path/to/.ip-labels"


@patch("protect_with_atakama.executor.BigID", MockBigID)
def test_execute_encrypt_path_filter(client, smb_mock):
    # path filter excludes share/path/to/file.txt
    response = client.simulate_post("/execute", body=encrypt_body("ds-smb-with-pii", path="share2/path"))
    assert response.status == falcon.HTTP_200
    assert not smb_mock.files_written

    # path filter includes share/path/to/file.txt
    response = client.simulate_post("/execute", body=encrypt_body("ds-smb-with-pii", path="share/path"))
    assert response.status == falcon.HTTP_200
    assert len(smb_mock.files_written) == 1
    assert smb_mock.files_written[0][0] == "share"
    assert smb_mock.files_renamed[0][0] == "share"
    assert smb_mock.files_renamed[0][1] == smb_mock.files_written[0][1]
    assert smb_mock.files_renamed[0][2] == "path/to/.ip-labels"


@patch("protect_with_atakama.executor.BigID", MockBigID)
def test_execute_encrypt_data_source_filter(client, smb_mock):
    # data source filter excludes all data sources
    response = client.simulate_post("/execute", body=encrypt_body("ds-smb-with-pii", ds_name="some_other_share"))
    assert response.status == falcon.HTTP_400
    assert not smb_mock.files_written

    # data source filter includes 1 data source
    response = client.simulate_post("/execute", body=encrypt_body("ds-smb-with-pii", ds_name="prod_file_share"))
    assert response.status == falcon.HTTP_200
    assert len(smb_mock.files_written) == 1
    assert smb_mock.files_written[0][0] == "share"
    assert smb_mock.files_renamed[0][0] == "share"
    assert smb_mock.files_renamed[0][1] == smb_mock.files_written[0][1]
    assert smb_mock.files_renamed[0][2] == "path/to/.ip-labels"


@patch("protect_with_atakama.executor.BigID", MockBigID)
def test_execute_encrypt_write_fails(client, smb_mock):
    store_file_count = 0

    def store_file(*args):
        nonlocal store_file_count
        store_file_count += 1
        if store_file_count % 2 == 1:
            # every other call fails
            raise RuntimeError("can't store")

    smb_mock.storeFile = store_file

    response = client.simulate_post("/execute", body=encrypt_body("ds-smb-with-pii"))
    assert response.status == falcon.HTTP_400


@patch("protect_with_atakama.executor.BigID", MockBigID)
def test_execute_errors(client):
    # unknown action
    response = client.simulate_post("/execute", body=verify_body("ds-name", "unknown-action"))
    assert response.status == falcon.HTTP_400

    # bad input
    response = client.simulate_post("/execute", body="")
    assert response.status == falcon.HTTP_500


@patch("protect_with_atakama.executor.BigID", MockBigID)
def test_execute_verify_basic(client, smb_mock):
    response = client.simulate_post("/execute", body=verify_body("ds-smb-with-pii"))
    assert response.status == falcon.HTTP_200
    assert len(smb_mock.files_written) == 1
    assert smb_mock.files_written[0][0] == "share-name"
    assert len(smb_mock.files_written[0][1]) == 32
    assert len(smb_mock.files_deleted) == 1
    assert smb_mock.files_deleted[0][0] == "share-name"
    assert smb_mock.files_deleted[0][1] == smb_mock.files_written[0][1]

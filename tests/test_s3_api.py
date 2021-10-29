from unittest.mock import patch

import pytest

from protect_with_atakama.s3_api import S3

valid_api_params = {
    "base_url": "https://s3.us-east-1.amazonaws.com/bigid-test-basic-auth",
    "username": "test",
    "password": "heebeejeebee"
}


@pytest.fixture(name="s3_api")
def fixture_s3_api():
    yield S3(valid_api_params)


def test_s3_api_init_fails():
    with pytest.raises(KeyError):
        S3({})

    for k in valid_api_params.keys():
        bad_params = valid_api_params.copy()
        bad_params.pop(k)
        with pytest.raises(KeyError):
            S3(bad_params)


def test_s3_api_headers(s3_api):
    assert s3_api._headers["UserAgent"] == valid_api_params["username"]
    assert s3_api._headers["Referer"] == valid_api_params["password"]


def test_s3_api_requests(s3_api):
    base_url = valid_api_params["base_url"]
    file = "/path/to/file.txt"
    data = "hello"

    with patch("protect_with_atakama.s3_api.requests") as mock_requests:
        s3_api.get(file)
        mock_requests.get.assert_called_once_with(f"{base_url}{file}", headers=s3_api._headers)

        s3_api.put(file, data)
        mock_requests.put.assert_called_once_with(f"{base_url}{file}", headers=s3_api._headers, data=data)

from socket import gethostname
from unittest.mock import patch, MagicMock

import pytest

from protect_with_atakama.smb_api import Smb


@pytest.fixture(name="smb_api")
def fixture_smb_api():
    with patch("protect_with_atakama.smb_api.SMBConnection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn.connect.return_value = True
        mock_conn_cls.return_value = mock_conn
        yield Smb("user", "password", "1.2.3.4")


@pytest.fixture(name="smb_api_connect_fails")
def fixture_smb_api_connect_fails():
    with patch("protect_with_atakama.smb_api.SMBConnection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn.connect.return_value = False
        mock_conn_cls.return_value = mock_conn
        yield Smb("user", "password", "1.2.3.4")


@pytest.fixture(name="smb_api_store_fails")
def fixture_smb_api_store_fails():
    def error(*_args, **_kwargs):
        raise RuntimeError("failed to store file")

    with patch("protect_with_atakama.smb_api.SMBConnection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn.connect.return_value = True
        mock_conn.storeFile = error
        mock_conn_cls.return_value = mock_conn
        yield Smb("user", "password", "1.2.3.4")


def test_smb_api_connect(smb_api):
    # not connected yet
    assert smb_api._conn is None

    with smb_api:
        # successful connection
        assert smb_api._conn is not None
        assert smb_api._conn.called_once_with(
            smb_api._user, smb_api._password, gethostname(), smb_api._address, domain="", is_direct_tcp=True
        )
        assert smb_api._conn.connect.called_once_with(smb_api._address, 445)
        conn = smb_api._conn

    # disconnected on exit
    assert conn.close.called_once()
    assert smb_api._conn is None


def test_smb_api_cannot_connect(smb_api_connect_fails):
    # not connected yet
    assert smb_api_connect_fails._conn is None

    with pytest.raises(RuntimeError):
        with smb_api_connect_fails:
            # failed connection raises
            pass

    # still disconnected
    assert smb_api_connect_fails._conn is None


def test_smb_api_file_ops(smb_api):
    # not connected yet
    assert smb_api._conn is None
    with pytest.raises(RuntimeError):
        _ = smb_api.connection

    with smb_api:
        # successful connection
        smb_api.write_file("share", "/path/to/file", b"bytes")
        assert smb_api.connection.storeFile.called_once_with("share", "/path/to/file", b"bytes")

        smb_api.delete_file("share", "/path/to/file")
        assert smb_api.connection.deleteFiles.called_once_with("share", "/path/to/file")

        smb_api.rename("share", "/path/to/file", "/new/path/to/file")
        assert smb_api.connection.rename.called_once_with("share", "/path/to/file", "/new/path/to/file")

    # disconnected on exit
    assert smb_api._conn is None

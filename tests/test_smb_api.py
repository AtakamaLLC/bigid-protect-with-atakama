from dataclasses import dataclass
from unittest.mock import patch, MagicMock

import pytest
from smb.smb_structs import OperationFailure

from protect_with_atakama.smb_api import Smb


@pytest.fixture(name="smb_api")
def fixture_smb_api():
    with patch("protect_with_atakama.smb_api.SMBConnection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn.connect.return_value = True

        def list_path(_share, path):
            if path == "not-found":
                raise OperationFailure("msg", "sub-msg")
            return ["something"]

        mock_conn.listPath = list_path

        @dataclass
        class MockShare:
            name: str
            isSpecial: bool

        mock_conn.listShares = lambda: [MockShare("s1", False), MockShare("IPC$", True)]

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
        smb_api._conn.connect.assert_called_once_with(smb_api._address, port=445)
        conn = smb_api._conn

    # disconnected on exit
    conn.close.assert_called_once()
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
        smb_api.connection.storeFile.assert_called_once()
        assert smb_api.connection.storeFile.mock_calls[0][1][0] == "share"
        assert smb_api.connection.storeFile.mock_calls[0][1][1] == "/path/to/file"
        smb_api.connection.reset_mock()

        smb_api.delete_file("share", "/path/to/file")
        smb_api.connection.deleteFiles.assert_called_once_with("share", "/path/to/file")
        smb_api.connection.reset_mock()

        smb_api.rename("share", "/path/to/file", "/new/path/to/file")
        smb_api.connection.rename.assert_called_once_with("share", "/path/to/file", "/new/path/to/file")
        smb_api.connection.reset_mock()

        smb_api.atomic_write("share", "/path/to", "file", b"data")
        smb_api.connection.storeFile.assert_called_once()
        assert smb_api.connection.storeFile.mock_calls[0][1][0] == "share"
        assert len(smb_api.connection.deleteFiles.mock_calls) == 2
        assert smb_api.connection.deleteFiles.mock_calls[0][1][0] == "share"
        assert smb_api.connection.deleteFiles.mock_calls[0][1][1] == "/path/to/file"
        assert smb_api.connection.deleteFiles.mock_calls[1][1][0] == "share"
        smb_api.connection.rename.assert_called_once()
        assert smb_api.connection.rename.mock_calls[0][1][0] == "share"
        assert smb_api.connection.rename.mock_calls[0][1][2] == "/path/to/file"

        assert smb_api.is_dir("share", "/path/to/file")
        assert not smb_api.is_dir("share", "not-found")

        shares = smb_api.list_shares()
        assert len(shares) == 1
        assert shares[0] == "s1"

    # disconnected on exit
    assert smb_api._conn is None

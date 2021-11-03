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


@pytest.fixture(name="smb_api_bad")
def fixture_smb_api_bad():
    with patch("protect_with_atakama.smb_api.SMBConnection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn.connect.return_value = False
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


def test_smb_api_cannot_connect(smb_api_bad):
    # not connected yet
    assert smb_api_bad._conn is None

    with pytest.raises(RuntimeError):
        with smb_api_bad:
            # failed connection raises
            pass

    # still disconnected
    assert smb_api_bad._conn is None


def test_smb_api_write_file(smb_api):
    # not connected yet
    assert smb_api._conn is None
    with pytest.raises(RuntimeError):
        _ = smb_api.connection

    with smb_api:
        # successful connection
        smb_api.write_file("share", "/path/to/file", b"bytes")
        assert smb_api.connection.storeFile.called_once()
        assert smb_api.connection.storeFile.mock_calls[0][1][0] == "share"
        assert smb_api.connection.storeFile.mock_calls[0][1][1] == "/path/to/file"

    # disconnected on exit
    assert smb_api._conn is None

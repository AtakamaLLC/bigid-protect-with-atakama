import logging
import os
from socket import gethostname
from tempfile import NamedTemporaryFile

from smb.SMBConnection import SMBConnection
from smb.smb_structs import OperationFailure

log = logging.getLogger(__name__)


class Smb:
    """
    Wrapper for PySMB `SMBConnection` class
    """

    def __init__(self, user: str, password: str, address: str, domain: str = ""):
        self._user = user
        self._password = password
        self._address = address
        self._domain = domain
        self._conn = None

    def __enter__(self) -> "Smb":
        if self._conn is None:
            self._conn = SMBConnection(
                self._user,
                self._password,
                gethostname(),
                self._address,
                domain=self._domain,
                is_direct_tcp=True,
            )
            if not self._conn.connect(self._address, port=445):
                self._conn = None
                raise RuntimeError("Failed to connect")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> SMBConnection:
        if not self._conn:
            raise RuntimeError("not connected")
        return self._conn

    def write_file(self, share: str, path: str, data: bytes) -> int:
        with NamedTemporaryFile() as temp_file:
            temp_file.write(data)
            temp_file.seek(0)
            return self.connection.storeFile(share, path, temp_file)

    def delete_file(self, share: str, path: str) -> None:
        self.connection.deleteFiles(share, path)

    def rename(self, share: str, old_path: str, new_path: str) -> None:
        self.connection.rename(share, old_path, new_path)

    def atomic_write(self, share: str, parent: str, file: str, data: bytes):
        temp_path = f"{parent}/{os.urandom(16).hex()}"
        target_path = f"{parent}/{file}"
        log.debug("atomic_write %s", target_path)
        try:
            self.write_file(share, temp_path, data)
            self.delete_file(share, target_path)
            self.rename(share, temp_path, target_path)
        finally:
            self.delete_file(share, temp_path)

    def is_dir(self, share: str, path: str) -> bool:
        assert self.connection
        try:
            # raises if path not found
            self.connection.listPath(share, path)
            return True
        except OperationFailure:
            return False

    def list_shares(self):
        assert self.connection
        return [share.name for share in self.connection.listShares() if not share.isSpecial]

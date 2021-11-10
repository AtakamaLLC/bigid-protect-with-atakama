import logging
from socket import gethostname
from tempfile import NamedTemporaryFile

from smb.SMBConnection import SMBConnection

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

    def rename(self, share: str, old_path: str, new_path: str):
        self.connection.rename(share, old_path, new_path)

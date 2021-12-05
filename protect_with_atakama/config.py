import logging
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class DataSourceBase:
    name: str
    kind: str
    label_filter: str
    path_filter: str

    def add_api_info(self, info: dict) -> None:
        pass  # pragma: no cover


@dataclass
class DataSourceSmb(DataSourceBase):
    username: str
    password: str
    server: str = ""
    shares: str = ""
    domain: str = ""

    def add_api_info(self, info: dict) -> None:
        self.server = info["smbServer"]
        self.shares = info.get("sharedResource", "")
        self.domain = info.get("domain", "")

    def __repr__(self):
        kws = [f"{key}={value!r}" for key, value in self.__dict__.items() if key not in ("username", "password")]
        return "{}({})".format(type(self).__name__, ", ".join(kws))


class Config:
    """
    {
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
            ...
        ]
    }

    """

    def __init__(self, cfg: dict):
        self._warnings: List[str] = []
        self._version: int = cfg["version"]
        self._data_sources: List[DataSourceBase] = []
        self._load_data_sources(cfg)

    @property
    def data_sources(self) -> List[DataSourceBase]:
        return self._data_sources

    @property
    def warnings(self) -> List[str]:
        return self._warnings

    def warn(self, warning: str) -> None:
        self._warnings.append(warning)
        log.warning(warning)

    def _load_data_sources(self, cfg: dict) -> None:
        for ds in cfg["data_sources"]:
            try:
                kind = ds["kind"]
                if kind == "smb":
                    self._data_sources.append(
                        DataSourceSmb(
                            name=ds["name"],
                            kind=kind,
                            label_filter=ds.get("label_filter", ".*"),
                            path_filter=ds.get("path_filter", ""),
                            username=ds["username"],
                            password=ds["password"]
                        )
                    )
                else:
                    self.warn(f"unsupported data source: {self._scrub_creds(ds)}")

            except Exception as e:
                self.warn(f"failed to parse data source: {self._scrub_creds(ds)} ex: {repr(e)}")

    @staticmethod
    def _scrub_creds(ds: dict) -> None:
        for k in ["username", "password"]:
            if k in ds:
                ds[k] = "********"

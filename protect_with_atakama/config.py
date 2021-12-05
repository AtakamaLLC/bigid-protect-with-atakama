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
    # TODO: repr
    username: str
    password: str
    server: str = ""
    domain: str = ""

    def add_api_info(self, info: dict) -> None:
        self.server = info["smbServer"]
        self.domain = info.get("domain", "")


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
            kind = ds["kind"]
            if kind == "smb":
                self._add_smb_data_source(ds)
            else:
                # TODO: track errors
                log.error("unsupported data source: %s", self._scrub_creds(ds))

    def _add_smb_data_source(self, ds: dict) -> None:
        try:
            self._data_sources.append(
                DataSourceSmb(
                    name=ds["name"],
                    kind="smb",
                    label_filter=ds.get("label_filter", ".*"),
                    path_filter=ds.get("path_filter", ""),
                    username=ds["username"],
                    password=ds["password"]
                )
            )
        except Exception as e:
            # TODO: track errors
            logging.exception("failed to parse data source: %s", self._scrub_creds(ds))

    @staticmethod
    def _scrub_creds(ds: dict) -> None:
        for k in ["username", "password"]:
            if k in ds:
                ds[k] = "********"

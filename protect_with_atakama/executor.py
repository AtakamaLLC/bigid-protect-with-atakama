import json
import logging
import os
import pathlib
import re
from collections import defaultdict
from typing import Dict, Any, Generator

import falcon

from protect_with_atakama.bigid_api import BigID
from protect_with_atakama.config import DataSourceSmb, DataSourceBase, Config
from protect_with_atakama.smb_api import Smb
from protect_with_atakama.utils import ExecutionError

log = logging.getLogger(__name__)


class Executor:
    """
    Encapsulates action execution
    """

    def __init__(self, params: dict):
        self._api: BigID = BigID(params)
        self._config: Config = Config(self._api.global_params["Config"])

    def execute(self) -> str:
        """
        Execute the action specified by input params
        """
        if self._api.action_name == "Encrypt":
            self._write_ip_labels()
        elif self._api.action_name == "Verify Config":
            self._verify_config()
        else:
            self._config.warn(f"unrecognized action name: {self._api.action_name}")

        if self._config.warnings:
            text = "\n".join(self._config.warnings)
            raise ExecutionError(falcon.HTTP_400, text)

        return self._api.get_progress_completed()

    def _data_sources(self) -> Generator[DataSourceBase, None, None]:
        name_filter = self._api.action_params.get("Data Source Name", "")
        label_filter = self._api.action_params.get("Label Filter", "")
        data_source_count = 0

        for ds in self._config.data_sources:
            try:
                if name_filter and name_filter != ds.name:
                    log.info(
                        "filtered out data source: %s (filter=%s)", ds.name, name_filter
                    )
                    continue

                if label_filter:
                    # action param overrides global param
                    ds.label_filter = label_filter

                query = [{"field": "name", "value": ds.name, "operator": "equal"}]
                params = {"filter": json.dumps(query)}
                ds_data = self._api.get("ds-connections", params=params).json()["data"]
                ds_count = ds_data["totalCount"]
                if ds_count != 1:
                    self._config.warn(
                        f"unexpected count ({ds_count}) for data source: {ds.name}"
                    )
                    continue

                ds_info = ds_data["ds_connections"][0]
                ds_type = ds_info["type"]
                if ds_type != ds.kind:
                    self._config.warn(
                        f"unexpected type ({ds_type}) for data source: {ds.name}"
                    )
                    continue

                ds.add_api_info(ds_info)
                data_source_count += 1
                yield ds

            except Exception as e:
                self._config.warn(f"error processing data source: {ds} ex: {repr(e)}")

        if data_source_count == 0:
            self._config.warn("no data sources enumerated")

    def _verify_config(self):
        for ds in self._data_sources():
            try:
                if isinstance(ds, DataSourceSmb):
                    self._verify_smb(ds)
            except Exception as e:
                self._config.warn(f"error verifying data source: {ds} ex: {repr(e)}")

    def _verify_smb(self, ds: DataSourceSmb):
        with Smb(ds.username, ds.password, ds.server, ds.domain) as smb:
            if len(ds.shares) == 1 and ds.shares[0] == "":
                ds.shares = smb.list_shares()

            for share in ds.shares:
                try:
                    filename = os.urandom(16).hex()
                    smb.write_file(share, filename, b"verify-smb-connection")
                    smb.delete_file(share, filename)
                    log.info("verified share %s for data source %s", share, ds)
                except Exception as ex:
                    self._config.warn(
                        f"failed to verify share {share} for data source {ds} - ex: {repr(ex)}"
                    )

    def _get_ip_labels(self, ds: DataSourceBase) -> Dict[tuple, Any]:
        ip_labels: Dict[tuple, Any] = defaultdict(lambda: {"files": {}})
        ds_scan = self._api.get(f"data-catalog?filter=system={ds.name}").json()
        log.info("scan result rows: %s", ds_scan["totalRowsCounter"])

        label_filter = re.compile(ds.label_filter, re.I)
        path_filter = ds.path_filter.lstrip("/")
        log.debug("filters: label=%s path=%s", label_filter.pattern, path_filter)
        ds_scan_results = ds_scan.get("results", [])
        log.debug("scan result count: %s", len(ds_scan_results))

        for f in ds_scan_results:
            try:
                log.debug("processing: %s", f)
                labels = f.get("attribute")
                filtered_labels = [l for l in labels if label_filter.match(l)]
                if not filtered_labels:
                    log.debug("filtered out file, labels=%s", labels)
                    continue

                full = pathlib.Path(f["fullObjectName"])
                if path_filter:
                    try:
                        full.relative_to(path_filter)
                    except ValueError:
                        log.debug("filtered out file, path=%s", full)
                        continue

                share = f["containerName"]
                parent = (share, str(full.relative_to(share).parent).replace("\\", "/"))
                name = f["objectName"]
                ip_labels[parent]["files"][name] = {"labels": filtered_labels}
            except:
                log.exception("error processing scan result row: %s", f)

        log.debug("ip_labels: %s", ip_labels)
        return ip_labels

    def _write_ip_labels(self) -> None:
        for ds in self._data_sources():
            try:
                ip_labels = self._get_ip_labels(ds)
                if not ip_labels:
                    log.warning("no ip-labels to write for data source: %s", ds.name)
                    continue

                ds: DataSourceSmb
                with Smb(ds.username, ds.password, ds.server, ds.domain) as smb:
                    for (share, path), files in ip_labels.items():
                        try:
                            if not smb.is_dir(share, path):
                                log.warning(
                                    "path not found, skipping - ds=%s share=%s path=%s",
                                    ds.name,
                                    share,
                                    path,
                                )
                                continue

                            smb.atomic_write(
                                share,
                                path,
                                ".ip-labels",
                                json.dumps(files, indent=4).encode(),
                            )
                        except Exception as e:
                            self._config.warn(
                                f"failed to write .ip-labels: ds={ds} share={share} path={path} ex={e}"
                            )
            except Exception as e:
                self._config.warn(
                    f"failed to write .ip-labels for data source: ds={ds} ex={e}"
                )

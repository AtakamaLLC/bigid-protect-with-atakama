import json
import logging
import os
import pathlib
import re
from collections import defaultdict
from typing import Dict, Any

import falcon

from protect_with_atakama.bigid_api import BigID
from protect_with_atakama.config import DataSourceSmb, DataSourceBase
from protect_with_atakama.smb_api import Smb
from protect_with_atakama.utils import ExecutionError

log = logging.getLogger(__name__)


class Executor:

    def __init__(self, params: dict):
        self._api = BigID(params)

    def execute(self) -> str:
        if self._api.action_name == "Encrypt":
            self._write_ip_labels()
        elif self._api.action_name == "Verify Config":
            self._verify_config()
        else:
            raise ExecutionError(
                falcon.HTTP_400,
                f"unrecognized action name: {self._api.action_name}",
            )

        return self._api.get_progress_completed()

    def _verify_config(self):
        for ds in self._api.data_sources():
            ds: DataSourceSmb

            # TODO: handle other kinds
            # TODO: try/except/record error/continue
            if ds.kind == "smb":
                # TODO: need param? get from api? get from list-shares?
                share = "share-name" #api.action_params["share"]
                with Smb(ds.username, ds.password, ds.server, ds.domain) as smb:
                    filename = os.urandom(16).hex()
                    smb.write_file(share, filename, b"verify-smb-connection")
                    smb.delete_file(share, filename)

    def _get_ip_labels(self, ds: DataSourceBase) -> Dict[tuple, Any]:
        ip_labels: Dict[tuple, Any] = defaultdict(lambda: {"files": {}})
        ds_scan = self._api.get(f"data-catalog?filter=system={ds.name}").json()
        log.info("scan result rows: %s", ds_scan["totalRowsCounter"])

        label_filter = re.compile(ds.label_filter, re.I)
        path_filter = ds.path_filter.lstrip("/")
        log.debug("filters: label=%s path=%s", label_filter.pattern, path_filter)
        ds_scan_results = ds_scan.get("results", [])
        for f in ds_scan_results:
            try:
                log.debug("processing: %s", f)
                labels = f.get("attribute")
                filtered_labels = [l for l in labels if label_filter.match(l)]
                if not filtered_labels:
                    log.debug("filtered out file, labels=%s", labels)
                    continue

                full = pathlib.Path(f["fullObjectName"])
                try:
                    if path_filter:
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
        error_count = 0
        ip_labels_count = 0
        data_source_count = 0

        for ds in self._api.data_sources():
            data_source_count += 1

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
                                "path not found, skipping - ds=%s share=%s path=%s", ds.name, share, path
                            )
                            continue

                        smb.atomic_write(
                            share, path, ".ip-labels", json.dumps(files, indent=4).encode()
                        )
                        ip_labels_count += 1
                    except:
                        error_count += 1
                        log.exception(
                            "failed to write .ip-labels: ds=%s share=%s path=%s", ds.name, share, path
                        )

        if not data_source_count:
            raise ExecutionError(falcon.HTTP_400, "No data sources processed")

        if error_count:
            raise ExecutionError(
                falcon.HTTP_400,
                f"Failed to write {error_count} of {ip_labels_count} files",
            )

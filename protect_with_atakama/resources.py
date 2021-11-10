import json
import logging
import os
import pathlib
import re
from collections import defaultdict
from typing import Dict, Any

import falcon

from protect_with_atakama.bigid_api import BigID
from protect_with_atakama.smb_api import Smb
from protect_with_atakama.utils import (
    LOG_DIR,
    DataSourceError,
    ExecutionError,
)

log = logging.getLogger(__name__)


class ManifestResource:
    """
    Returns the app manifest
    """

    manifest_path: str = "protect_with_atakama/assets/manifest.json"

    def __init__(self):
        self._manifest: str = ""

    @property
    def manifest(self):
        if not self._manifest:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self._manifest = f.read()
        return self._manifest

    def on_get(self, _req: falcon.Request, resp: falcon.Response):
        """
        Handle GET request
        """
        log.debug("on_get: manifest")
        try:
            resp.text = self.manifest
            log.debug("return manifest: len=%s", len(resp.text))
        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.text = repr(e)
            log.exception("failed to get manifest - %s", repr(e))


class LogsResource:
    """
    Returns the app's logs
    """

    def on_get(
        self, _req: falcon.Request, resp: falcon.Response
    ):  # pylint: disable=no-self-use
        """
        Handle GET request
        """
        log.debug("on_get: logs")
        try:
            all_logs = ""
            log_files = os.listdir(LOG_DIR)
            log_files.sort(reverse=True)
            for f in log_files:
                with open(os.path.join(LOG_DIR, f), "r", encoding="utf-8") as log_file:
                    all_logs += log_file.read()
            resp.text = all_logs
            log.debug("return logs: len=%s", len(resp.text))
        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.text = repr(e)
            log.exception("failed to get logs - %s", repr(e))


class ExecuteResource:
    """
    Executes an action defined in the manifest
    """

    def on_post(self, req: falcon.Request, resp: falcon.Response):
        """
        Handle POST request
        """
        try:
            log.debug("on_post: execute")
            bigid_api = BigID(req.get_media())

            if bigid_api.action_name == "protect-smb":
                self._write_ip_labels(bigid_api)
            elif bigid_api.action_name == "verify-smb-connection":
                self._verify_smb_connection(bigid_api)
            else:
                raise ExecutionError(
                    falcon.HTTP_400,
                    f"unrecognized action name: {bigid_api.action_name}",
                )

            resp.text = bigid_api.get_progress_completed()

        except ExecutionError as e:
            resp.status = e.status
            resp.text = e.message
            log.exception("failed to execute - %s", repr(e))

        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.text = repr(e)
            log.exception("failed to execute - %s", repr(e))

    def _verify_smb_connection(self, api: BigID):
        ds_info = self._get_data_source_info(api)
        server = ds_info["smbServer"]
        domain = ds_info.get("domain", "")
        username = api.action_params["username"]
        password = api.action_params["password"]
        share = api.action_params["share"]
        with Smb(username, password, server, domain) as smb:
            filename = os.urandom(16).hex()
            smb.write_file(share, filename, b"verify-smb-connection")
            smb.delete_file(share, filename)

    @staticmethod
    def _get_data_source_info(api: BigID) -> Dict[str, Any]:
        ds_name = api.action_params["data-source-name"]
        query = [{"field": "name", "value": ds_name, "operator": "equal"}]
        params = {"filter": json.dumps(query)}
        ds_data = api.get("ds-connections", params=params).json()["data"]
        ds_count = ds_data["totalCount"]
        if ds_count != 1:
            raise DataSourceError(
                falcon.HTTP_400, f"unexpected data source count: {ds_count}"
            )

        ds_info = ds_data["ds_connections"][0]
        ds_type = ds_info["type"]
        if ds_type != "smb":
            raise DataSourceError(
                falcon.HTTP_400, f"unexpected data source type: {ds_type}"
            )

        return ds_info

    @staticmethod
    def _get_ip_labels(api: BigID) -> Dict[tuple, Any]:
        ip_labels: Dict[tuple, Any] = defaultdict(lambda: {"files": {}})
        ds_name = api.action_params["data-source-name"]
        ds_scan = api.get(f"data-catalog?filter=system={ds_name}").json()
        log.info("scan result rows: %s", ds_scan["totalRowsCounter"])

        label_regex = re.compile(api.action_params["label-regex"], re.I)
        path_filter = api.action_params["path"]
        log.debug("filters: label-regex=%s path=%s", label_regex.pattern, path_filter)
        ds_scan_results = ds_scan.get("results", [])
        for f in ds_scan_results:
            try:
                log.debug("processing: %s", f)
                labels = f.get("attribute")
                filtered_labels = [l for l in labels if label_regex.match(l)]
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

    def _write_ip_labels(self, api: BigID) -> None:
        ds_info = self._get_data_source_info(api)
        ip_labels = self._get_ip_labels(api)
        if not ip_labels:
            log.warning("no ip-labels to write")
            return

        error_count = 0
        server = ds_info["smbServer"]
        domain = ds_info.get("domain", "")
        username = api.action_params["username"]
        password = api.action_params["password"]
        with Smb(username, password, server, domain) as smb:
            for (share, path), files in ip_labels.items():
                try:
                    # TODO: check for existence of file/folder?
                    ip_labels_path = f"{path}/.ip-labels"
                    log.debug("writing .ip-labels: %s", ip_labels_path)
                    smb.write_file(
                        share, ip_labels_path, json.dumps(files, indent=4).encode()
                    )
                except:
                    error_count += 1
                    log.exception(
                        "failed to write .ip-labels: share=%s path=%s", share, path
                    )

        if error_count:
            raise ExecutionError(falcon.HTTP_400, f"Failed to write {error_count} of {len(ip_labels)} files")
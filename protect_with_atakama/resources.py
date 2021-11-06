import json
import logging
import re
from collections import defaultdict
from typing import Dict, Any

import falcon

from protect_with_atakama.bigid_api import BigID
from protect_with_atakama.smb_api import Smb
from protect_with_atakama.utils import (
    LOG_FILE,
    DataSourceError,
    ProtectWithAtakamaError,
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
            log.exception("failed to get manifest")


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
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                resp.text = f.read()
                log.debug("return logs: len=%s", len(resp.text))
        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.text = repr(e)
            log.exception("failed to get logs")


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
            self._write_ip_labels(bigid_api)
            resp.text = bigid_api.get_progress_completed()
        except ProtectWithAtakamaError as e:
            resp.status = e.status
            resp.text = e.message
            log.exception("failed to execute (400)")
        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.text = repr(e)
            log.exception("failed to execute (500)")

    @staticmethod
    def _get_data_source_info(api: BigID) -> Dict[str, Any]:
        ds_name = api.action_params["data-source-name"]
        query = f'[{{ "field": "name", "value": "{ds_name}", "operator": "equal" }}]'
        ds_data = api.get(f"ds-connections?filter={query}").json()["data"]
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

        label_regex = api.action_params["label-regex"]
        # _path = api.action_params["path"]
        ds_scan_results = ds_scan.get("results", [])
        for f in ds_scan_results:
            try:
                log.debug("processing: %s", f)
                labels = f.get("attribute")
                filtered_labels = [l for l in labels if re.match(label_regex, l, re.I)]
                if filtered_labels:
                    # TODO: path filter
                    name = f["objectName"]
                    full = f["fullObjectName"]
                    share = f["containerName"]
                    parent_path = f"{full[len(share):-len(name) - 1]}".replace(
                        "\\", "/"
                    )
                    parent = (share, parent_path)
                    ip_labels[parent]["files"][name] = {"labels": labels}
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
                    log.exception(
                        "failed to write .ip-labels: share=%s path=%s", share, path
                    )

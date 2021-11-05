import json
import logging
from collections import defaultdict
from typing import Dict, Any

import falcon

from protect_with_atakama.bigid_api import BigID
from protect_with_atakama.smb_api import Smb
from protect_with_atakama.utils import LOG_FILE, DataSourceError, ScanResultsError, ProtectWithAtakamaError

log = logging.getLogger(__name__)


class ManifestResource:
    manifest_path: str = "protect_with_atakama/assets/manifest.json"

    def __init__(self):
        self._manifest: str = ""

    @property
    def manifest(self):
        if not self._manifest:
            with open(self.manifest_path, "r") as f:
                self._manifest = f.read()
        return self._manifest

    def on_get(self, _req: falcon.Request, resp: falcon.Response):
        log.debug("on_get: manifest")
        try:
            resp.text = self.manifest
            log.debug(f"return manifest: len={len(resp.text)}")
        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.text = repr(e)
            log.exception("failed to get manifest")


class LogsResource:
    def on_get(self, _req: falcon.Request, resp: falcon.Response):
        log.debug("on_get: logs")
        try:
            with open(LOG_FILE, "r") as f:
                resp.text = f.read()
                log.debug(f"return logs: len={len(resp.text)}")
        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.text = repr(e)
            log.exception("failed to get logs")


class ExecuteResource:

    def _get_data_source_info(self, api: BigID) -> Dict[str, Any]:
        ds_name = api.action_params["data-source-name"]
        query = '[{ "field": "name", "value": "%s", "operator": "equal" }]' % ds_name
        ds_data = api.get(f"ds-connections?filter={query}").json()["data"]
        ds_count = ds_data["totalCount"]
        if ds_count != 1:
            raise DataSourceError(falcon.HTTP_400, f"unexpected data source count: {ds_count}")

        ds_info = ds_data["ds_connections"][0]
        ds_type = ds_info["type"]
        if ds_type != "smb":
            raise DataSourceError(falcon.HTTP_400, f"unexpected data source type: {ds_type}")

        return ds_info

    def _get_ip_labels(self, api: BigID) -> Dict[tuple, Any]:
        ip_labels: Dict[tuple, Any] = defaultdict(lambda: {"files": {}})
        ds_name = api.action_params["data-source-name"]
        ds_scan = api.get(f"data-catalog?filter=system={ds_name}").json()
        log.info(f"scan result rows: {ds_scan['totalRowsCounter']}")

        _label_regex = api.action_params["label-regex"]
        _path = api.action_params["path"]
        ds_scan_results = ds_scan.get("results", [])
        for f in ds_scan_results:
            try:
                log.debug(f"processing: {f}")
                labels = f.get("attribute")
                if labels:
                    # TODO: label filter
                    # TODO: path filter
                    name = f["objectName"]
                    full = f["fullObjectName"]
                    share = f["containerName"]
                    parent_path = f"{full[len(share):-len(name) - 1]}".replace("\\", "/")
                    parent = (share, parent_path)
                    ip_labels[parent]["files"][name] = {"labels": labels}
            except:
                log.exception(f"error processing scan result row: {f}")

        log.debug(f"ip_labels: {ip_labels}")
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
                    log.debug(f"writing .ip-labels: {ip_labels_path}")
                    smb.write_file(share, ip_labels_path, json.dumps(files, indent=4).encode())
                    print("here")
                except:
                    log.exception(f"failed to write .ip-labels: share={share} path={path}")

    def on_post(self, req: falcon.Request, resp: falcon.Response):
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

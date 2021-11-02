import json
import logging
from collections import defaultdict
from typing import Dict, Any

import falcon

from protect_with_atakama.bigid_api import BigID
from protect_with_atakama.smb_api import Smb
from protect_with_atakama.utils import LOG_FILE

log = logging.getLogger(__name__)


class ManifestResource:
    def __init__(self):
        self._manifest: str = ""

    @property
    def manifest(self):
        if not self._manifest:
            with open("protect_with_atakama/assets/manifest.json", "r") as f:
                self._manifest = f.read()
        return self._manifest

    def on_get(self, _req: falcon.Request, resp: falcon.Response):
        log.debug("on_get: manifest")
        try:
            resp.text = self.manifest
            log.debug(f"return manifest: len={len(resp.text)}")
        except:
            resp.status = falcon.HTTP_500
            log.exception("failed to get manifest")


class LogsResource:
    def on_get(self, _req: falcon.Request, resp: falcon.Response):
        log.debug("on_get: logs")
        try:
            with open(LOG_FILE, "r") as f:
                resp.text = f.read()
                log.debug(f"return logs: len={len(resp.text)}")
        except:
            resp.status = falcon.HTTP_500
            log.exception("failed to get logs")


class ExecuteResource:
    def on_post(self, req: falcon.Request, resp: falcon.Response):
        log.debug("on_post: execute")
        bigid_api = BigID(req.get_media())

        ds_name = bigid_api.action_params["data-source-name"]
        log.debug(f"data source name: {ds_name}")

        ds_scan_results = bigid_api.get(f"data-catalog?filter=system={ds_name}").json()
        #log.info(f"scan results: {ds_scan_results}")
        log.info(f"scan result rows: {ds_scan_results.get('totalRowsCounter')}")

        query = '[{ "field": "name", "value": "%s", "operator": "equal" }]' % ds_name
        ds_info = bigid_api.get(f"ds-connections?filter={query}").json()
        smb_server = ds_info["data"]["ds_connections"][0]["smbServer"]
        log.debug(f"smb server: {smb_server}")
        log.debug(f"data source info: {ds_info}")

        def empty_ip_labels() -> Dict[str, Any]:
            return {"files": {}}

        ip_labels: Dict[str, Any] = defaultdict(empty_ip_labels)

        for f in ds_scan_results.get("results"):
            labels = f.get("attribute")
            if labels:
                name = f.get("objectName")
                full = f.get("fullObjectName")
                parent_path = f"//{smb_server}/{full[0:-len(name) - 1]}".replace("/", "\\")
                ip_labels[parent_path]["files"][name] = {"labels": labels}

        log.debug(f"ip_labels: {ip_labels}")

        resp.text = bigid_api.get_progress_completed()

        # TODO: use SMB

        # with Smb("smbguest", "SolidG0LD", smb_server) as smb:
        #     smb.write_file("bigid-proto-3-smb", "/hello.txt", b"hello")


        # for k, v in ip_labels:
        #     ip_labels_path = f"{k}\\.ip-labels"
        #     log.debug(f"ip-labels path: {ip_labels_path}")
        #     with open(ip_labels_path, "wb") as f:
        #         f.write(json.dumps(v, indent=4).encode())







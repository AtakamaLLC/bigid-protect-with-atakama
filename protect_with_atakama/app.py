import logging
from typing import Dict, Any, List

import falcon
import requests

from protect_with_atakama.bigid_api import BigID, Status


class ManifestResource:
    def __init__(self):
        self._manifest: str = ""

    @property
    def manifest(self):
        if not self._manifest:
            with open("assets/manifest.json", "r") as f:
                self._manifest = f.read()
        return self._manifest

    def on_get(self, _req: falcon.Request, resp: falcon.Response):
        resp.text = self.manifest


class LogsResource:
    def on_get(self, _req: falcon.Request, resp: falcon.Response):
        resp.text = "put logs here"


class ExecuteResource:
    def on_post(self, req: falcon.Request, resp: falcon.Response):
        bigid_api = BigID(req.get_media())

        ds_name = bigid_api.action_params["data_source_name"]
        query = '[{ "field": "name", "value": "%s", "operator": "equal" }]' % ds_name
        ds_data = bigid_api.get(f"ds-connections?filter={query}").json()
        smb_server = ds_data["data"]["ds_connections"][0]["smbServer"]
        scan_results = bigid_api.get(f"data-catalog?filter=system={ds_name}").json()

        rows = scan_results.get("totalRowsCount")
        files = scan_results.get("results")
        for f in files:
            labels = f.get("attribute")
            if labels:
                name = f.get("objectName")
                full = f.get("fullObjectName")
                path = f"//{smb_server}/{full[0:-len(name) - 1]}".replace("/", "\\")
                #ip_labels[path]["files"][name] = {"labels": labels}

        resp.text = bigid_api.get_progress_completed()




app = falcon.App()
app.add_route('/manifest', ManifestResource())
app.add_route('/logs', LogsResource())
app.add_route("/execute", ExecuteResource())


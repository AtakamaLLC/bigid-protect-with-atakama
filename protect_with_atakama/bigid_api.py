import json
import logging
from enum import Enum, unique
from typing import Dict, Any, Optional, Generator

import requests

from protect_with_atakama.config import Config, DataSourceBase

log = logging.getLogger(__name__)


@unique
class Status(Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class BigID:
    """
    BigID API Wrapper

    Initialize with the params JSON received from BigID via the /execute endpoint:

    {
        'actionName': 'action-name-from-manifest',
        'executionId': 'exec-id-str',
        'globalParams': [{'paramName': 'name-str', 'paramValue': 'value-str'}],
        'actionParams': [{'paramName': 'name-str', 'paramValue': 'value-str'}],
        'bigidToken': 'token-str',
        'updateResultCallback': 'https://bigid-host.net:443/api/v1/tpa/executions/exec-id-str',
        'bigidBaseUrl': 'https://bigid-host.net:443/api/v1/',
        'tpaId': 'tpa-id-str'
    }

    """

    def __init__(self, params: Dict[str, Any]):
        self._action_name: str = params["actionName"]
        self._base_url: str = params["bigidBaseUrl"]
        self._update_url: str = params["updateResultCallback"]
        self._execution_id: str = params["executionId"]
        self._tpa_id: str = params["tpaId"]
        self._global_params = {
            p["paramName"]: p["paramValue"] for p in params["globalParams"]
        }
        self._action_params = {
            p["paramName"]: p["paramValue"] for p in params["actionParams"]
        }
        self._headers: Dict[str, str] = {
            "Content-Type": "application/json; charset=UTF-8",
            "Authorization": params["bigidToken"],
        }
        self._config = Config(self.global_params["Config"])
        log.info("init: %s", self._action_name)

    @property
    def global_params(self) -> Dict[str, Any]:
        return self._global_params

    @property
    def action_params(self) -> Dict[str, Any]:
        return self._action_params

    @property
    def action_name(self) -> str:
        return self._action_name

    @property
    def config(self) -> Config:
        return self._config

    def data_sources(self) -> Generator[DataSourceBase, None, None]:
        name_filter = self.action_params.get("Data Source Name", "")
        label_filter = self.action_params.get("Label Filter", "")
        for ds in self.config.data_sources:
            if name_filter and name_filter != ds.name:
                log.info("filtered out data source: %s (filter=%s)", ds.name, name_filter)
                continue

            if label_filter:
                # action param overrides global param
                ds.label_filter = label_filter

            query = [{"field": "name", "value": ds.name, "operator": "equal"}]
            params = {"filter": json.dumps(query)}
            ds_data = self.get("ds-connections", params=params).json()["data"]
            ds_count = ds_data["totalCount"]
            if ds_count != 1:
                # TODO: track errors
                log.error("unexpected count (%s) for data source: %s", ds_count, ds.name)
                continue

            ds_info = ds_data["ds_connections"][0]
            ds_type = ds_info["type"]
            if ds_type != ds.kind:
                # TODO: track errors
                log.error("unexpected type (%s) for data source: %s", ds_type, ds.name)
                continue

            try:
                ds.add_api_info(ds_info)
            except:
                # TODO: track errors
                log.exception("failed to add data source api info: %s", ds_info)
                continue

            yield ds

        # TODO: count data sources, error if 0

    def get(self, endpoint: str, params: Optional[Dict] = None) -> requests.Response:
        log.info("get: %s %s", endpoint, params)
        return requests.get(
            f"{self._base_url}{endpoint}", params=params, headers=self._headers
        )

    def post(self, endpoint, data) -> requests.Response:
        log.info("post: %s", endpoint)
        return requests.post(
            f"{self._base_url}{endpoint}", headers=self._headers, data=data
        )

    def put(self, endpoint, data) -> requests.Response:
        log.info("put: %s", endpoint)
        return requests.put(
            f"{self._base_url}{endpoint}", headers=self._headers, data=data
        )

    def send_progress_update(self, progress: float, message: str) -> requests.Response:
        log.info("send progress: %s %s", progress, message)
        data = self._progress_update(Status.IN_PROGRESS, progress, message)
        return requests.put(self._update_url, headers=self._headers, data=data)

    def get_progress_completed(self) -> str:
        return json.dumps(self._progress_update(Status.COMPLETED, 1.0, "Done"))

    def _progress_update(
        self, status: Status, progress: float, message: str
    ) -> Dict[str, str]:
        return {
            "executionId": self._execution_id,
            "statusEnum": status.name,
            "progress": progress,
            "message": message,
        }

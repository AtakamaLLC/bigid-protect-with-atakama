from enum import Enum, unique
from typing import Dict

import requests


@unique
class Status(Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class BigID:
    """
    BigID API Wrapper

    Initialize with the params Dict received from BigID via the /manifest endpoint.

    Use get() / put() / post() to query the BigID API.

    Use generate_response() to update BigID on /execute request progress.
    """

    def __init__(self, params: Dict[str, str]):
        self._base_url: str = params["bigidBaseUrl"]
        self._update_url: str = params["updateResultCallback"]
        self._execution_id: str = params["executionId"]
        self._tpa_id: str = params["tpaId"]
        self._headers: Dict[str, str] = {
            "Content-Type": "application/json; charset=UTF-8",
            "Authorization": params["bigidToken"]
        }

    def get(self, endpoint: str) -> requests.Response:
        return requests.get(f"{self._base_url}{endpoint}", headers=self._headers)

    def post(self, endpoint, data) -> requests.Response:
        return requests.post(f"{self._base_url}{endpoint}", headers=self._headers, data=data)

    def put(self, endpoint, data) -> requests.Response:
        return requests.put(f"{self._base_url}{endpoint}", headers=self._headers, data=data)

    def generate_response(self, status: Status, progress: float, message: str):
        return {
            "executionId": self._execution_id,
            "statusEnum": status.name,
            "progress": progress,
            "message": message
        }

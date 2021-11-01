from typing import Dict

import requests


class S3:

    def __init__(self, params: Dict[str, str]):
        self._base_url = params["base_url"]
        self._headers: Dict[str, str] = {
            "User-Agent": params["username"],
            "Referer": params["password"]
        }

    def put(self, path: str, content: bytes) -> requests.Response:
        return requests.put(f"{self._base_url}{path}", headers=self._headers, data=content)

    def get(self, path: str) -> requests.Response:
        return requests.get(f"{self._base_url}{path}", headers=self._headers)

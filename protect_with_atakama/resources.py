import html
import logging
import os

import falcon

from protect_with_atakama.executor import Executor
from protect_with_atakama.utils import (
    LOG_DIR,
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
                    all_logs += html.escape(log_file.read())
            resp.text = all_logs
            log.debug("return logs: len=%s", len(resp.text))
        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.text = repr(e)
            log.exception("failed to get logs - %s", repr(e))


class IconResource:
    """
    Returns the app's icon
    """

    icon_path = "protect_with_atakama/assets/icon.svg"

    def on_get(self, _req: falcon.Request, resp: falcon.Response):
        """
        Handle GET request
        """
        log.debug("on_get: icon")
        try:
            with open(self.icon_path, "rb") as f:
                resp.data = f.read()
                resp.content_type = "image/svg+xml"
            log.debug("return icon: len=%s", len(resp.data))
        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.text = repr(e)
            log.exception("failed to get icon - %s", repr(e))


class ExecuteResource:
    """
    Executes an action defined in the manifest
    """

    def on_post(
        self, req: falcon.Request, resp: falcon.Response
    ):  # pylint: disable=no-self-use
        """
        Handle POST request
        """
        try:
            log.debug("on_post: execute")
            executor = Executor(req.get_media())
            resp.text = executor.execute()

        except ExecutionError as e:
            resp.status = e.status
            resp.text = e.message
            log.exception("failed to execute - %s", repr(e))

        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.text = repr(e)
            log.exception("failed to execute - %s", repr(e))

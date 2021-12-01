import logging

import falcon

from protect_with_atakama.resources import (
    ManifestResource,
    LogsResource,
    ExecuteResource,
    IconResource,
)
from protect_with_atakama.utils import init_logging

init_logging()
log = logging.getLogger(__name__)


def get_app() -> falcon.App:
    log.info("initialize atakama app")
    atakama = falcon.App()
    atakama.add_route("/manifest", ManifestResource())
    atakama.add_route("/logs", LogsResource())
    atakama.add_route("/execute", ExecuteResource())
    atakama.add_route("/assets/icon", IconResource())
    return atakama


app = get_app()

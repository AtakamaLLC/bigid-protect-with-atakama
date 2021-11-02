import logging

import falcon

from protect_with_atakama.resources import ManifestResource, LogsResource, ExecuteResource
from protect_with_atakama.utils import init_logging

init_logging()
log = logging.getLogger(__name__)


def get_app() -> falcon.App:
    """
    App entry point
    """
    log.info("initialize app")
    app = falcon.App()
    app.add_route('/manifest', ManifestResource())
    app.add_route('/logs', LogsResource())
    app.add_route("/execute", ExecuteResource())
    return app


app = get_app()
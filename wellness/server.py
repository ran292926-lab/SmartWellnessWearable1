"""Settings for the development web server that runs the app (PR8, SR19)."""

import sys

from werkzeug import serving


def configure():
    # PR8: the server would otherwise log every request with the client's IP address,
    # which is not in the Personal Data Map.
    serving.WSGIRequestHandler.log_request = lambda *args, **kwargs: None

    # F5: error lines (for example failed TLS handshakes) are written without the client address.
    def log(handler, kind, message, *args):
        serving._log(kind, f"[{handler.log_date_time_string()}] {message}\n", *args)
    serving.WSGIRequestHandler.log = log

    def handle_error(server, request, client_address):
        if server.passthrough_errors:
            raise
        print("A connection failed before a request was read (client address not logged).", file=sys.stderr)
    serving.BaseWSGIServer.handle_error = handle_error

    # F6: the Server header does not reveal the Werkzeug and Python versions.
    serving.WSGIRequestHandler.version_string = lambda handler: "SmartWellness"

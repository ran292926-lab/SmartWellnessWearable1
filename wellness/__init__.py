"""Smart Wellness Wearable web application."""

import time

from flask import Flask, render_template, request
from werkzeug.exceptions import HTTPException

from . import crypto, db, headers, ratelimit, retention
from .config import Config
from .sessions import check_csrf, load_session


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    # F9: browsers keep CSS and JavaScript for an hour, so they do not count towards
    # the SR27 limit on every page; the version changes at each server start.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600
    app.jinja_env.globals["static_version"] = str(int(time.time()))

    db.init_db(app.config["DATABASE"])
    crypto.load_key(app.config)
    with app.app_context():
        retention.apply()                         # PR5, PR12, SR23 at startup

    app.before_request(ratelimit.check)           # SR27
    app.before_request(retention.apply_hourly)   # PR5, PR12, SR23
    app.before_request(load_session)
    app.before_request(check_csrf)               # F1
    app.teardown_appcontext(db.close_db)
    app.after_request(headers.add)               # Week 12: W1-W5

    from . import account, api, auth, pages, privacy
    app.register_blueprint(auth.bp)
    app.register_blueprint(pages.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(account.bp)
    app.register_blueprint(privacy.bp)                # PR15-PR19

    # SR19: error messages without stack traces, database details or file paths
    @app.errorhandler(HTTPException)
    def http_error(e):
        if request.path.startswith("/api/"):
            return {"error": e.name}, e.code
        messages = {404: "Page not found.", 405: "This page cannot be opened directly. Go back to the home page."}
        return render_template("error.html", detail=messages.get(e.code, "The request could not be completed.")), e.code

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("error.html", detail="An unexpected error occurred."), 500

    return app

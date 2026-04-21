from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .runtime_config import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_SECRET_KEY,
    load_env_config,
)


def create_app(test_config=None, instance_path=None) -> Flask:
    flask_kwargs = {"instance_relative_config": True}
    if instance_path is not None:
        flask_kwargs["instance_path"] = str(Path(instance_path).resolve())

    app = Flask(__name__, **flask_kwargs)
    instance_dir = Path(app.instance_path)
    instance_dir.mkdir(parents=True, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=DEFAULT_SECRET_KEY,
        DATABASE=str(instance_dir / "search_aggregator.sqlite3"),
        ADMIN_PASSWORD=DEFAULT_ADMIN_PASSWORD,
        PREFERRED_URL_SCHEME="http",
        TRUST_PROXY=False,
    )

    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
        app.config.update(load_env_config())
    else:
        app.config.update(load_env_config())
        app.config.update(test_config)

    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    from . import db

    db.init_app(app)

    from . import feed_import

    feed_import.init_app(app)

    from . import release_checks

    release_checks.init_app(app)

    from .routes import bp

    app.register_blueprint(bp)

    @app.get("/health")
    def health():
        return {"status": "ok", "app": "search-aggregator"}

    @app.get("/health/ready")
    def health_ready():
        snapshot = release_checks.get_release_readiness_snapshot()
        status_code = 200 if snapshot["ready_for_launch"] else 503
        return {
            "status": "ready" if snapshot["ready_for_launch"] else "not_ready",
            "ready": snapshot["ready_for_launch"],
            "blocking_issues": snapshot["blocking_issues"],
            "warning_issues": snapshot["warning_issues"],
        }, status_code

    return app

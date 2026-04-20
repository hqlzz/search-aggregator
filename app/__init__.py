from pathlib import Path

from flask import Flask


def create_app(test_config=None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='***',
        DATABASE=str(Path(app.instance_path) / 'search_aggregator.sqlite3'),
        ADMIN_PASSWORD='***',
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.update(test_config)

    from . import db
    db.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    @app.get('/health')
    def health():
        return {'status': 'ok', 'app': 'search-aggregator'}

    return app

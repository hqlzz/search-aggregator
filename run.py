import os

from app import create_app
from app.runtime_config import parse_env_flag


def get_run_settings():
    return {
        "host": os.environ.get("SEARCH_AGGREGATOR_HOST", "0.0.0.0"),
        "port": int(os.environ.get("SEARCH_AGGREGATOR_PORT", "8765")),
        "debug": parse_env_flag("SEARCH_AGGREGATOR_DEBUG"),
    }


app = create_app()


if __name__ == "__main__":
    app.run(**get_run_settings())

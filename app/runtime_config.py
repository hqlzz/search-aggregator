import os


DEFAULT_SECRET_KEY = "dev-secret-key-change-me"
DEFAULT_ADMIN_PASSWORD = "change-me"


def parse_env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_env_config():
    config = {}
    env_mappings = {
        "SEARCH_AGGREGATOR_SECRET_KEY": "SECRET_KEY",
        "SEARCH_AGGREGATOR_DATABASE": "DATABASE",
        "SEARCH_AGGREGATOR_ADMIN_PASSWORD": "ADMIN_PASSWORD",
        "SEARCH_AGGREGATOR_PREFERRED_URL_SCHEME": "PREFERRED_URL_SCHEME",
    }
    for env_name, config_name in env_mappings.items():
        value = os.environ.get(env_name)
        if value:
            config[config_name] = value

    if "SEARCH_AGGREGATOR_TRUST_PROXY" in os.environ:
        config["TRUST_PROXY"] = parse_env_flag("SEARCH_AGGREGATOR_TRUST_PROXY")

    return config

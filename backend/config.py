"""Load settings from a .env file in the project root into os.environ.

Stdlib only. Real environment variables always win over values in .env.
Key values are never printed or logged.
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ENV_PATH = os.path.join(PROJECT_ROOT, ".env")


def _strip_quotes(value):
    """Remove one pair of matching surrounding single or double quotes."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def load_env(path=None):
    """Read KEY=VALUE lines from a .env file into os.environ.

    A key already present in the environment is left unchanged.
    A missing file loads nothing. Returns the number of keys loaded.
    """
    env_path = path or DEFAULT_ENV_PATH
    if not os.path.isfile(env_path):
        return 0

    loaded = 0
    with open(env_path, "r", encoding="utf-8-sig") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = _strip_quotes(value.strip())
            if not key or key in os.environ:
                continue
            os.environ[key] = value
            loaded += 1
    return loaded

"""Environment resolution for local project configuration."""

import os


def environment_value(name, default=None):
    return os.environ.get(name, default)

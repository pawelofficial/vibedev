"""vibedev — agentic development as a Python package.

Typical use:

    import vibedev
    vibedev.prompt("build a calculator web app")

By default the agent works inside ``./vibedev-output/<timestamp>/`` with
``bypassPermissions`` mode. Override with the ``set_*`` configurators.
"""

from vibedev.config import (
    get_config,
    set_model,
    set_permissions,
    set_workspace_root,
)
from vibedev.core import prompt

__all__ = [
    "prompt",
    "set_permissions",
    "set_model",
    "set_workspace_root",
    "get_config",
]

__version__ = "0.1.0"

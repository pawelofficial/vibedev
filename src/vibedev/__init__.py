"""vibedev — agentic development as a Python package.

Typical use:

    import vibedev
    vibedev.prompt("build a calculator web app")

By default the agent works inside ``./vibedev-output/`` (created if missing)
with ``bypassPermissions`` mode. Override with the ``set_*`` configurators.
"""

from vibedev.config import (
    LOG_LEVEL,
)
__version__ = "0.1.0"

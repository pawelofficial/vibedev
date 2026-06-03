"""
calculator/extensions.py
~~~~~~~~~~~~~~~~~~~~~~~~
Module-level singleton for the arithmetic engine.

Instantiated once at import time so that routes.py (and any future
extension) can do::

    from calculator.extensions import calculator

and always receive the same ``Calculator`` instance.  Because
``Calculator`` is completely stateless there is no thread-safety concern.
"""

from calculator.engine import Calculator

#: Shared engine instance — import this, never construct your own.
calculator = Calculator()

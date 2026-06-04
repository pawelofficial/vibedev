"""Utility for normalising SQL identifiers across dialects."""

import re

# Matches any of the three quoting styles wrapping the entire identifier:
#   ANSI / standard:  "name"
#   MySQL:            `name`
#   T-SQL:            [name]
_QUOTED = re.compile(
    r'^"(?P<ansi>[^"]*)"$'      # ANSI double-quotes
    r"|^`(?P<mysql>[^`]*)`$"    # MySQL back-ticks
    r"|^\[(?P<tsql>[^\]]*)\]$"  # T-SQL square brackets
)


def normalize_name(name: str) -> str:
    """Strip SQL quoting characters and return a lowercased, whitespace-stripped identifier.

    Handles all three common quoting styles:
      * ANSI / standard: ``"name"``
      * MySQL:           `` `name` ``
      * T-SQL:           ``[name]``

    When no quoting is present the input is returned lowercased and stripped
    of surrounding whitespace unchanged.  An empty string is returned as-is.

    Args:
        name: A raw SQL identifier token, optionally surrounded by quotes.

    Returns:
        The unquoted, lowercased, whitespace-stripped identifier string.
    """
    if not name:
        return ""

    stripped = name.strip()
    m = _QUOTED.match(stripped)
    if m:
        inner = m.group("ansi") or m.group("mysql") or m.group("tsql") or ""
        return inner.lower().strip()

    return stripped.lower()

"""Custom exception types for the sql_lineage package.

Kept in their own module so every other module can import them
without creating circular imports.
"""

from __future__ import annotations


class SchemaParseError(Exception):
    """Base exception for all errors raised by sql_lineage.

    Parameters
    ----------
    message:
        Human-readable description of the error.
    detail:
        Optional supplementary information (e.g. the offending SQL fragment).
    """

    detail: str

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return f"{self.message} – {self.detail}"
        return self.message


class UnresolvedReferenceError(SchemaParseError):
    """Raised when a column or table reference inside a view cannot be
    matched to a known table/column.

    Parameters
    ----------
    ref:
        The unresolved identifier string.
    context:
        Optional context describing where the reference appeared.
    """

    ref: str

    def __init__(self, ref: str, context: str = "") -> None:
        self.ref = ref
        super().__init__(f"Unresolved reference: {ref}", detail=context)


class CircularDependencyError(SchemaParseError):
    """Raised when a cycle is detected in the view dependency graph.

    Parameters
    ----------
    cycle:
        Ordered list of view/table names that form the cycle.
    """

    cycle: list[str]

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__(
            "Circular dependency detected: " + " -> ".join(cycle)
        )

"""
calculator/engine.py
~~~~~~~~~~~~~~~~~~~~
Pure-Python arithmetic engine.  No Flask imports.

Expressions are evaluated through Python's AST parser so that arbitrary
code execution is impossible — only a small, explicit whitelist of node
types is permitted before the sanitised tree is handed to eval/compile.
"""

import ast

# Build the frozenset of allowed AST node types.  ast.Num / ast.Str were
# deprecated in Python 3.8 and removed in 3.12; we add them only when
# present so the engine works across all supported interpreter versions.
_ALLOWED: set = {
    ast.Expression,
    ast.Constant,      # numeric / boolean literals (Python ≥ 3.8)
    ast.BinOp,         # a + b, a * b, …
    ast.UnaryOp,       # -x, +x
    # binary-operator node types
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    # unary-operator node types
    ast.UAdd,
    ast.USub,
}

# Backward-compat: ast.Num is the legacy literal node (Python < 3.8 style)
if hasattr(ast, "Num"):          # pragma: no cover – Python ≤ 3.7 / compat
    _ALLOWED.add(ast.Num)        # type: ignore[attr-defined]


class Calculator:
    """Stateless engine that receives a raw expression string and returns a
    numeric result, or raises ``ValueError`` on invalid / unsafe input.

    Usage::

        calc = Calculator()
        result = calc.evaluate("(3 + 4) * 2")   # → 14.0
    """

    #: AST node types that are permitted during the safety walk.
    ALLOWED_NODES: frozenset = frozenset(_ALLOWED)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, expression: str) -> float:
        """Parse *expression* with :func:`ast.parse`, walk the AST to reject
        unsafe nodes, then compile and eval the sanitised tree.

        Parameters
        ----------
        expression:
            A raw arithmetic expression string (e.g. ``"1 + 2 * (3 / 4)"``).

        Returns
        -------
        float
            The numeric result.  The caller is responsible for display
            formatting (e.g. stripping a trailing ``.0``).

        Raises
        ------
        ValueError
            On empty input, syntax errors, disallowed AST nodes, division by
            zero, or any other evaluation failure.
        """
        try:
            expression = str(expression).strip()
        except (TypeError, AttributeError) as exc:
            raise ValueError(f"Expression must be a string: {exc}") from exc
        if not expression:
            raise ValueError("Expression must not be empty.")

        # ---- 1. Parse ----
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"Invalid expression syntax: {exc}") from exc

        # ---- 2. Safety walk — reject anything outside the whitelist ----
        for node in ast.walk(tree):
            if type(node) not in self.ALLOWED_NODES:
                raise ValueError(
                    f"Unsafe or unsupported operation: "
                    f"{type(node).__name__!r} is not allowed."
                )

        # ---- 3. Compile + eval the validated AST ----
        try:
            # compile() accepts an ast.Expression object directly; the result
            # is a plain code object that eval() can execute.  Because we
            # already walked and approved every node this is safe.
            result = eval(compile(tree, filename="<expression>", mode="eval"))  # noqa: S307
        except ZeroDivisionError:
            raise ValueError("Division by zero.")
        except Exception as exc:
            raise ValueError(f"Could not evaluate expression: {exc}") from exc

        try:
            return float(result)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Could not convert result to number: {exc}") from exc

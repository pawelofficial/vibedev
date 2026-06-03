"""Safe AST-based expression evaluator for the flask-calculator app."""

import ast


class CalculatorError(ValueError):
    """Raised for all evaluation failures (division-by-zero, unsupported nodes, syntax errors, empty input)."""


class Calculator:
    """Stateless calculator engine that evaluates expression strings via a sandboxed AST walk."""

    class _SafeVisitor(ast.NodeVisitor):
        """Walks a parsed AST and evaluates only the explicitly allowed node types."""

        def visit_BinOp(self, node: ast.BinOp) -> float:
            left = self.visit(node.left)
            right = self.visit(node.right)
            op = node.op
            if isinstance(op, ast.Add):
                return left + right
            if isinstance(op, ast.Sub):
                return left - right
            if isinstance(op, ast.Mult):
                return left * right
            if isinstance(op, ast.Div):
                if right == 0:
                    raise CalculatorError("Division by zero")
                return left / right
            if isinstance(op, ast.Mod):
                if right == 0:
                    raise CalculatorError("Division by zero")
                return left % right
            raise CalculatorError("Unsupported operation")

        def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
            if isinstance(node.op, ast.USub):
                return -self.visit(node.operand)
            raise CalculatorError("Unsupported operation")

        def visit_Constant(self, node: ast.Constant) -> float:
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise CalculatorError("Unsupported operation")

        def generic_visit(self, node: ast.AST) -> float:  # type: ignore[override]
            raise CalculatorError("Unsupported operation")

    def evaluate(self, expression: str) -> float:
        """Parse *expression*, walk the AST, and return the numeric result as a float.

        Raises:
            CalculatorError: for empty input, syntax errors, unsupported node types,
                             division/modulo by zero, or any other evaluation failure.
        """
        if not expression or not expression.strip():
            raise CalculatorError("Empty expression")

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise CalculatorError(f"Syntax error: {exc}") from exc

        visitor = self._SafeVisitor()
        try:
            result = visitor.visit(tree.body)
        except CalculatorError:
            raise
        except Exception as exc:
            raise CalculatorError(f"Evaluation error: {exc}") from exc

        return float(result)

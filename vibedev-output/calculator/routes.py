"""
calculator/routes.py
~~~~~~~~~~~~~~~~~~~~
Flask Blueprint with all HTTP handlers for the calculator app.

Routes
------
GET  /            – Renders the single-page calculator UI.
POST /calculate   – Accepts JSON {expression: str} and returns
                    {result: str} on success or {error: str} (HTTP 400)
                    on failure.
"""

from flask import Blueprint, jsonify, render_template, request

from calculator.extensions import calculator

#: Blueprint instance registered on the application factory in __init__.py.
bp = Blueprint("calculator", __name__)


@bp.route("/")
def index():
    """Render the calculator single-page UI."""
    return render_template("index.html")


@bp.route("/calculate", methods=["POST"])
def calculate():
    """Evaluate an arithmetic expression and return the result as JSON.

    Request body (JSON)::

        {"expression": "3 + 4 * 2"}

    Success response (HTTP 200)::

        {"result": "11"}

    Error response (HTTP 400)::

        {"error": "Division by zero."}
    """
    data = request.get_json(force=True) or {}
    expression = data.get("expression", "")

    try:
        raw = calculator.evaluate(expression)
        # Format cleanly: drop the redundant ".0" for whole-number results.
        result_str = str(int(raw)) if raw == int(raw) else str(raw)
        return jsonify({"result": result_str})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

"""
Flask Blueprint with all route handlers for the Column Lineage Web App.

Handlers import MODELS and GRAPH from schema_service (cached; parsed once).
"""

from flask import Blueprint, jsonify, send_from_directory

from lineage_parser import get_upstream_lineage, get_downstream_lineage
from schema_service import load_schema

bp = Blueprint('lineage', __name__)

# Resolve schema data once at import time (cached in schema_service)
MODELS, GRAPH = load_schema()


@bp.route('/')
def index():
    return send_from_directory('static', 'index.html')


@bp.route('/api/graph')
def api_graph():
    """Return the full lineage graph (nodes + edges)."""
    return jsonify(GRAPH)


@bp.route('/api/upstream/<model_name>/<column_name>')
def api_upstream(model_name, column_name):
    """Return recursive upstream lineage for a column."""
    sources = get_upstream_lineage(MODELS, model_name, column_name)
    return jsonify({'model': model_name, 'column': column_name, 'upstream': sources})


@bp.route('/api/downstream/<model_name>/<column_name>')
def api_downstream(model_name, column_name):
    """Return recursive downstream lineage for a column."""
    consumers = get_downstream_lineage(MODELS, model_name, column_name)
    return jsonify({'model': model_name, 'column': column_name, 'downstream': consumers})


@bp.route('/api/models')
def api_models():
    """List all models with their types."""
    return jsonify([
        {'name': m.name, 'type': m.model_type, 'column_count': len(m.columns)}
        for m in MODELS.values()
    ])

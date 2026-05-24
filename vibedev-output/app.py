"""
Column Lineage Web App - Flask backend.

Serves the interactive column-lineage UI and provides API endpoints
for lineage data.
"""

import json
from pathlib import Path
from flask import Flask, jsonify, send_from_directory

from lineage_parser import parse_schema, get_lineage_graph, get_upstream_lineage, get_downstream_lineage

app = Flask(__name__, static_folder='static')

# Parse schema on startup
SCHEMA_PATH = Path(__file__).parent / 'schema.txt'
_schema_text = SCHEMA_PATH.read_text(encoding='utf-8')
MODELS = parse_schema(_schema_text)
GRAPH = get_lineage_graph(MODELS)


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/graph')
def api_graph():
    """Return the full lineage graph (nodes + edges)."""
    return jsonify(GRAPH)


@app.route('/api/upstream/<model_name>/<column_name>')
def api_upstream(model_name, column_name):
    """Return recursive upstream lineage for a column."""
    sources = get_upstream_lineage(MODELS, model_name, column_name)
    return jsonify({'model': model_name, 'column': column_name, 'upstream': sources})


@app.route('/api/downstream/<model_name>/<column_name>')
def api_downstream(model_name, column_name):
    """Return recursive downstream lineage for a column."""
    consumers = get_downstream_lineage(MODELS, model_name, column_name)
    return jsonify({'model': model_name, 'column': column_name, 'downstream': consumers})


@app.route('/api/models')
def api_models():
    """List all models with their types."""
    return jsonify([
        {'name': m.name, 'type': m.model_type, 'column_count': len(m.columns)}
        for m in MODELS.values()
    ])


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


if __name__ == '__main__':
    app.run(debug=True, port=5000)

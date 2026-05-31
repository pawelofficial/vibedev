"""
Flask Blueprint with all route handlers for the Column Lineage Web App.

Handlers import MODELS and GRAPH from schema_service (cached; parsed once).
"""

import os
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

from generate_schema import build_schema_from_postgres
from lineage_parser import get_upstream_lineage, get_downstream_lineage
from schema_service import SCHEMA_PATH, load_schema, reload_schema

bp = Blueprint('lineage', __name__)

# Resolve schema data once at import time (cached in schema_service)
MODELS, GRAPH = load_schema()


def _load_env_files():
    """Load .env files from the app directory and parent project if available."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    app_dir = Path(__file__).resolve().parent
    for env_path in (app_dir / '.env', app_dir.parent / '.env'):
        if env_path.exists():
            load_dotenv(env_path, override=False)


def _build_postgres_dsn(database):
    _load_env_files()
    dbname = database or os.getenv('PG_DATABASE')
    host = os.getenv('PG_HOST')
    port = os.getenv('PG_PORT')
    user = os.getenv('PG_USER')
    password = os.getenv('PG_PASSWORD')

    missing = [
        name for name, value in {
            'database': dbname,
            'PG_HOST': host,
            'PG_PORT': port,
            'PG_USER': user,
            'PG_PASSWORD': password,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(
            'Missing PostgreSQL configuration: ' + ', '.join(missing)
        )

    return (
        f"host={host} port={port} dbname={dbname} "
        f"user={user} password={password}"
    )


def _safe_output_path(output_path):
    requested = (output_path or 'schema.txt').strip() or 'schema.txt'
    target = (Path(__file__).resolve().parent / requested).resolve()
    app_dir = Path(__file__).resolve().parent
    if app_dir not in target.parents and target != app_dir:
        raise ValueError('Output path must stay inside the app directory.')
    return target


@bp.route('/')
def index():
    return send_from_directory('static', 'index.html')


@bp.route('/api/graph')
def api_graph():
    """Return the full lineage graph (nodes + edges)."""
    return jsonify(GRAPH)


@bp.route('/api/generate-schema', methods=['POST'])
def api_generate_schema():
    """Regenerate schema.txt by introspecting a PostgreSQL database."""
    global MODELS, GRAPH

    payload = request.get_json(silent=True) or {}
    database = (payload.get('database') or '').strip()
    schemas = [
        s.strip()
        for s in (payload.get('schemas') or 'public').split(',')
        if s.strip()
    ]
    if not schemas:
        return jsonify({'error': 'At least one schema is required.'}), 400

    try:
        dsn = _build_postgres_dsn(database)
        schema_parts = []
        for schema_name in schemas:
            schema_parts.append(
                f"-- PostgreSQL schema: {schema_name}\n"
                + build_schema_from_postgres(dsn, pg_schema=schema_name).strip()
            )

        target = _safe_output_path(payload.get('output'))
        target.write_text('\n\n'.join(schema_parts) + '\n', encoding='utf-8')

        if target == SCHEMA_PATH.resolve():
            MODELS, GRAPH = reload_schema()

        return jsonify({
            'ok': True,
            'output': str(target),
            'schemas': schemas,
            'table_count': sum(part.count('CREATE TABLE') for part in schema_parts),
            'view_count': sum(part.count('CREATE VIEW') for part in schema_parts),
            'graph': GRAPH if target == SCHEMA_PATH.resolve() else None,
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


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

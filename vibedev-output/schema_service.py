"""
Schema loading service for the Column Lineage Web App.

Parses schema.txt on first call and caches the result so multiple
imports or calls do not re-parse.
"""

from pathlib import Path

from lineage_parser import parse_schema, get_lineage_graph

SCHEMA_PATH = Path(__file__).parent / 'schema.txt'

# Module-level cache — populated on first call to load_schema()
_models = None
_graph = None


def load_schema():
    """Load and parse schema.txt, returning (models, graph).

    Results are cached at module level — subsequent calls return the
    same objects without re-reading or re-parsing.
    """
    global _models, _graph
    if _models is None:
        schema_text = SCHEMA_PATH.read_text(encoding='utf-8')
        _models = parse_schema(schema_text)
        _graph = get_lineage_graph(_models)
    return _models, _graph

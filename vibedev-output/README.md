# Column Lineage Explorer

Interactive web application that parses SQL DDL (tables and views) and displays column-level lineage in a graph UI.

## Features

- **Model Nodes**: Shows all 6 base tables and 8 views as interactive graph nodes
- **Column-Level Lineage Edges**: Traces data flow from source columns to derived columns
- **Click to Inspect**: Click any model or column to see upstream/downstream lineage
- **Multi-Source Derivation**: Columns derived from multiple upstream sources are marked with ◆
- **Search**: Search box for finding models and columns by name
- **Default View**: Opens focused on the `mart_customer_ltv_segments` model
- **Pan & Zoom**: Mouse drag to pan, scroll wheel to zoom
- **Drag-to-Reposition Nodes**: Click and drag any table or view node to reposition it on the canvas. Connected edges update in real time. Positions persist across page refreshes via `sessionStorage` (cleared when the browser tab closes). Click "Reset View" to restore all nodes to their default layout positions

## Lineage Capabilities

The parser handles:
- Direct passthrough columns
- Aliases and renamed columns
- Casts (`::TYPE`)
- CASE expressions
- Functions: COALESCE, NULLIF, LOWER, TRIM, UPPER, DATE_TRUNC
- String concatenation (`||`)
- Arithmetic expressions
- Joins across multiple tables
- CTEs (WITH ... AS) — resolved transparently to real models
- Aggregate functions (COUNT, SUM, MIN, MAX) and filtered aggregates (FILTER WHERE)
- UNION ALL (merges lineage from all branches)
- Window functions (DENSE_RANK, NTILE, etc.)
- Views depending on other views (multi-layer lineage)

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Or install individually
pip install flask sqlglot
```

## Run

```bash
# Start the web server
python app.py

# Open in browser
# http://localhost:5000
```

## Test

```bash
# Run the full test suite (253 tests)
python -m pytest tests/ -v

# Run only the lineage-extraction tests (56 tests)
python -m pytest tests/test_lineage.py -v

# Run only the verification / integration tests (54 tests)
python -m pytest tests/test_tester_verification.py -v

# Run only the drag-feature verification tests (53 tests)
python -m pytest tests/test_drag_verification.py -v

# Run only the backend modularization tests (30 tests)
python -m pytest tests/test_modularization.py -v

# Run only the sqlglot parser tests (41 tests)
python -m pytest tests/test_sqlglot_parser.py -v

# Run only the sqlglot verification tests (19 tests)
python -m pytest tests/test_tester_sqlglot_verification.py -v

# Run specific test classes
python -m pytest tests/test_lineage.py::TestSpecificLineageRequirements -v
python -m pytest tests/test_lineage.py::TestMartCustomerLtvSegments -v
python -m pytest tests/test_tester_verification.py::TestDeepLineageProofs -v
python -m pytest tests/test_tester_verification.py::TestFlaskAPI -v
python -m pytest tests/test_tester_verification.py::TestDragInfrastructure -v
python -m pytest tests/test_sqlglot_parser.py::TestNestedCTEs -v
```

## Project Structure

```
├── app.py                          # Flask application entry point (creates app, registers blueprint)
├── routes.py                       # Flask Blueprint with all route handlers
├── schema_service.py               # Schema loading service (parses schema.txt, caches result)
├── lineage_parser.py               # SQL DDL parser + lineage extraction engine
├── schema.txt                      # Input SQL schema (6 tables, 8 views)
├── static/
│   ├── index.html                  # Main UI page
│   ├── app.js                      # Frontend graph visualization (SVG-based)
│   └── style.css                   # Dark-theme styles
├── tests/
│   ├── test_lineage.py                    # 56 tests covering all lineage scenarios
│   ├── test_tester_verification.py        # 54 tests: deep lineage, API, graph, drag infrastructure
│   ├── test_drag_verification.py          # 53 tests: drag-feature structural verification
│   ├── test_modularization.py             # 30 tests: module structure, imports, caching, backward compat
│   ├── test_sqlglot_parser.py             # 41 tests: sqlglot parsing, CTEs, UNION ALL, window funcs, dbt templates
│   └── test_tester_sqlglot_verification.py # 19 tests: sqlglot integration, cross-view chains, fallback path
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main UI |
| `GET /api/graph` | Full lineage graph (nodes + edges) |
| `GET /api/models` | List all models with types |
| `GET /api/upstream/<model>/<column>` | Recursive upstream lineage |
| `GET /api/downstream/<model>/<column>` | Recursive downstream lineage |

## Architecture

### Backend modules

The Flask backend is split into three peer modules for maintainability:

- **`app.py`** — Thin entry point (~12 lines). Creates the `Flask` instance, registers the Blueprint from `routes.py`, and provides the `if __name__ == '__main__'` dev-server block. `from app import app` still works for backward compatibility.
- **`schema_service.py`** — Schema loading with module-level caching. `load_schema()` reads and parses `schema.txt` once; subsequent calls return the same cached `(MODELS, GRAPH)` tuple.
- **`routes.py`** — Flask Blueprint (`bp`) with all five API route handlers. Imports parsed data from `schema_service` rather than parsing directly.
- **`lineage_parser.py`** — Pure-Python SQL DDL parser, fully decoupled from Flask.

### Parser

The parser uses [sqlglot](https://github.com/tobymao/sqlglot) as its primary SQL parsing engine, with a regex-based fallback for per-statement error recovery. It:

1. Parses all SQL DDL via `sqlglot.parse()` (PostgreSQL dialect) for robust AST-based extraction
2. Extracts `CREATE TABLE` column definitions from the sqlglot AST (`ColumnDef` nodes)
3. Parses `CREATE VIEW` statements including CTEs, UNION ALL, and nested subqueries via AST traversal
4. Resolves table aliases from `FROM`/`JOIN` clauses using sqlglot `Table` and `Join` nodes
5. Extracts SELECT expressions and resolves column references (`Column` nodes) to upstream sources
6. Resolves CTE references transparently — the final view lineage shows only real tables/views
7. Handles `SELECT *` expansion from source models
8. Preprocesses dbt Jinja templates (`{{ source(...) }}`, `{{ ref(...) }}`) before parsing
9. Falls back to regex parsing per-statement when sqlglot cannot handle a particular construct

### Frontend

The frontend uses vanilla JavaScript with SVG for rendering the directed acyclic graph. No external visualization libraries required.

# Column Lineage Explorer

Interactive web application that parses SQL DDL (tables and views) and displays column-level lineage in a graph UI.

## Features

- **Model Nodes**: Shows all 5 base tables and 8 views as interactive graph nodes
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
pip install flask
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
# Run the full test suite (163 tests)
python -m pytest tests/ -v

# Run only the lineage-extraction tests (56 tests)
python -m pytest tests/test_lineage.py -v

# Run only the verification / integration tests (54 tests)
python -m pytest tests/test_tester_verification.py -v

# Run only the drag-feature verification tests (53 tests)
python -m pytest tests/test_drag_verification.py -v

# Run specific test classes
python -m pytest tests/test_lineage.py::TestSpecificLineageRequirements -v
python -m pytest tests/test_lineage.py::TestMartCustomerLtvSegments -v
python -m pytest tests/test_tester_verification.py::TestDeepLineageProofs -v
python -m pytest tests/test_tester_verification.py::TestFlaskAPI -v
python -m pytest tests/test_tester_verification.py::TestDragInfrastructure -v
```

## Project Structure

```
├── app.py                          # Flask web server + API endpoints
├── lineage_parser.py               # SQL DDL parser + lineage extraction engine
├── schema.txt                      # Input SQL schema (5 tables, 8 views)
├── static/
│   ├── index.html                  # Main UI page
│   ├── app.js                      # Frontend graph visualization (SVG-based)
│   └── style.css                   # Dark-theme styles
├── tests/
│   ├── test_lineage.py             # 56 tests covering all lineage scenarios
│   ├── test_tester_verification.py # 54 tests: deep lineage, API, graph, drag infrastructure
│   └── test_drag_verification.py   # 53 tests: drag-feature structural verification
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

The parser is pragmatic and tailored to PostgreSQL DDL. It:

1. Extracts `CREATE TABLE` definitions for base table columns
2. Parses `CREATE VIEW` statements including CTEs, UNION ALL, and nested subqueries
3. Resolves table aliases from FROM/JOIN clauses
4. Extracts SELECT expressions and resolves column references to upstream sources
5. Resolves CTE references transparently — the final view lineage shows only real tables/views
6. Handles `SELECT *` expansion from source models

The frontend uses vanilla JavaScript with SVG for rendering the directed acyclic graph. No external visualization libraries required.

# vibedev plan

## Goal
Build a column-lineage web app for the SQL models in schema.txt.

## Tasks
- [x] Build a column-lineage web app for the SQL models in schema.txt.
- [x] Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.
- [x] Add node-level drag handlers to `renderNodes()` in `static/app.js` using PointerEvents, with a 4px movement threshold to disambiguate click from drag.
- [x] Implement connected-edge re-rendering on drag: on each `pointermove` during a node drag, recompute and update only the SVG `<path>` elements whose `data-source-model` or `data-target-model` matches the dragged node.
- [x] Add `cursor: grab` / `cursor: grabbing` CSS rules for `.model-node` elements during hover and active drag states.
- [x] Persist dragged positions to `sessionStorage` (keyed by node ID); restore them in `layoutGraph()` if present, so positions survive in-page navigation and soft refreshes within the session.
- [x] Ensure the existing "Reset View" button also clears stored positions from `sessionStorage` and re-runs `layoutGraph()` to return nodes to their default positions.
- [x] Raise dragged node to top z-order (re-append the `<g>` element to its parent) during drag to avoid overlap confusion.
- [x] Add Python/pytest structural tests verifying: (a) the `app.js` source contains pointer event listeners on node groups, (b) the `style.css` contains `cursor: grab` for `.model-node`, (c) the Flask-served HTML includes `app.js` with drag-rel...
- [x] Update `README.md` to document the new drag-to-reposition behavior under the Features section and note session-scoped persistence.
- [x] Modularize the Flask backend currently concentrated in `app.py` so the backend is easier to maintain and extend.
- [ ] **Decide on module layout**: Choose between flat peer modules (`routes.py`, `schema_service.py` beside `app.py`) or a Flask package directory (`app/` with `__init__.py`).
- [ ] **Extract schema loading into `schema_service.py`**: Move `SCHEMA_PATH` resolution, `parse_schema()` call, and `MODELS`/`GRAPH` computation into a dedicated module with a public `load_schema()` function that returns `(models, graph)` and c...
- [ ] **Extract API route handlers into `routes.py`**: Move the five route handler functions (`index`, `api_graph`, `api_upstream`, `api_downstream`, `api_models`) into a Flask Blueprint in a new `routes.py`.
- [ ] **Reduce `app.py` to an application factory / entry point**: `app.py` should create the `Flask` instance, call `schema_service.load_schema()` (or import the cached globals), register the Blueprint from `routes.py`, and retain the `if __nam...
- [ ] **Update all test imports to use the new module structure**: Update `from app import app` in `test_tester_verification.py` (3 occurrences) and `test_drag_verification.py` (1 occurrence) to import through the new structure.
- [ ] **Run the full pytest suite (`python -m pytest tests/ -v`) and fix any regressions** caused by the refactor.
- [ ] **Update `README.md`**: Revise the "Project Structure" tree diagram to show the new modules.
- [x] **Remove the "Decide on module layout" task** — commit to the flat peer-module approach (`schema_service.py` and `routes.py` as siblings of `app.py`).
- [x] **Resolve whether the explicit `static_files` route should be kept or dropped** during the Blueprint extraction.
- [x] **Add a smoke test that `python app.py` still starts the server** (or at minimum, verify the `if __name__ == '__main__'` block is present and `app` is importable from `app.py`).
- [x] Use `sqlglot` when parsing `schema.txt` so SQL DDL and SELECT expressions are parsed more robustly than the current regex-first approach.
- [ ] **Clean up stale plan state**: Mark the 7 pending modularization sub-tasks as complete (the modules `schema_service.py`, `routes.py`, and the slim `app.py` already exist and pass tests), so the developer starts with a clean task list.
- [ ] **Add `sqlglot` to `requirements.txt`**: Add `sqlglot>=26.0` as a dependency.
- [ ] **Implement a dbt Jinja preprocessor function**: Create a `_preprocess_dbt_templates(sql_text: str) -> str` function (in `lineage_parser.py` or a new `dbt_preprocessor.py`) that regex-replaces `{{ source('schema', 'table') }}` → `table` (o...
- [ ] **Implement sqlglot-based statement extraction**: Replace the two top-level regexes in `parse_schema()` — the CREATE TABLE regex (`r'CREATE\s+TABLE\s+(\w+)\s*\((.*?)\);'`) and the CREATE VIEW regex (`r'CREATE\s+VIEW\s+(\w+)\s+AS\s+(.*?);(?...
- [ ] **Implement sqlglot-based CREATE TABLE column extraction**: Replace `_parse_table_columns()` regex logic with `sqlglot` AST traversal to extract column names from `CREATE TABLE` statements.
- [ ] **Implement sqlglot-based CREATE VIEW body parsing**: Replace the manual CTE parser (`_parse_ctes`), FROM/JOIN alias extractor (`_extract_from_aliases`), SELECT expression extractor (`_extract_select_expressions`), and column reference res...
- [ ] **Update hardcoded test assertions for known parser limitations**: Update `test_lineage.py::TestBaseTableParsing::test_all_tables_found` (5 → 6 tables, add `nosuchtable`), `test_all_views_found` (5 → 8 views), `TestGraphStructure::test_gra...
- [ ] **Update `static/app.js` `MODEL_LAYERS`**: Add layer assignments for `rpt_customer_growth_cohorts`, `mart_segment_health_snapshot`, `rpt_executive_revenue_dashboard`, and `nosuchtable` so the new models render correctly in the DAG layout.
- [ ] **Add focused sqlglot parser tests**: Add a new test class (or file `tests/test_sqlglot_parser.py`) with tests proving sqlglot handles: (a) nested CTEs (views 6–8), (b) UNION ALL lineage merging (view 4), (c) window functions with PARTITIO...
- [ ] **Add dbt syntax parsing tests**: Add tests proving `{{ source('raw', 'orders') }}` resolves to the correct table reference and `{{ ref('stg_orders_enriched') }}` resolves to the correct view reference.
- [ ] **Add fallback-path tests**: Add tests that feed deliberately malformed SQL (or a dialect sqlglot doesn't support) and verify the regex fallback produces the same output as the current parser.
- [ ] **Run full pytest suite and fix regressions**: Execute `python -m pytest tests/ -v` and fix all failures introduced by the refactor.
- [ ] **Update `README.md`**: Add `sqlglot` to the Setup/Install section, document the new parser capabilities (dbt syntax, all 8 views now parsed), update the test count, and note the sqlglot+regex-fallback architecture under the Parser section.
- [x] create a standalone script for schema.txt file generator.

## History
- 2026-05-24 - Request: Build a column-lineage web app for the SQL models in schema.txt.
- 2026-05-24 - Completed: Build a column-lineage web app for the SQL models in schema.txt.
- 2026-05-24 - Request: Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.
- 2026-05-24 - Request: Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.
- 2026-05-24 - Analyst review: ## Missing Requirements - **Click vs. drag disambiguation**: The title `<text>` element already has a `click` handler for `selectModel` and column texts have `click` for `selectColumn`. The plan does not specify how to distinguish a click (selection) from a drag (reposition). A movement-th...
- 2026-05-24 - Completed: Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.
- 2026-05-24 - Request: Modularize the Flask backend currently concentrated in `app.py` so the backend is easier to maintain and extend.
- 2026-05-24 - Analyst review: Let me examine the current codebase to understand what's in `app.py` and the existing test structure before I can provide a thorough analysis. Now I have a complete picture of the codebase. Let me provide my analysis. --- ## Missing Requirements - **Target module layout is unspecified.** T...
- 2026-05-25 - Request: Modularize the Flask backend currently concentrated in `app.py` so the backend is easier to maintain and extend.
- 2026-05-25 - Analyst review: Let me examine the current codebase to understand the existing structure before providing my analysis. Now let me check how `test_lineage.py` handles imports, and also verify if there's a `conftest.py`: Now I have a complete picture of the codebase. Here is my analysis: --- ## Missing Requ...
- 2026-05-25 - Completed: Modularize the Flask backend currently concentrated in `app.py` so the backend is easier to maintain and extend.
- 2026-05-25 - Completed: **Remove the "Decide on module layout" task** — commit to the flat peer-module approach (`schema_service.py` and `routes.py` as siblings of `app.py`).
- 2026-05-25 - Completed: **Resolve whether the explicit `static_files` route should be kept or dropped** during the Blueprint extraction.
- 2026-05-25 - Completed: **Add a smoke test that `python app.py` still starts the server** (or at minimum, verify the `if __name__ == '__main__'` block is present and `app` is importable from `app.py`).
- 2026-05-25 - Request: Use `sqlglot` when parsing `schema.txt` so SQL DDL and SELECT expressions are parsed more robustly than the current regex-first approach.
- 2026-05-26 - Request: Use `sqlglot` when parsing `schema.txt` so SQL DDL and SELECT expressions are parsed more robustly than the current regex-first approach.
- 2026-05-26 - Analyst review: Let me first examine the existing codebase to understand the current parser, schema, tests, and dependencies before challenging the plan. Now I have a thorough understanding of the codebase. Let me compile my analysis. ## Missing Requirements - **dbt Jinja preprocessing strategy is undefin...
- 2026-05-26 - Request: Use `sqlglot` when parsing `schema.txt` so SQL DDL and SELECT expressions are parsed more robustly than the current regex-first approach.
- 2026-05-26 - Completed: Use `sqlglot` when parsing `schema.txt` so SQL DDL and SELECT expressions are parsed more robustly than the current regex-first approach.
- 2026-05-31 - Request: create a standalone script for schema.txt file generator.
- 2026-05-31 - Completed: create a standalone script for schema.txt file generator.

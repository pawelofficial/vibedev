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
- [ ] Modularize the Flask backend currently concentrated in `app.py` so the backend is easier to maintain and extend.
- [ ] **Decide on module layout**: Choose between flat peer modules (`routes.py`, `schema_service.py` beside `app.py`) or a Flask package directory (`app/` with `__init__.py`).
- [ ] **Extract schema loading into `schema_service.py`**: Move `SCHEMA_PATH` resolution, `parse_schema()` call, and `MODELS`/`GRAPH` computation into a dedicated module with a public `load_schema()` function that returns `(models, graph)` and c...
- [ ] **Extract API route handlers into `routes.py`**: Move the five route handler functions (`index`, `api_graph`, `api_upstream`, `api_downstream`, `api_models`) into a Flask Blueprint in a new `routes.py`.
- [ ] **Reduce `app.py` to an application factory / entry point**: `app.py` should create the `Flask` instance, call `schema_service.load_schema()` (or import the cached globals), register the Blueprint from `routes.py`, and retain the `if __nam...
- [ ] **Update all test imports to use the new module structure**: Update `from app import app` in `test_tester_verification.py` (3 occurrences) and `test_drag_verification.py` (1 occurrence) to import through the new structure.
- [ ] **Run the full pytest suite (`python -m pytest tests/ -v`) and fix any regressions** caused by the refactor.
- [ ] **Update `README.md`**: Revise the "Project Structure" tree diagram to show the new modules.

## History
- 2026-05-24 - Request: Build a column-lineage web app for the SQL models in schema.txt.
- 2026-05-24 - Completed: Build a column-lineage web app for the SQL models in schema.txt.
- 2026-05-24 - Request: Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.
- 2026-05-24 - Request: Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.
- 2026-05-24 - Analyst review: ## Missing Requirements - **Click vs. drag disambiguation**: The title `<text>` element already has a `click` handler for `selectModel` and column texts have `click` for `selectColumn`. The plan does not specify how to distinguish a click (selection) from a drag (reposition). A movement-th...
- 2026-05-24 - Completed: Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.
- 2026-05-24 - Request: Modularize the Flask backend currently concentrated in `app.py` so the backend is easier to maintain and extend.
- 2026-05-24 - Analyst review: Let me examine the current codebase to understand what's in `app.py` and the existing test structure before I can provide a thorough analysis. Now I have a complete picture of the codebase. Let me provide my analysis. --- ## Missing Requirements - **Target module layout is unspecified.** T...

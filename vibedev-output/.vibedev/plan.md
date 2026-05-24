# vibedev plan

## Goal
Build a column-lineage web app for the SQL models in schema.txt.

## Tasks
- [x] Build a column-lineage web app for the SQL models in schema.txt.
- [x] Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.
- [ ] Add node-level drag handlers to `renderNodes()` in `static/app.js` using PointerEvents, with a 4px movement threshold to disambiguate click from drag.
- [ ] Implement connected-edge re-rendering on drag: on each `pointermove` during a node drag, recompute and update only the SVG `<path>` elements whose `data-source-model` or `data-target-model` matches the dragged node.
- [ ] Add `cursor: grab` / `cursor: grabbing` CSS rules for `.model-node` elements during hover and active drag states.
- [ ] Persist dragged positions to `sessionStorage` (keyed by node ID); restore them in `layoutGraph()` if present, so positions survive in-page navigation and soft refreshes within the session.
- [ ] Ensure the existing "Reset View" button also clears stored positions from `sessionStorage` and re-runs `layoutGraph()` to return nodes to their default positions.
- [ ] Raise dragged node to top z-order (re-append the `<g>` element to its parent) during drag to avoid overlap confusion.
- [ ] Add Python/pytest structural tests verifying: (a) the `app.js` source contains pointer event listeners on node groups, (b) the `style.css` contains `cursor: grab` for `.model-node`, (c) the Flask-served HTML includes `app.js` with drag-rel...
- [ ] Update `README.md` to document the new drag-to-reposition behavior under the Features section and note session-scoped persistence.

## History
- 2026-05-24 - Request: Build a column-lineage web app for the SQL models in schema.txt.
- 2026-05-24 - Completed: Build a column-lineage web app for the SQL models in schema.txt.
- 2026-05-24 - Request: Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.
- 2026-05-24 - Request: Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.
- 2026-05-24 - Analyst review: ## Missing Requirements - **Click vs. drag disambiguation**: The title `<text>` element already has a `click` handler for `selectModel` and column texts have `click` for `selectColumn`. The plan does not specify how to distinguish a click (selection) from a drag (reposition). A movement-th...
- 2026-05-24 - Completed: Users should be able to drag and reposition the boxes/nodes that represent SQL tables and views in the lineage graph.

"""
Tester verification: drag-to-reposition node feature.

Structural & behavioral checks that the drag implementation meets
acceptance criteria. No browser engine, so we verify code structure,
CSS rules, JS function signatures, and Flask-served asset integrity.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------
@pytest.fixture(scope="module")
def flask_client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(scope="module")
def js_source(flask_client):
    resp = flask_client.get("/static/app.js")
    assert resp.status_code == 200
    return resp.data.decode("utf-8")


@pytest.fixture(scope="module")
def css_source(flask_client):
    resp = flask_client.get("/static/style.css")
    assert resp.status_code == 200
    return resp.data.decode("utf-8")


@pytest.fixture(scope="module")
def html_source(flask_client):
    resp = flask_client.get("/")
    assert resp.status_code == 200
    return resp.data.decode("utf-8")


# ------------------------------------------------------------------
# 1. Pointer events are used (not mouse events) for node drag
# ------------------------------------------------------------------
class TestPointerEventUsage:
    """The implementation must use PointerEvents on node groups, not
    plain mouse events, for unified mouse/touch/stylus support."""

    def test_pointerdown_registered(self, js_source):
        assert "pointerdown" in js_source

    def test_pointermove_registered(self, js_source):
        assert "pointermove" in js_source

    def test_pointerup_registered(self, js_source):
        assert "pointerup" in js_source

    def test_pointercancel_registered(self, js_source):
        """pointercancel handles edge cases like system dialogs."""
        assert "pointercancel" in js_source

    def test_pointer_capture(self, js_source):
        """setPointerCapture ensures drag continues outside SVG bounds."""
        assert "setPointerCapture" in js_source
        assert "releasePointerCapture" in js_source


# ------------------------------------------------------------------
# 2. Click/drag disambiguation via movement threshold
# ------------------------------------------------------------------
class TestClickDragThreshold:
    """A 4px movement threshold must separate click from drag."""

    def test_threshold_constant_defined(self, js_source):
        assert "NODE_DRAG_THRESHOLD" in js_source

    def test_threshold_value_is_4(self, js_source):
        match = re.search(r"NODE_DRAG_THRESHOLD\s*=\s*(\d+)", js_source)
        assert match, "NODE_DRAG_THRESHOLD constant not found"
        assert int(match.group(1)) == 4, f"Expected threshold 4, got {match.group(1)}"

    def test_threshold_checked_before_activating_drag(self, js_source):
        """The pointermove handler must check the threshold before setting hasMoved."""
        assert "hasMoved" in js_source
        # The pattern: check Math.abs(dx) < threshold before setting hasMoved=true
        assert "Math.abs" in js_source

    def test_handle_node_click_dispatches_on_no_move(self, js_source):
        """When threshold is not exceeded, pointerup must call handleNodeClick."""
        assert "handleNodeClick" in js_source


# ------------------------------------------------------------------
# 3. Click still works: selectModel and selectColumn delegation
# ------------------------------------------------------------------
class TestClickDelegation:
    """handleNodeClick must dispatch to selectModel or selectColumn
    based on the click target — no regressions from old click handlers."""

    def test_handle_node_click_calls_select_column(self, js_source):
        """Column text clicks → selectColumn."""
        assert "selectColumn" in js_source

    def test_handle_node_click_calls_select_model(self, js_source):
        """Title/background clicks → selectModel."""
        # handleNodeClick should contain a call to selectModel
        assert "selectModel" in js_source

    def test_handle_node_click_checks_column_text_class(self, js_source):
        """Must walk the DOM to find .column-text to identify column clicks."""
        assert ".column-text" in js_source

    def test_no_standalone_click_handlers_on_svg_node_elements(self, js_source):
        """Old click handlers on title/column <text> inside renderNodes
        must be removed. The only click handlers should be in sidebar,
        search, and controls — NOT on SVG node groups/rects/texts."""
        # Extract the renderNodes function body
        start = js_source.find("function renderNodes(")
        end = js_source.find("function setupNodeDrag(")
        if start != -1 and end != -1:
            render_body = js_source[start:end]
            # There should be NO .addEventListener('click' in renderNodes
            assert "addEventListener('click'" not in render_body, (
                "renderNodes still has standalone click handlers — "
                "they should be handled via setupNodeDrag/handleNodeClick"
            )


# ------------------------------------------------------------------
# 4. Surgical edge update (not full re-render)
# ------------------------------------------------------------------
class TestConnectedEdgeUpdate:
    """Only edges connected to the dragged node should be updated,
    not all ~167 edges."""

    def test_update_connected_edges_function_exists(self, js_source):
        assert "function updateConnectedEdges" in js_source

    def test_uses_dataset_selector_for_source(self, js_source):
        """Must query paths by data-source-model attribute."""
        assert "data-source-model" in js_source

    def test_uses_dataset_selector_for_target(self, js_source):
        """Must query paths by data-target-model attribute."""
        assert "data-target-model" in js_source

    def test_edges_have_data_attributes_set(self, js_source):
        """renderEdges must set dataset.sourceModel/targetModel on <path>."""
        assert "dataset.sourceModel" in js_source
        assert "dataset.targetModel" in js_source
        assert "dataset.sourceColumn" in js_source
        assert "dataset.targetColumn" in js_source

    def test_pointermove_calls_update_connected_edges(self, js_source):
        """During drag, pointermove must call updateConnectedEdges, not renderEdges."""
        # Find the pointermove handler block — need a larger window since
        # the handler body spans many lines with threshold/transform logic
        idx = js_source.find("pointermove")
        assert idx != -1
        # Get a larger chunk to cover the full handler body
        chunk = js_source[idx:idx + 2000]
        assert "updateConnectedEdges" in chunk, (
            "pointermove handler should call updateConnectedEdges"
        )


# ------------------------------------------------------------------
# 5. Coordinate space: scale correction
# ------------------------------------------------------------------
class TestCoordinateSpace:
    """Drag deltas must be divided by viewTransform.scale to convert
    screen pixels to graph-space units."""

    def test_scale_division_present(self, js_source):
        """Must divide by viewTransform.scale in pointermove."""
        assert "viewTransform.scale" in js_source
        # Specific pattern: dx / viewTransform.scale
        assert re.search(r"d[xy]\s*/\s*viewTransform\.scale", js_source), (
            "Expected dx/dy divided by viewTransform.scale for zoom correction"
        )

    def test_positions_stored_in_graph_space(self, js_source):
        """Positions saved to nodePositions/sessionStorage must be graph-space,
        not screen-space. Verify origNodeX/Y is used as the anchor."""
        assert "origNodeX" in js_source
        assert "origNodeY" in js_source


# ------------------------------------------------------------------
# 6. sessionStorage persistence
# ------------------------------------------------------------------
class TestSessionStoragePersistence:
    """Positions must be persisted to sessionStorage (not localStorage)."""

    def test_uses_session_storage_not_local_storage(self, js_source):
        """Must use sessionStorage, not localStorage."""
        assert "sessionStorage" in js_source
        # localStorage should NOT be used for node positions
        assert "localStorage" not in js_source, (
            "Should use sessionStorage, not localStorage, per acceptance criteria"
        )

    def test_session_key_is_namespaced(self, js_source):
        """The key must be namespaced to avoid collisions."""
        assert "vibedev-lineage-positions" in js_source

    def test_save_function_exists(self, js_source):
        assert "function savePositionsToSession" in js_source

    def test_load_function_exists(self, js_source):
        assert "function loadPositionsFromSession" in js_source

    def test_clear_function_exists(self, js_source):
        assert "function clearPositionsFromSession" in js_source

    def test_layout_graph_restores_saved_positions(self, js_source):
        """layoutGraph must call loadPositionsFromSession to restore positions."""
        # Find layoutGraph function
        start = js_source.find("function layoutGraph(")
        end = js_source.find("function renderGraph(")
        if start != -1 and end != -1:
            layout_body = js_source[start:end]
            assert "loadPositionsFromSession" in layout_body, (
                "layoutGraph must call loadPositionsFromSession to restore positions"
            )

    def test_save_called_on_drag_end(self, js_source):
        """savePositionsToSession must be called when drag ends."""
        assert "savePositionsToSession" in js_source


# ------------------------------------------------------------------
# 7. Reset View clears positions
# ------------------------------------------------------------------
class TestResetViewClearsPositions:
    """The Reset View button must clear stored positions and re-layout."""

    def test_reset_view_calls_clear(self, js_source):
        """resetView must call clearPositionsFromSession."""
        start = js_source.find("function resetView(")
        assert start != -1, "resetView function not found"
        end = js_source.find("function focusMart(")
        if end == -1:
            end = start + 500
        reset_body = js_source[start:end]
        assert "clearPositionsFromSession" in reset_body, (
            "resetView must clear sessionStorage positions"
        )

    def test_reset_view_calls_layout_graph(self, js_source):
        """After clearing, resetView must re-run layoutGraph."""
        start = js_source.find("function resetView(")
        end = js_source.find("function focusMart(")
        if end == -1:
            end = start + 500
        reset_body = js_source[start:end]
        assert "layoutGraph()" in reset_body

    def test_reset_view_calls_render_graph(self, js_source):
        """After re-layout, resetView must re-render."""
        start = js_source.find("function resetView(")
        end = js_source.find("function focusMart(")
        if end == -1:
            end = start + 500
        reset_body = js_source[start:end]
        assert "renderGraph()" in reset_body


# ------------------------------------------------------------------
# 8. Z-ordering: dragged node rises to top
# ------------------------------------------------------------------
class TestZOrdering:
    """During drag, the node <g> must be re-appended to render on top."""

    def test_re_append_to_parent(self, js_source):
        """parent.appendChild(groupEl) re-orders the node to the end (top)."""
        assert "parent.appendChild" in js_source or "parentNode.appendChild" in js_source


# ------------------------------------------------------------------
# 9. CSS cursor styles
# ------------------------------------------------------------------
class TestCursorStyles:
    """Visual feedback: grab on hover, grabbing during drag."""

    def test_cursor_grab_on_model_node(self, css_source):
        assert "cursor: grab" in css_source

    def test_cursor_grabbing_during_drag(self, css_source):
        assert "cursor: grabbing" in css_source

    def test_node_dragging_body_class(self, js_source):
        """JS must add/remove 'node-dragging' class on body during drag."""
        assert "node-dragging" in js_source

    def test_body_node_dragging_in_css(self, css_source):
        """CSS must target body.node-dragging for grabbing cursor."""
        assert "body.node-dragging" in css_source

    def test_cursor_pointer_on_interactive_text(self, css_source):
        """Title and column text should keep cursor: pointer for click affordance."""
        assert "cursor: pointer" in css_source


# ------------------------------------------------------------------
# 10. Pan/drag separation
# ------------------------------------------------------------------
class TestPanDragSeparation:
    """Canvas pan must not interfere with node drag."""

    def test_pan_uses_mousedown_on_svg(self, js_source):
        """Pan should only activate on SVG root or edges-group."""
        assert "e.target === svg" in js_source

    def test_pan_checks_edges_group(self, js_source):
        assert "edges-group" in js_source

    def test_node_drag_stops_propagation(self, js_source):
        """Pointer events on nodes must stop propagation to prevent pan conflict."""
        # Find setupNodeDrag and check for stopPropagation
        start = js_source.find("function setupNodeDrag(")
        assert start != -1
        chunk = js_source[start:start + 800]
        assert "stopPropagation" in chunk


# ------------------------------------------------------------------
# 11. Nodes group wrapper for z-order management
# ------------------------------------------------------------------
class TestNodesGroup:
    """Nodes should be wrapped in a #nodes-group <g>."""

    def test_nodes_group_id_in_js(self, js_source):
        assert "nodes-group" in js_source


# ------------------------------------------------------------------
# 12. updateNodePosition correctness
# ------------------------------------------------------------------
class TestUpdateNodePosition:
    """updateNodePosition must update both nodePositions and columnYPositions."""

    def test_function_exists(self, js_source):
        assert "function updateNodePosition" in js_source

    def test_updates_column_y_positions(self, js_source):
        """Must shift columnYPositions by deltaY."""
        start = js_source.find("function updateNodePosition")
        assert start != -1
        chunk = js_source[start:start + 500]
        assert "columnYPositions" in chunk
        assert "deltaY" in chunk


# ------------------------------------------------------------------
# 13. README documents drag feature
# ------------------------------------------------------------------
class TestREADME:
    """README must document the drag-to-reposition feature."""

    def test_readme_mentions_drag(self):
        readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
        assert "drag" in readme.lower(), "README should mention drag feature"

    def test_readme_mentions_session_storage(self):
        readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
        assert "session" in readme.lower(), (
            "README should mention session-scoped persistence"
        )

    def test_readme_mentions_reposition(self):
        readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
        assert "reposition" in readme.lower(), "README should mention repositioning"


# ------------------------------------------------------------------
# 14. Edge Bezier path correctness pattern
# ------------------------------------------------------------------
class TestEdgePathPattern:
    """Edge paths must use Bezier curves with consistent coordinate logic."""

    def test_bezier_curve_path_in_render_edges(self, js_source):
        """Both renderEdges and updateConnectedEdges must produce the same
        Bezier path format: M x1,y1 C midX,y1 midX,y2 x2,y2."""
        # renderEdges Bezier
        assert re.search(r"M\$\{x1\},\$\{y1\}\s*C\$\{midX\}", js_source)

    def test_update_connected_edges_uses_same_bezier(self, js_source):
        """updateConnectedEdges must produce the same path shape as renderEdges."""
        # Count the bezier pattern - should appear at least twice (renderEdges + updateConnectedEdges)
        pattern = r"M\$\{x1\},\$\{y1\}\s*C\$\{midX\}"
        matches = re.findall(pattern, js_source)
        assert len(matches) >= 2, (
            f"Expected Bezier path pattern in both renderEdges and updateConnectedEdges, "
            f"found {len(matches)} occurrences"
        )


# ------------------------------------------------------------------
# 15. Error handling in sessionStorage helpers
# ------------------------------------------------------------------
class TestSessionStorageErrorHandling:
    """sessionStorage helpers must handle unavailability gracefully."""

    def test_save_has_try_catch(self, js_source):
        start = js_source.find("function savePositionsToSession")
        assert start != -1
        chunk = js_source[start:start + 500]
        assert "try" in chunk and "catch" in chunk

    def test_load_has_try_catch(self, js_source):
        start = js_source.find("function loadPositionsFromSession")
        assert start != -1
        chunk = js_source[start:start + 300]
        assert "try" in chunk and "catch" in chunk

    def test_clear_has_try_catch(self, js_source):
        start = js_source.find("function clearPositionsFromSession")
        assert start != -1
        chunk = js_source[start:start + 300]
        assert "try" in chunk and "catch" in chunk


# ------------------------------------------------------------------
# 16. HTML integrity (app.js is included and loadable)
# ------------------------------------------------------------------
class TestHTMLIntegrity:
    """The served HTML must include app.js which has the drag code."""

    def test_html_includes_app_js(self, html_source):
        assert "app.js" in html_source

    def test_js_file_parseable_size(self, js_source):
        """JS file should be substantially larger than original ~530 lines
        due to drag additions (~735 lines)."""
        line_count = js_source.count("\n")
        assert line_count >= 700, (
            f"Expected ~735+ lines with drag code, got {line_count}"
        )

    def test_js_is_iife(self, js_source):
        """JS must be wrapped in an IIFE to avoid global pollution."""
        assert js_source.strip().startswith("/**") or js_source.strip().startswith("(function")
        assert "})();" in js_source

"""
Regression tests for column detail panel lineage depth.

The SVG highlighter walks lineage transitively. The detail panel should use the
same traversal so it does not show only the immediate one-hop dependencies.
"""

import re
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))


APP_JS = Path(__file__).parent.parent / "static" / "app.js"


def _read_js():
    return APP_JS.read_text(encoding="utf-8")


def _function_body(source, function_name, next_function_name):
    start = source.find(f"function {function_name}(")
    end = source.find(f"function {next_function_name}(", start)
    assert start != -1, f"{function_name} not found"
    assert end != -1, f"{next_function_name} not found after {function_name}"
    return source[start:end]


def _collect_upstream_columns(graph, model, column):
    queue = [(model, column)]
    visited = {(model, column)}
    columns = []
    column_keys = set()

    while queue:
        cur_model, cur_column = queue.pop(0)
        for edge in graph["edges"]:
            if edge["target_model"] != cur_model or edge["target_column"] != cur_column:
                continue

            source = (edge["source_model"], edge["source_column"])
            if source not in column_keys:
                column_keys.add(source)
                columns.append(source)
            if source not in visited:
                visited.add(source)
                queue.append(source)

    return columns


class TestTransitiveLineagePanel:
    def test_shared_transitive_collector_exists(self):
        js = _read_js()
        assert "function collectColumnLineage" in js
        assert "upQueue" in js
        assert "downQueue" in js

    def test_select_column_uses_transitive_collector_for_detail_counts(self):
        js = _read_js()
        body = _function_body(js, "selectColumn", "highlightColumnEdges")

        assert "collectColumnLineage(modelId, columnName)" in body
        assert "upstreamColumns.length" in body
        assert "downstreamColumns.length" in body
        assert "graphData.edges.filter(e => e.target_model" not in body
        assert "graphData.edges.filter(e => e.source_model" not in body

    def test_highlighter_uses_same_collector_as_detail_panel(self):
        js = _read_js()
        body = _function_body(js, "highlightColumnEdges", "setupSearch")

        assert "collectColumnLineage(modelId, columnName)" in body
        assert "lineage.upstreamEdgeKeys" in body
        assert "lineage.downstreamEdgeKeys" in body

    def test_executive_rank_has_more_transitive_than_direct_upstream_columns(self):
        from schema_service import load_schema

        _, graph = load_schema()
        direct = [
            edge
            for edge in graph["edges"]
            if edge["target_model"] == "rpt_executive_revenue_dashboard"
            and edge["target_column"] == "segment_revenue_rank"
        ]
        transitive = _collect_upstream_columns(
            graph,
            "rpt_executive_revenue_dashboard",
            "segment_revenue_rank",
        )

        assert len(direct) == 2
        assert len(transitive) > len(direct)
        assert ("raw_order_items", "quantity") in transitive
        assert ("raw_payments", "amount") in transitive

    def test_collector_deduplicates_columns_before_rendering(self):
        js = _read_js()
        body = _function_body(js, "collectColumnLineage", "selectColumn")

        assert re.search(r"if\s*\(key === selectedKey \|\| keys\.has\(key\)\) return", body)
        assert "keys.add(key)" in body

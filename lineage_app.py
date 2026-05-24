r"""Driver script for the SQL column-lineage app experiment.

Run with:

    python lineage_app.py

Before running, put ``schema.txt`` in the configured workspace directory:

    Copy-Item .\schema.txt .\vibedev-output\schema.txt

This script uses team mode with a business analyst, developer, and tester, all
on Opus 4.6. The main model is also Opus 4.6; in current vibedev team mode it
is used for README update / fallback-manager work while Python owns the
planning and dev-test loop.
"""

import vibedev


# --- configuration -----------------------------------------------------------

vibedev.set_permissions("bypassPermissions")
vibedev.set_model("claude-opus-4-6")
vibedev.set_workspace_root("./vibedev-output")

vibedev.set_team(
    [
        ("business_analyst", "claude-opus-4-6"),
        ("developer", "claude-opus-4-6"),
        ("tester", "claude-opus-4-6"),
    ]
)


# --- run ---------------------------------------------------------------------

STARTUP_PROMPT = """
Build a column-lineage web app for the SQL models in schema.txt.

The file schema.txt is already present in the current workspace. Read it and
build an app that parses the 5 base tables and 5 views, extracts column-level
lineage, and displays the result in an interactive UI.

Core requirements:
- Show SQL tables/views as model nodes.
- Show column-to-column lineage edges.
- Let a user click a model or column to inspect upstream and downstream lineage.
- Make it clear when a column is derived from multiple upstream columns.
- Include a search box for model and column names.
- Include a useful default view for the final mart_customer_ltv_segments model.

Lineage extraction requirements:
- Handle direct passthrough columns.
- Handle aliases and renamed columns.
- Handle casts.
- Handle CASE expressions.
- Handle COALESCE, NULLIF, LOWER, TRIM, UPPER, DATE_TRUNC, and concatenation.
- Handle arithmetic expressions.
- Handle joins across multiple tables.
- Handle CTEs.
- Handle aggregate functions and filtered aggregates.
- Handle UNION ALL.
- Handle window functions.
- Handle views depending on other views.

Implementation guidance:
- Prefer a simple local web app that can be run from the workspace.
- It is fine to implement a pragmatic parser tailored to the provided SQL, but
  keep the design clear enough that more SQL support could be added later.
- Include tests for lineage extraction. At minimum, prove lineage for:
  - mart_customer_ltv_segments.ltv_after_fees_amount
  - mart_customer_ltv_segments.customer_segment
  - fct_customer_revenue_daily.daily_revenue_amount
  - stg_orders_enriched.net_collected_amount
  - stg_line_items_priced.estimated_line_margin
- Update README.md with setup, run, and test instructions.
"""

FEATURE_PROMPT = """
Continue the existing lineage app in this workspace. Do not rebuild it from scratch.
Implement this UI feature:
Users should be able to drag and reposition the boxes/nodes that represent SQL
tables and views in the lineage graph. Currently those nodes are fixed in place.
Requirements:
- Preserve the existing app structure and lineage parsing behavior.
- Make table/view nodes draggable with mouse or pointer interactions.
- Keep lineage edges connected to nodes after they move.
- The moved positions should remain stable during the current browser session.
- Add or update tests where practical for the graph/node positioning behavior.
- Update README.md if the UI behavior or usage instructions change.
"""

FEATURE_PROMPT = """
Continue the existing lineage app in this workspace. Do not rebuild it from scratch.

Implement this refactor:
Modularize the Flask backend currently concentrated in `app.py` so the backend is easier to maintain and extend.

Requirements:
- Preserve all existing user-facing behavior and API responses.
- Split backend responsibilities into focused modules where appropriate, for example app creation/routing, schema loading, graph/model access, and API handlers.
- Keep `app.py` as a small runnable entry point or application factory wrapper.
- Avoid changing frontend behavior unless a backend import path or static-serving detail requires it.
- Update tests where needed so they import the app through the new structure.
- Run the relevant pytest suite and fix regressions caused by the refactor.
- Update `README.md` if setup, run commands, or project structure change.
"""

USER_PROMPT=FEATURE_PROMPT

workspace = vibedev.prompt(
    USER_PROMPT,
    workspace=None,
    quiet=False,
)

print(f"\nvibedev finished. Generated project lives in: {workspace}")

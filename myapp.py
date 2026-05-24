"""Example vibedev driver script.

Run with:  python myapp.py

Tweak the configuration block and the prompt to taste. Each `set_*` call mutates
module-level state for vibedev, so subsequent `prompt()` calls pick it up.
"""

import vibedev

# --- configuration -----------------------------------------------------------

vibedev.set_permissions("bypassPermissions")   # fire-and-forget; agent edits/runs freely
vibedev.set_model("claude-opus-4-7")           # the manager's model (the main agent)
vibedev.set_workspace_root("./vibedev-output") # agent works directly in this dir (created if missing)

# Each team entry is either a bare role name (inherits set_model) or a
# (role, model) tuple for a per-role override. Duplicates are meaningful —
# the two devs become distinct instances (developer / developer-2) that the
# manager can dispatch to in parallel.
vibedev.set_team([
    ("developer", "claude-haiku-4-5"),
    ("developer", "claude-haiku-4-5"),
    ("tester",    "claude-sonnet-4-6"),
])

# --- run ---------------------------------------------------------------------

USER_PROMPT = "build a hello-world flask app that returns JSON from /hello"

workspace = vibedev.prompt(
    USER_PROMPT,
    # workspace=None -> use the configured workspace_root directly
    # workspace="./my-fixed-dir" -> use that dir directly (overrides root)
    workspace=None,
    quiet=False,
)

print(f"\nvibedev finished. Generated project lives in: {workspace}")

"""Example vibedev driver script.

Run with:  python myapp.py

Tweak the configuration block and the prompt to taste. Each `set_*` call mutates
module-level state for vibedev, so subsequent `prompt()` calls pick it up.
"""

import vibedev

# --- configuration -----------------------------------------------------------

vibedev.set_permissions("bypassPermissions")   # fire-and-forget; agent edits/runs freely
vibedev.set_model("claude-haiku-4-5")          # cheapest; bump to claude-sonnet-4-6 or claude-opus-4-7 for harder builds
vibedev.set_workspace_root("./vibedev-output") # agent works directly in this dir (created if missing)

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

"""Command-line entry point: ``vibedev "build a calculator app"``."""

from __future__ import annotations

import argparse
import sys

from vibedev.config import (
    set_common_knowledge,
    set_model,
    set_permissions,
    set_workspace_root,
)
from vibedev.core import prompt as run_prompt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vibedev",
        description="Agentic dev: describe a project, get a project.",
    )
    parser.add_argument("prompt", help="What to build, e.g. 'a calculator web app'.")
    parser.add_argument(
        "--workspace",
        help="Workspace directory for this run (overrides --workspace-root).",
    )
    parser.add_argument("--model", help="Claude model ID to use.")
    parser.add_argument(
        "--permissions",
        choices=["bypassPermissions", "acceptEdits", "default", "plan"],
    )
    parser.add_argument(
        "--workspace-root",
        help="Workspace root directory (default: ./vibedev-output, used directly).",
    )
    parser.add_argument(
        "--no-common-knowledge",
        action="store_true",
        help="Skip generated .vibedev/common_knowledge.md and the knowledge curator.",
    )
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args(argv)

    if args.model:
        set_model(args.model)
    if args.permissions:
        set_permissions(args.permissions)
    if args.workspace_root:
        set_workspace_root(args.workspace_root)
    if args.no_common_knowledge:
        set_common_knowledge(False)

    ws = run_prompt(args.prompt, workspace=args.workspace, quiet=args.quiet)
    print(f"\n[vibedev] done. workspace: {ws}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

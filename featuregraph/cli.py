import sys
import argparse
from pathlib import Path

# Support running as a standalone script or installed module
if __name__ == "__main__" and __package__ is None:
    file_path = Path(__file__).resolve()
    sys.path.insert(0, str(file_path.parent.parent))
    __package__ = "featuregraph"

from featuregraph.core.scanner import WorkspaceScanner
from featuregraph.core.annotator import collect_suggestions, apply_suggestions, _comment_prefix
from featuregraph.formatters.json_formatter import JSONFormatter
from featuregraph.formatters.markdown_formatter import MarkdownFormatter
from featuregraph.formatters.html_visualizer import HTMLVisualizer
from featuregraph.hooks.git_hook import GitHookManager
from featuregraph.skills.skill_manager import SkillManager

# @feature [CLI-01] Main
def main():
    parser = argparse.ArgumentParser(
        prog="featuregraph",
        description="Token-efficient AST-indexed feature topology map for AI coding agents."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: scan
    scan_parser = subparsers.add_parser("scan", help="Scan codebase and generate feature graph files")
    scan_parser.add_argument("--dir", default=".", help="Root directory to scan (default: .)")
    scan_parser.add_argument("--json", default="FEATURE_INDEX.json", help="Output JSON path")
    scan_parser.add_argument("--md", default="SYSTEM_FEATURE_GRAPH.md", help="Output Markdown path")
    scan_parser.add_argument("--html", default=None, help="Optional output interactive HTML path")
    scan_parser.add_argument("--quiet", action="store_true", help="Suppress console output")

    # Command: init
    init_parser = subparsers.add_parser("init", help="Initialize FeatureGraph in current repository with pre-commit hook")

    # Command: query
    query_parser = subparsers.add_parser("query", help="Query a specific feature ID and print its exact line ranges and dependencies")
    query_parser.add_argument("feature_id", help="Feature ID to query (e.g. AUTH-01)")

    # Command: hook
    hook_parser = subparsers.add_parser("hook", help="Install or remove git pre-commit hook")
    hook_parser.add_argument("--install", action="store_true", help="Install git pre-commit hook")
    hook_parser.add_argument("--uninstall", action="store_true", help="Uninstall git pre-commit hook")

    # Command: visualize
    viz_parser = subparsers.add_parser("visualize", help="Generate an interactive HTML dependency graph")
    viz_parser.add_argument("--out", default="featuregraph.html", help="HTML output path")

    # Command: annotate
    ann_parser = subparsers.add_parser(
        "annotate",
        help="Auto-suggest @feature tags for un-annotated symbols (dry-run by default)"
    )
    ann_parser.add_argument("--dir", default=".", help="Root directory to annotate (default: .)")
    ann_parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Preview suggestions without writing to files (default)"
    )
    ann_parser.add_argument(
        "--yes", "-y", action="store_true", default=False,
        help="Write @feature tags to files without prompting"
    )
    ann_parser.add_argument(
        "--limit", type=int, default=0,
        help="Limit suggestions to first N symbols (0 = all)"
    )

    # Command: skill
    skill_parser = subparsers.add_parser(
        "skill",
        help="Install or display the FeatureGraph skill for AI coding agents"
    )
    skill_parser.add_argument("--install", action="store_true", help="Install workspace skill in .agents/skills/featuregraph")
    skill_parser.add_argument("--global", dest="is_global", action="store_true", help="Install globally across agent configs (~/.gemini, ~/.claude, ~/.cursor)")
    skill_parser.add_argument("--show", action="store_true", help="Print SKILL.md definition to stdout")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "scan":
        root = Path(getattr(args, "dir", ".")).resolve()
        quiet = getattr(args, "quiet", False)

        scanner = WorkspaceScanner(root)

        if not quiet:
            subprojects = scanner.detect_subprojects()
            if subprojects:
                print(f"⚡ [FeatureGraph] Multi-Project Workspace detected ({len(subprojects)} projects: {', '.join(subprojects)})")
            print(f"⚡ [FeatureGraph] Scanning codebase in {root}...")

        graph = scanner.scan()
        graph_dict = graph.to_dict()

        json_out = root / getattr(args, "json", "FEATURE_INDEX.json")
        md_out = root / getattr(args, "md", "SYSTEM_FEATURE_GRAPH.md")

        JSONFormatter.write_to_file(graph_dict, json_out, root)
        MarkdownFormatter.write_to_file(graph_dict, md_out, root)

        if getattr(args, "html", None):
            html_out = root / args.html
            HTMLVisualizer.generate(graph_dict, html_out)

        if not quiet:
            print(f"✓ Mapped {len(graph_dict)} features.")
            print(f"✓ Created compact index: {json_out.name}")
            print(f"✓ Created markdown graph: {md_out.name}")

    elif args.command == "init":
        root = Path(".").resolve()
        hook_installed = GitHookManager.install(root)
        if hook_installed:
            print("✓ Installed git pre-commit hook.")
        else:
            print("ℹ Skipped git hook (no .git directory found).")

        scanner = WorkspaceScanner(root)
        graph = scanner.scan()
        graph_dict = graph.to_dict()
        JSONFormatter.write_to_file(graph_dict, root / "FEATURE_INDEX.json", root)
        MarkdownFormatter.write_to_file(graph_dict, root / "SYSTEM_FEATURE_GRAPH.md", root)

        # Generate AGENTS.md Circuit-Breaker Directive
        agents_md = root / "AGENTS.md"
        if not agents_md.exists():
            agents_md.write_text(
                """# AI AGENT SHORT-CIRCUIT CONSTITUTION

> 🛑 **MANDATORY SHORT-CIRCUIT DIRECTIVE:**
> When asked about features, architecture, onboarding, or where code lives:
> **READ `FEATURE_INDEX.json` AND STOP IMMEDIATELY.**
> Do NOT execute recursive ListDir sweeps or multi-file exploratory reads.
> `FEATURE_INDEX.json` is the 100% complete, AST line-indexed single source of truth.
""",
                encoding="utf-8"
            )
            print("✓ Generated AI Agent Constitution: AGENTS.md")

        # Install workspace skill
        skill_file = SkillManager.install_workspace_skill(root)
        print(f"✓ Installed workspace AI agent skill: {skill_file.relative_to(root)}")

        print("✓ Initial graph and circuit-breaker protocol generated successfully.")

    elif args.command == "query":
        import json
        idx_file = Path("FEATURE_INDEX.json")
        if not idx_file.exists():
            print("Error: FEATURE_INDEX.json not found. Run 'featuregraph scan' first.")
            sys.exit(1)
        
        data = json.loads(idx_file.read_text(encoding="utf-8"))
        feat_id = args.feature_id.upper()
        feat = data.get("features", {}).get(feat_id)
        if not feat:
            print(f"Feature '{feat_id}' not found in index.")
            sys.exit(1)

        print(f"\n=======================================================")
        print(f"  FEATURE: [{feat_id}] {feat.get('name', '')}")
        print(f"=======================================================")
        print(f"Description : {feat.get('description', 'N/A')}")
        print(f"Depends On  : {', '.join(feat.get('depends_on', [])) or 'None'}")
        print(f"Called By   : {', '.join(feat.get('called_by', [])) or 'None'}")
        print("\nExact Line Locations:")
        for loc in feat.get("locations", []):
            lines = loc.get("lines") or [loc.get("start_line", 1), loc.get("end_line", 1)]
            print(f"  • {loc['file']} #L{lines[0]}-L{lines[1]} ({loc.get('symbol', 'module')})")
        print("=======================================================\n")

    elif args.command == "hook":
        root = Path(".").resolve()
        if args.uninstall:
            GitHookManager.uninstall(root)
            print("✓ Git pre-commit hook uninstalled.")
        else:
            GitHookManager.install(root)
            print("✓ Git pre-commit hook installed.")

    elif args.command == "visualize":
        root = Path(".").resolve()
        scanner = WorkspaceScanner(root)
        graph = scanner.scan()
        out_path = root / args.out
        HTMLVisualizer.generate(graph.to_dict(), out_path)
        print(f"✓ Generated interactive topology map: {out_path}")

    elif args.command == "annotate":
        root = Path(getattr(args, "dir", ".")).resolve()
        dry_run = getattr(args, "dry_run", True)
        auto_yes = getattr(args, "yes", False)
        limit = getattr(args, "limit", 0)

        print(f"⚡ [FeatureGraph] Scanning for un-annotated symbols in {root}...")
        suggestions = collect_suggestions(root)

        if not suggestions:
            print("✓ All symbols are already annotated — nothing to do.")
            sys.exit(0)

        if limit > 0:
            suggestions = suggestions[:limit]

        # ── Pretty preview ──────────────────────────────────────────────────
        total = len(suggestions)
        files_hit = len({s.file for s in suggestions})
        print(f"\n{'─'*60}")
        print(f"  Found {total} un-annotated symbol(s) across {files_hit} file(s)")
        print(f"{'─'*60}\n")

        current_file = None
        for sg in sorted(suggestions, key=lambda s: (s.file, s.line)):
            rel = sg.file.relative_to(root)
            if sg.file != current_file:
                print(f"  📄 {rel}")
                current_file = sg.file
            prefix = _comment_prefix(sg.lang)
            print(f"      L{sg.line:>4}  {sg.indent}{prefix} @feature [{sg.feature_id}] {sg.name}")

        print(f"\n{'─'*60}")

        # ── Write decision ──────────────────────────────────────────────────
        if dry_run and not auto_yes:
            print("  ℹ  Dry-run mode. Run with --yes to write these tags.")
            print(f"{'─'*60}\n")
            sys.exit(0)

        if not auto_yes:
            try:
                answer = input(f"\n  Write {total} @feature tag(s) to {files_hit} file(s)? [y/N] ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\nAborted.")
                sys.exit(0)
            if answer not in ("y", "yes"):
                print("Aborted.")
                sys.exit(0)

        written = apply_suggestions(suggestions)
        tag_count = sum(written.values())
        print(f"\n✓ Wrote {tag_count} @feature tag(s) across {len(written)} file(s).")
        print("  Run 'featuregraph scan' to rebuild the index.\n")

    elif args.command == "skill":
        root = Path(".").resolve()
        if getattr(args, "show", False):
            print(SkillManager.get_skill_content())
        elif getattr(args, "is_global", False):
            installed = SkillManager.install_global_skills()
            for p in installed:
                print(f"✓ Installed global AI agent skill: {p}")
            if not installed:
                print("ℹ No global skill directories could be written.")
        elif getattr(args, "install", False):
            skill_file = SkillManager.install_workspace_skill(root)
            print(f"✓ Installed workspace AI agent skill: {skill_file}")
        else:
            # Default: install workspace + global
            skill_file = SkillManager.install_workspace_skill(root)
            print(f"✓ Installed workspace AI agent skill: {skill_file}")
            installed = SkillManager.install_global_skills()
            for p in installed:
                print(f"✓ Installed global AI agent skill: {p}")

if __name__ == "__main__":
    main()

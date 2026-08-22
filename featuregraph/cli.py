import sys
import argparse
from pathlib import Path

# Support running as a standalone script or installed module
if __name__ == "__main__" and __package__ is None:
    file_path = Path(__file__).resolve()
    sys.path.insert(0, str(file_path.parent.parent))
    __package__ = "featuregraph"

from featuregraph.core.scanner import WorkspaceScanner
from featuregraph.formatters.json_formatter import JSONFormatter
from featuregraph.formatters.markdown_formatter import MarkdownFormatter
from featuregraph.formatters.html_visualizer import HTMLVisualizer
from featuregraph.hooks.git_hook import GitHookManager

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

    args = parser.parse_args()

    if not args.command or args.command == "scan":
        root = Path(getattr(args, "dir", ".")).resolve()
        quiet = getattr(args, "quiet", False)
        
        if not quiet:
            print(f"⚡ [FeatureGraph] Scanning codebase in {root}...")
            
        scanner = WorkspaceScanner(root)
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
        GitHookManager.install(root)
        print("⚡ [FeatureGraph] Initialized repository & installed git pre-commit hook.")
        
        scanner = WorkspaceScanner(root)
        graph = scanner.scan()
        graph_dict = graph.to_dict()
        JSONFormatter.write_to_file(graph_dict, root / "FEATURE_INDEX.json", root)
        MarkdownFormatter.write_to_file(graph_dict, root / "SYSTEM_FEATURE_GRAPH.md", root)
        print("✓ Initial graph generated successfully.")

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
            print(f"  • {loc['file']} #L{loc['start_line']}-L{loc['end_line']} ({loc.get('symbol', 'module')})")
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

if __name__ == "__main__":
    main()

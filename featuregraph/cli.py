import json
import sys
import argparse
from pathlib import Path

# Support running as a standalone script or installed module
if __name__ == "__main__" and __package__ is None:
    file_path = Path(__file__).resolve()
    sys.path.insert(0, str(file_path.parent.parent))
    __package__ = "featuregraph"

from featuregraph.core.scanner import WorkspaceScanner
from featuregraph.core.dependency_resolver import build_symbol_aliases
from featuregraph.core.annotator import collect_suggestions, apply_suggestions, _comment_prefix
from featuregraph.formatters.json_formatter import JSONFormatter
from featuregraph.formatters.markdown_formatter import MarkdownFormatter
from featuregraph.hooks.git_hook import GitHookManager
from featuregraph.skills.skill_manager import SkillManager


def _guard_fresh(root: Path, index_file: Path, force: bool) -> None:
    """Refuse stale results; the recorded stat fingerprint must match the current tree."""
    if force or not index_file.is_file():
        return
    try:
        meta = json.loads(index_file.read_text(encoding="utf-8")).get("_meta", {})
    except (OSError, ValueError):
        return  # unreadable/legacy artifact; scan will rewrite it
    recorded = meta.get("tree_hash")
    if not recorded:
        return  # ponytail: indexes that predate fingerprints skip the check
    if WorkspaceScanner(root).tree_hash() != recorded:
        print("index is stale (tree changed since scan); run: featuregraph scan", file=sys.stderr)
        sys.exit(1)

def _print_ambiguous(query: str, candidates, as_json: bool):
    if as_json:
        print(json.dumps({
            "error": "ambiguous",
            "query": query,
            "candidates": [
                {"id": symbol_id, "feature_id": feature_id, "file": file_path}
                for symbol_id, feature_id, file_path in candidates
            ],
        }, indent=2))
    else:
        print(f"Ambiguous name '{query}' — {len(candidates)} candidates:")
        for symbol_id, feature_id, file_path in candidates:
            print(f"  {symbol_id} -> {feature_id} ({file_path})")
        print("Use a qualified ID.")
    sys.exit(1)


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
    scan_parser.add_argument("--json", default=None, help="Write an extra copy of the JSON index to this path")
    scan_parser.add_argument("--md", default=None, help="Output Markdown path (default: .featuregraph/graph.md)")
    scan_parser.add_argument("--quiet", action="store_true", help="Suppress console output")

    # Command: init
    subparsers.add_parser("init", help="Initialize FeatureGraph in current repository with pre-commit hook")

    # Command: query
    query_parser = subparsers.add_parser("query", help="Query a feature ID or symbol ID and print its exact line ranges and dependencies")
    query_parser.add_argument("feature_id", help="Feature ID, qualified symbol ID, or unambiguous symbol (e.g. AUTH-01 or web.app.layout)")
    query_parser.add_argument("--dir", default=".", help="Project root containing .featuregraph/ (default: .)")
    query_parser.add_argument("--json", action="store_true", help="Machine-readable JSON output (for agents/CI)")
    query_parser.add_argument("--force", action="store_true", help="Return results even if the tree changed since scan")

    # Command: search
    search_parser = subparsers.add_parser("search", help="Search features by symbol ID, name, or keyword")
    search_parser.add_argument("query", help="Symbol ID, unambiguous symbol, or search terms (e.g. 'web.app.layout', 'parser')")
    search_parser.add_argument("--dir", default=".", help="Project root containing .featuregraph/ (default: .)")
    search_parser.add_argument("--json", action="store_true", help="Machine-readable JSON output (for agents/CI)")
    search_parser.add_argument("--force", action="store_true", help="Return results even if the tree changed since scan")

    # Command: hook
    hook_parser = subparsers.add_parser("hook", help="Install or remove git pre-commit hook")
    hook_parser.add_argument("--install", action="store_true", help="Install git pre-commit hook")
    hook_parser.add_argument("--uninstall", action="store_true", help="Uninstall git pre-commit hook")

    # Command: annotate
    ann_parser = subparsers.add_parser(
        "annotate",
        help="Auto-suggest @feature tags for un-annotated symbols (dry-run by default)"
    )
    ann_parser.add_argument("--dir", default=".", help="Root directory to annotate (default: .)")
    ann_parser.add_argument(
        "--dry-run", action="store_true", default=True,
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

        fg_dir = root / ".featuregraph"
        fg_dir.mkdir(parents=True, exist_ok=True)
        meta = scanner.scan_meta()
        JSONFormatter.write_unindexed(scanner.unindexed, fg_dir)

        JSONFormatter.write_all(graph_dict, fg_dir, root, meta=meta)
        if getattr(args, "json", None):
            JSONFormatter.write_to_file(graph_dict, root / args.json, root, meta=meta)

        md_out = root / args.md if getattr(args, "md", None) else fg_dir / "graph.md"
        MarkdownFormatter.write_to_file(graph_dict, md_out, root)

        if not quiet:
            categories = JSONFormatter.split_by_category(graph_dict)
            if not graph_dict:
                print("⚠ No features found — the index is empty. Add @feature tags or run 'featuregraph annotate'.")
            else:
                print(f"✓ Mapped {len(graph_dict)} features across {len(categories)} domain categories.")
            print("✓ Created 2-Tier Manifest: .featuregraph/manifest.json")
            print(f"✓ Created Category Chunks: .featuregraph/categories/ ({len(categories)} files)")
            print(f"✓ Created markdown graph:  {md_out.relative_to(root) if md_out.is_relative_to(root) else md_out}")

    elif args.command == "init":
        root = Path(".").resolve()
        hook_status = GitHookManager.install(root)
        if hook_status == "installed":
            print("✓ Installed git pre-commit hook.")
        elif hook_status == "foreign-hook":
            print("ℹ Skipped git hook: existing pre-commit hook found (not overwritten).")
        else:
            print("ℹ Skipped git hook (no .git directory found).")

        scanner = WorkspaceScanner(root)
        graph = scanner.scan()
        graph_dict = graph.to_dict()
        meta = scanner.scan_meta()

        fg_dir = root / ".featuregraph"
        fg_dir.mkdir(parents=True, exist_ok=True)
        JSONFormatter.write_all(graph_dict, fg_dir, root, meta=meta)
        JSONFormatter.write_unindexed(scanner.unindexed, fg_dir)
        md_out = fg_dir / "graph.md"
        MarkdownFormatter.write_to_file(graph_dict, md_out, root)

        # Generate or append AGENTS.md Circuit-Breaker Directive
        agents_md = root / "AGENTS.md"
        directive = """# AI AGENT SHORT-CIRCUIT CONSTITUTION

> 🛑 **MANDATORY SHORT-CIRCUIT DIRECTIVE:**
> When asked about features, architecture, onboarding, or where code lives:
> 1. **READ `.featuregraph/manifest.json`** to identify the domain category, feature IDs, and symbol IDs. Symbol IDs are bare when unique and path-qualified on collision (e.g. `web.app.layout` vs `web.app.docs.layout`); an ambiguous bare name exits 1 with candidates.
> 2. **READ `.featuregraph/categories/<category>.json`** to get exact line spans (`#Lstart-Lend`).
> 3. Read **ONLY** the specific lines required for the task.
> 4. If `_meta.status != ok`, do not treat the manifest as complete — fall back to targeted exploration or run `featuregraph annotate`/`scan`.
> 5. If `query` refuses as stale, run `featuregraph scan`.
> Do NOT execute recursive ListDir sweeps or multi-file exploratory reads.
"""
        if not agents_md.exists():
            agents_md.write_text(directive, encoding="utf-8")
            print("✓ Generated AI Agent Constitution: AGENTS.md")
        elif "SHORT-CIRCUIT DIRECTIVE" not in agents_md.read_text(encoding="utf-8", errors="ignore"):
            with open(agents_md, "a", encoding="utf-8") as f:
                f.write("\n" + directive)
            print("✓ Appended Short-Circuit Directive to existing AGENTS.md")

        # Install workspace skill
        skill_file = SkillManager.install_workspace_skill(root)
        print(f"✓ Installed workspace AI agent skill: {skill_file.relative_to(root)}")

        categories = JSONFormatter.split_by_category(graph_dict)
        if not graph_dict:
            print("⚠ No features found — the index is empty. Add @feature tags or run 'featuregraph annotate'.")
        else:
            print(f"✓ Initialized 2-Tier Index: {len(graph_dict)} features in {len(categories)} categories.")

    elif args.command == "query":
        root = Path(args.dir).resolve()
        idx_file = root / ".featuregraph" / "index.json"
        if not idx_file.exists():
            idx_file = root / "FEATURE_INDEX.json"
        if not idx_file.exists():
            print(f"Error: Feature index not found under {root}. Run 'featuregraph scan' first.")
            sys.exit(1)

        _guard_fresh(root, idx_file, args.force)
        data = json.loads(idx_file.read_text(encoding="utf-8"))
        features = data.get("features", {})
        feat_id = args.feature_id.upper()
        feat = features.get(feat_id)
        if not feat:
            by_id, by_symbol = build_symbol_aliases(features)
            target = by_id.get(args.feature_id.casefold())
            if target:
                feat_id = target
                feat = features.get(target)
            else:
                candidates = by_symbol.get(args.feature_id.casefold(), [])
                if len(candidates) > 1:
                    _print_ambiguous(args.feature_id, candidates, args.json)
                if candidates:
                    feat_id = candidates[0][1]
                    feat = features.get(feat_id)
        if not feat:
            print(f"Feature '{args.feature_id.upper()}' not found in index.")
            sys.exit(1)

        if args.json:
            print(json.dumps({"id": feat_id, **feat}, indent=2))
        else:
            print("\n=======================================================")
            print(f"  FEATURE: [{feat_id}] {feat.get('name', '')}")
            print("=======================================================")
            print(f"Description : {feat.get('description', 'N/A')}")
            print(f"Depends On  : {', '.join(feat.get('depends_on', [])) or 'None'}")
            print(f"Called By   : {', '.join(feat.get('called_by', [])) or 'None'}")
            print("\nExact Line Locations:")
            for loc in feat.get("locations", []):
                lines = loc.get("lines") or [loc.get("start_line", 1), loc.get("end_line", 1)]
                print(f"  • {loc['file']} #L{lines[0]}-L{lines[1]} ({loc.get('symbol', 'module')})")
            print("=======================================================\n")

    elif args.command == "search":
        root = Path(args.dir).resolve()
        manifest_file = root / ".featuregraph" / "manifest.json"
        idx_file = root / ".featuregraph" / "index.json"

        if not manifest_file.exists() and not idx_file.exists():
            print(f"Error: No .featuregraph index found under {root}. Run 'featuregraph scan' first.")
            sys.exit(1)

        _guard_fresh(root, idx_file if idx_file.exists() else manifest_file, args.force)
        query_text = args.query
        q_lower = query_text.lower()
        q_words = set(q_lower.split())

        features = {}
        categories = {}
        cats_dir = root / ".featuregraph" / "categories"
        if cats_dir.is_dir():
            for cat_json in cats_dir.glob("*.json"):
                cat_name = cat_json.stem
                cat_data = json.loads(cat_json.read_text(encoding="utf-8"))
                for fid, fmeta in cat_data.items():
                    features[fid] = fmeta
                    categories[fid] = cat_name
        elif idx_file.exists():
            idx_data = json.loads(idx_file.read_text(encoding="utf-8"))
            for fid, fmeta in idx_data.get("features", {}).items():
                features[fid] = fmeta
                categories[fid] = fmeta.get("category", "core")

        matched_features = []
        target = query_text.upper() if query_text.upper() in features else None
        if not target:
            by_id, by_symbol = build_symbol_aliases(features)
            target = by_id.get(query_text.casefold())
            if not target:
                candidates = by_symbol.get(query_text.casefold(), [])
                if len(candidates) > 1:
                    _print_ambiguous(query_text, candidates, args.json)
                if candidates:
                    target = candidates[0][1]

        if target:
            matched_features.append((categories.get(target, "core"), target, features[target]))
        else:
            for fid, fmeta in features.items():
                cat_name = categories.get(fid, fmeta.get("category", "core"))
                name = fmeta.get("name", "").lower()
                desc = fmeta.get("description", "").lower()
                locs = " ".join(loc.get("symbol", "").lower() for loc in fmeta.get("locations", []))
                text = f"{cat_name.lower()} {fid.lower()} {name} {desc} {locs}"
                if any(w in text for w in q_words) or q_lower in text:
                    matched_features.append((cat_name, fid, fmeta))

        if args.json:
            print(json.dumps(
                [{"id": fid, "category": cat, **fmeta} for cat, fid, fmeta in matched_features],
                indent=2,
            ))
        elif matched_features:
            by_cat = {}
            for cat, fid, fmeta in matched_features:
                by_cat.setdefault(cat, []).append((fid, fmeta))
            print(f"\n⚡ [FeatureGraph] Match for '{query_text}':")
            for cat, feats in sorted(by_cat.items()):
                print(f"  Category '{cat}':")
                for fid, fmeta in feats:
                    print(f"    [{fid}] {fmeta.get('name', '')} ({fmeta.get('description', '')})")
                    for loc in fmeta.get("locations", []):
                        lines = loc.get("lines") or [loc.get("start_line", 1), loc.get("end_line", 1)]
                        print(f"      • {loc['file']} #L{lines[0]}-L{lines[1]} ({loc.get('symbol', 'module')})")
            print()
        else:
            print(f"No match for '{query_text}'. Try 'featuregraph scan' or inspect .featuregraph/graph.md.")

    elif args.command == "hook":
        root = Path(".").resolve()
        if args.uninstall:
            if GitHookManager.uninstall(root):
                print("✓ Git pre-commit hook uninstalled.")
            else:
                print("ℹ No featuregraph-managed pre-commit hook found.")
        else:
            status = GitHookManager.install(root)
            if status == "installed":
                print("✓ Git pre-commit hook installed.")
            elif status == "foreign-hook":
                print("ℹ Existing pre-commit hook found — not overwritten.")
            else:
                print("ℹ No .git directory found.")

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

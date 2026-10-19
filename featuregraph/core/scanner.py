import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from .parser_py import PythonFeatureParser
from .parser_ts import TypeScriptFeatureParser
from .parser_generic import GenericFeatureParser
from .dependency_resolver import DependencyResolver
from .graph import FeatureGraph

DEFAULT_IGNORE = {
    "venv", "node_modules", "dist", "build",
    "__pycache__", "logs", "coverage"
}

# @feature [SCANNER-01] Workspace scanner
class WorkspaceScanner:
    """Recursively scans codebase directories and parses feature tags into a FeatureGraph."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.ignore_patterns = set(DEFAULT_IGNORE)
        self._load_ignore_file()

    # @feature [SCANNER-02] Detect subprojects
    def detect_subprojects(self) -> List[str]:
        """Detects if current root is a multi-project workspace containing multiple repositories."""
        subprojects = []
        try:
            for child in self.root_dir.iterdir():
                if child.is_dir() and not self._should_ignore_dir(child.name):
                    if (child / ".git").exists() or (child / "pyproject.toml").exists() or (child / "package.json").exists():
                        subprojects.append(child.name)
        except (PermissionError, OSError):
            pass
        return sorted(subprojects)

    def _load_ignore_file(self):
        ignore_file = self.root_dir / ".featureignore"
        if ignore_file.exists():
            for line in ignore_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.ignore_patterns.add(line.rstrip("/"))

    def _should_ignore_dir(self, dir_name: str) -> bool:
        if dir_name.startswith(".") and dir_name not in [".", ".."]:
            return True
        return dir_name in self.ignore_patterns

    def _git_file_list(self) -> Optional[List[str]]:
        """Tracked + untracked-but-not-ignored files via git, or None when git is unavailable."""
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.root_dir), "ls-files", "-z",
                 "--cached", "--others", "--exclude-standard"],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return [p for p in proc.stdout.split("\0") if p]

    def iter_files(self) -> Iterator[Path]:
        """
        Yields candidate source files. Inside a git repo uses git's file list so
        .gitignore'd trees (vendor, target, .next, …) are never scanned; falls back
        to a filtered os.walk elsewhere. Always honours .featureignore and hidden dirs.
        """
        git_files = self._git_file_list()
        if git_files is not None:
            for rel in sorted(git_files):
                parts = Path(rel).parts
                if any(p.startswith(".") or p in self.ignore_patterns for p in parts[:-1]):
                    continue
                if parts[-1].startswith("."):
                    continue
                path = self.root_dir / rel
                if path.is_file():
                    yield path
            return

        for root, dirs, files in os.walk(self.root_dir, topdown=True):
            dirs[:] = sorted(d for d in dirs if not self._should_ignore_dir(d))
            for file in sorted(files):
                if not file.startswith("."):
                    yield Path(root) / file

    def _source_files(self) -> Iterator[Tuple[Path, Path, os.stat_result]]:
        """Exact file set scan parses: supported, non-empty, selected by iter_files."""
        for path in self.iter_files():
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_size == 0:
                continue  # empty files (e.g. __init__.py) are not "unparsed"
            if not (
                path.suffix == ".py"
                or path.suffix in (".ts", ".tsx", ".js", ".jsx")
                or GenericFeatureParser.is_supported(path)
            ):
                continue
            yield path, path.relative_to(self.root_dir), st

    def tree_hash(self) -> str:
        """sha256 over sorted (relpath, size, mtime_ns); .featuregraph is hidden, so iter_files skips it."""
        h = hashlib.sha256()
        for _, rel_path, st in sorted(self._source_files(), key=lambda f: f[1].as_posix()):
            h.update(f"{rel_path.as_posix()}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())
        return h.hexdigest()

    # @feature [SCANNER-03] Scan
    def scan(self) -> FeatureGraph:
        graph = FeatureGraph()
        resolver = DependencyResolver()

        # Pass 1: Parse all files & index defined symbols
        scanned_files = []
        unparsed: List[str] = []
        hasher = hashlib.sha256()
        total_files = 0

        for path, rel_path, st in sorted(self._source_files(), key=lambda f: f[1].as_posix()):
            total_files += 1
            hasher.update(f"{rel_path.as_posix()}\0{st.st_size}\0{st.st_mtime_ns}\n".encode())

            if path.suffix == ".py":
                parsed = PythonFeatureParser.parse_file(path)
            elif path.suffix in [".ts", ".tsx", ".js", ".jsx"]:
                parsed = TypeScriptFeatureParser.parse_file(path)
            else:
                parsed = GenericFeatureParser.parse_file(path)

            if parsed:
                for item in parsed:
                    item["rel_path"] = rel_path.as_posix()
                scanned_files.append((path, rel_path, parsed))
            else:
                unparsed.append(str(rel_path))

        if unparsed:
            sample = ", ".join(unparsed[:3])
            suffix = f" (+{len(unparsed) - 3} more)" if len(unparsed) > 3 else ""
            print(
                f"⚠ {len(unparsed)} file(s) with no parseable features (untagged or syntax error): {sample}{suffix}",
                file=sys.stderr,
            )

        # Pass 2: Infer cross-feature dependencies & populate graph
        all_features = [item for _, _, parsed in scanned_files for item in parsed]
        resolver.register_feature_symbols(all_features)

        for path, rel_path, parsed in scanned_files:
            inferred_deps = resolver.resolve_file_dependencies(path, parsed)

            for item in parsed:
                feat_id = item["feature_id"]
                auto_deps = inferred_deps.get(feat_id, set())
                manual_deps = set(item.get("depends_on", []))
                all_deps = sorted(list(manual_deps | auto_deps))

                item_loc = [{
                    "file": str(rel_path),
                    "lines": [item["start_line"], item["end_line"]],
                    "symbol": item["symbol"],
                    "symbol_id": item.get("symbol_id", item["symbol"]),
                    "type": item["type"],
                }]
                graph.add_feature(feat_id, {
                    "name": item["name"],
                    "depends_on": all_deps,
                    "locations": item_loc
                })

        # Explicit @depends tags may point at features that do not exist (typo, rename, deletion).
        # Inferred deps can't dangle — the resolver only knows registered feature IDs.
        unresolved = sorted({
            (feat_id, dep)
            for feat_id, deps in graph.edges.items()
            for dep in deps
            if dep not in graph.nodes
        })
        if unresolved:
            sample = ", ".join(f"{feat} → {dep}" for feat, dep in unresolved[:3])
            suffix = "…" if len(unresolved) > 3 else ""
            print(
                f"⚠ {len(unresolved)} unresolved @depends reference(s) — no such feature: {sample}{suffix}",
                file=sys.stderr,
            )

        # B4: truthful manifest fields; empty wins regardless of file counts.
        self.tree_hash_value = hasher.hexdigest()
        self.total_files = total_files
        self.indexed_files = len(scanned_files)
        self.unindexed = sorted(unparsed)
        self.status = (
            "empty" if not graph.nodes else "ok" if not unparsed else "partial"
        )

        return graph

    def scan_meta(self) -> dict:
        return {
            "tree_hash": self.tree_hash_value,
            "status": self.status,
            "total_files": self.total_files,
            "indexed_files": self.indexed_files,
            "unindexed_files": len(self.unindexed),
        }


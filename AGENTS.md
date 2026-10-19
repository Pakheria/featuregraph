# FeatureGraph Agent Notes

> 🛑 **MANDATORY SHORT-CIRCUIT DIRECTIVE:**
> When asked about features, architecture, onboarding, or where code lives:
> 1. **READ `.featuregraph/manifest.json`** to identify the domain category, feature IDs, and symbol IDs. Symbol IDs are bare when unique and path-qualified on collision; an ambiguous bare name exits 1 with candidates.
> 2. **READ `.featuregraph/categories/<category>.json`** to get exact line spans (`#Lstart-Lend`).
> 3. Read **ONLY** the specific lines required for the task.
> 4. If `_meta.status != ok`, do not treat the manifest as complete — fall back to targeted exploration or run `featuregraph annotate`/`scan`.
> 5. `_meta.file_level_files` counts files indexed only at file granularity (data/shell/config or no named symbols); query them by `FILE-...` ID.
> 6. If `query` refuses as stale, run `featuregraph scan`.
> Do NOT execute recursive ListDir sweeps or multi-file exploratory reads.

## Project Conventions

- Tests: `python -m pytest -q`; lint: `ruff check featuregraph`.
- Keep `@feature` tags on public behavior; untagged `.js` files get auto `CJS-...` coverage and symbol-less files get `FILE-...` coverage.
- Regenerate and commit `.featuregraph/` after changing tagged source.
- Do not qualify `CJS-...`/`FILE-...` entries for dependency inference; they are coverage entries, not call-graph nodes.

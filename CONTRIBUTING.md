## Contributing to ConsciousDB Sidecar

Thank you for your interest in contributing! This project treats the vector database itself as the model ("database-as-model"). Contributions should preserve transparency, auditability, and low operational overhead.

### Quick Start
```bash
python -m venv .venv
. .venv/Scripts/activate  # PowerShell: . .\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest -q
```

### Development Workflow
1. Fork & branch: `feat/<short-topic>` or `fix/<issue-id>`.
2. Add/adjust tests (prefer test-first for bug fixes & public behavior changes).
3. Run lint & type checks locally (will be enforced in CI):
   ```bash
   ruff check .
   mypy consciousdb-sidecar
   pytest --cov=consciousdb-sidecar
   ```
4. (First time) install git hooks: `pre-commit install` (auto lint/format/safety on commit)
4. Update `CHANGELOG.md` under `Unreleased` with a concise entry (Added / Changed / Fixed / Removed).
5. Submit PR with template sections completed.

### Style & Standards
- **Python Version**: 3.11+
- **Lint**: Ruff (configured in `pyproject.toml`). Keep PRs lint-clean.
- **Formatting**: Ruff’s implied style; avoid massive unrelated reformatting.
- **Types**: Gradually increase coverage. New/modified functions should include type hints.
- **Logging**: Use structured logging (dict-like extra fields); avoid print.
- **Tests**: Use `pytest`. Keep them fast (unit/integration < ~5s). Avoid external network calls.

### Commit Guidelines
- Use conventional-ish prefixes for readability: `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`, `test:`, `build:`, `ci:`.
- Keep first line ≤ 72 chars; add detail below if needed.

### Branch Protection Expectations
PR must:
- Pass CI (lint, types, tests, coverage threshold).
- Contain test updates for changed logic.
- Update CHANGELOG if user-facing.
- Avoid lowering coverage materially without justification.

### Security / Sensitive Data
- Do not log API keys or raw customer content.
- Adaptive state must remain metadata-only (no raw document text).

### Performance Considerations
- Provide micro-benchmark or rationale when changing solver, ranking, or graph construction.
- Keep default dependency footprint minimal (optional extras for connectors/embedders).

### Release Process (Planned)
- Tag `vX.Y.Z` → CI builds sdist/wheel & container → GitHub Release notes auto-generated from CHANGELOG.

### Questions / Discussion
Open a GitHub Discussion or issue; for architectural shifts propose an RFC (markdown doc) summarizing motivation & alternatives.

Thanks for helping build a model-free, transparent retrieval coherence layer!

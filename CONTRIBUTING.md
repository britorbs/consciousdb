## Contributing to ConsciousDB

Thank you for your interest in contributing! This project treats your existing vector database as the model via a convex coherence optimization. High signal, well‑scoped contributions keep iteration velocity high while preserving mathematical and operational integrity.

### Development Setup
1. Clone & create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate  # PowerShell: . .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .[dev]
```
2. (Optional) Install extras for connectors / embedders:
```bash
pip install -e .[embedders-sentencetransformers,connectors-pinecone,connectors-chroma]
```
3. Run the API (mock connector):
```bash
export USE_MOCK=true
uvicorn api.main:app --reload --port 8080
```

### Running Tests & Coverage
We enforce 85% line coverage (CI fails below threshold).
```bash
pytest -q --cov=. --cov-report=term --cov-report=xml
```
Upload to Codecov locally (optional) with:
```bash
bash <(curl -s https://codecov.io/bash) -f coverage.xml || true
```

### Linting & Type Checks
```bash
ruff check .
mypy .
```
Run these before pushing; the CI pipeline runs ruff + mypy + tests + coverage.

### Pull Request Guidelines
1. Create a descriptive branch name: `feature/<short-desc>` or `fix/<issue-id>`.
2. Keep PRs small & focused (prefer <500 LOC diff excluding generated / tests).
3. Include / update tests for new logic (happy path + at least one edge case).
4. Update relevant docs (`docs/ALGORITHM.md`, `RECEIPTS.md`, `API.md`) if schema or math changes.
5. Avoid premature abstractions—optimize for clarity over cleverness.
6. Do not introduce new heavy dependencies without discussion (open an issue first).
7. Add structured logs instead of ad-hoc prints; keep receipt schema additions backwards-compatible.

### Commit Message Style
Use conventional-ish prefixes:
`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `perf:`, `build:`, `chore:`.

Example:
```
feat: add MS MARCO dataset loader with caching layer
```

### Architectural Notes
Core loop: embed -> recall -> local graph -> SPD solve (CG) -> per-node ΔH attribution -> rank -> receipt.
Per-node energy terms must sum (within FP tolerance) to `deltaH_total` and align with `deltaH_trace`.
Any solver changes must maintain symmetry & positive definiteness of the system matrix.

### Filing Issues
Provide: purpose, minimal reproduction (if bug), expected vs actual behavior, environment (OS, Python, connector). Label clearly (`bug`, `enhancement`, `docs`).

### Security
Report vulnerabilities privately first (open a security advisory or email the maintainer). Avoid creating PoC exploit PRs without coordination.

### License & CLA
Code is under BSL 1.1 with future conversion to Apache 2.0. Submitting a PR implies you have the right to contribute under that license; no separate CLA currently required.

### Thank You
Your contributions help push an explainable, physics-inspired alternative to opaque rerankers. 🚀
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

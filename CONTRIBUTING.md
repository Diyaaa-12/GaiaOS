# Contributing to GaiaOS

Thank you for contributing. This project is built one milestone at a time — see `docs/Roadmap_Phase1.md` for the current scope.

## Branching Convention

- **`main`** — stable branch; always reflects the latest completed milestone.
- **`feature/<milestone-name>`** — one branch per milestone (e.g. `feature/milestone-1-repo-setup`, `feature/milestone-2-project-structure`).

Workflow:

1. Branch from `main`: `git checkout -b feature/milestone-N-short-name`
2. Implement only the current milestone's deliverables.
3. Open a pull request into `main` when acceptance criteria are met.
4. Do not start the next milestone until the current one is merged.

## Development Setup

Follow the setup steps in [README.md](README.md). A fresh clone must produce a working virtual environment with no undocumented steps.

## Scope Discipline

- Implement only what the active milestone lists under **Deliverables**.
- Do not add code, folders, or dependencies from later milestones.
- The frozen architecture lives in `docs/Architecture.md` — do not modify it.
- Phase 1 roadmap details live in `docs/Roadmap_Phase1.md`.

## Python Version

Python **3.12** is required. The version is pinned in `.python-version` and enforced in `pyproject.toml` via `requires-python`.

## Dependency Management

This project uses **pip + venv** with split requirement files:

- `requirements/base.txt` — runtime dependencies
- `requirements/dev.txt` — development dependencies (includes base via `-r base.txt`)

Install development dependencies after activating your virtual environment:

```bash
pip install -r requirements/dev.txt
```

## Commits

Write clear, focused commit messages that describe *why* the change was made, not just what changed. Keep each commit scoped to the milestone you are working on.

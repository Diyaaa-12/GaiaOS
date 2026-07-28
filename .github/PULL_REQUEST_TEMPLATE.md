## Description

Briefly describe the purpose of this PR, the changes introduced, and the rationale behind them.

- **Milestone Reference**: Closes # / Relates to Milestone: `[Milestone Name/Number]`

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Open Source / Governance / Documentation update
- [ ] Performance / Refactoring / CI improvement

## Engineering Checklist

### Testing & Verification
- [ ] Unit & integration tests added or updated (`pytest` passes cleanly)
- [ ] All new logic has negative/failure path coverage
- [ ] Verification commands run locally with clean output

### Documentation
- [ ] Architectural docs, README, or per-milestone `docs/` updated if affected
- [ ] Inline docstrings and type annotations added for new public APIs
- [ ] `CONTRIBUTING.md` / `CONTRIBUTING_AGENTS.md` guidelines followed

### Security
- [ ] No secrets, tokens, or private credentials committed
- [ ] Input validation, error sanitization, and prompt-injection defenses maintained
- [ ] No raw SQL queries or unvalidated user input evaluation

### Breaking Changes & API Consistency
- [ ] No breaking changes to existing REST endpoints (`/api/v1`) without versioning
- [ ] OpenAPI spec regenerated if endpoints changed (`python scripts/generate_openapi_spec.py`)
- [ ] `docs/api/CHANGELOG.md` updated for any API surface additions

### DevOps & Continuous Integration
- [ ] Docker container builds verified (`Dockerfile`, `Dockerfile.worker`, etc.)
- [ ] CI workflow (`.github/workflows/ci.yml`) passes cleanly
- [ ] Dependencies added to lockfiles (`requirements/*.lock`) if updated

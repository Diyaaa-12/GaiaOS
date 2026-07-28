# First Pull Request (PR) Contribution Walkthrough

[Documentation Hub](../README.md) | [Environment Setup](ENVIRONMENT_SETUP.md) | [Project Structure](PROJECT_STRUCTURE.md) | [How-To Guides](HOW_TO_GUIDES.md)

---

Welcome to GaiaOS! This end-to-end guide walks first-time contributors through every step of making their very first contribution — from finding a suitable issue to submitting a Pull Request and passing CI.

---

## Step 1: Find a Suitable Issue

Browse open issues in our GitHub tracker:
- **[`good first issue`](https://github.com/Diyaaa-12/GaiaOS/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)**: Small, self-contained tasks designed for first-time contributors.
- **[`help wanted`](https://github.com/Diyaaa-12/GaiaOS/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22)**: Open tasks where community assistance is actively sought.

Comment on the issue to let maintainers know you would like to work on it!

---

## Step 2: Fork & Clone the Repository

1. Click the **Fork** button at the top right of the [GaiaOS repository page](https://github.com/Diyaaa-12/GaiaOS).
2. Clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/GaiaOS.git
   cd GaiaOS
   ```
3. Set up the upstream remote:
   ```bash
   git remote add upstream https://github.com/Diyaaa-12/GaiaOS.git
   ```

---

## Step 3: Set Up Your Development Environment

Configure your local Python 3.12 virtual environment, install pinned dependencies (`requirements/dev.lock`), copy environment configurations, and spin up PostgreSQL and Redis infrastructure containers by following the **[Environment Setup Guide](ENVIRONMENT_SETUP.md)**.


---

## Step 4: Create a Feature Branch

Always create a new branch off the latest `main` branch before making changes:

```bash
git checkout main
git pull upstream main
git checkout -b feature/short-descriptive-name
```

Use descriptive branch names, such as `feature/add-wind-speed-tool` or `fix/jwt-expiration-handling`.

---

## Step 5: Implement Changes & Write Tests

1. Refer to the [Project Structure Guide](PROJECT_STRUCTURE.md) to locate where your changes belong.
2. Follow our [How-To Guides](HOW_TO_GUIDES.md) when adding new agents, API endpoints, database models, or tests.
3. Write matching unit or integration tests under `tests/` for all new code paths.

---

## Step 6: Run Local Verification

Before committing, run full local verification to ensure your changes satisfy all quality gates:

```bash
python scripts/verify.py
```

Or run individual verification commands:
```bash
ruff check .
mypy .
pytest
python scripts/generate_openapi_spec.py
```

---

## Step 7: Commit & Push Changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "feat(api): add health check latency metrics endpoint"
git push origin feature/short-descriptive-name
```

---

## Step 8: Open a Pull Request

1. Navigate to your fork on GitHub.
2. Click **Compare & pull request** next to your branch.
3. Complete the [Pull Request Template](../../.github/PULL_REQUEST_TEMPLATE.md):
   - Link the relevant issue (e.g. `Fixes #123`).
   - Describe the changes made and the motivation behind them.
   - Confirm that local verification passed.
4. Submit the PR targeting the `main` branch of `Diyaaa-12/GaiaOS`.

---

## Step 9: Pass CI & Respond to Review Feedback

- **Continuous Integration**: GitHub Actions will automatically run the CI pipeline (`.github/workflows/ci.yml`). Ensure all checks pass (green checkmark).
- **Code Review**: Maintainers may request minor tweaks or clarifying questions. Address feedback by pushing additional commits to your branch — the PR will update automatically.

Congratulations on making your contribution to GaiaOS! 🎉


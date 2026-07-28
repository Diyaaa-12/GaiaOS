# GaiaOS Support & Community Guidelines

Welcome to the GaiaOS community! We want to ensure you have a clear, welcoming, and effective experience when asking questions, getting support, reporting bugs, or contributing.

---

## 1. Where to Get Help

| Question / Need | Recommended Channel | Details |
| --------------- | ------------------- | ------- |
| **General Usage & Q&A** | [GitHub Issues](https://github.com/Diyaaa-12/GaiaOS/issues) | Submit how-to questions, discuss architectural ideas, or ask for guidance. |
| **Bug Reports** | [GitHub Issues (Bug Report)](https://github.com/Diyaaa-12/GaiaOS/issues/new?template=bug_report.yml) | Report reproducible bugs, unexpected errors, or system regressions. |
| **Feature Requests** | [GitHub Issues (Feature Request)](https://github.com/Diyaaa-12/GaiaOS/issues/new?template=feature_request.yml) | Propose new agent capabilities, architectural enhancements, or platform tools. |
| **Security Vulnerabilities** | [GitHub Private Vulnerability Reporting](https://github.com/Diyaaa-12/GaiaOS/security/advisories/new) | **Do NOT open public issues for security bugs.** See [`SECURITY.md`](SECURITY.md). |
| **Code of Conduct Reports** | Private Maintainer Communication | Report harassment or unacceptable behavior per [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). |

---

## 2. Finding Issues to Work On

If you are a first-time contributor looking to get involved, explore the issue tracker for the following labels:

- **`good first issue`**: Well-defined, self-contained issues specifically suitable for first-time contributors.
- **`help wanted`**: Open tasks where community contributions and assistance are actively welcomed.
- **`area/agent`**: Tasks related to domain risk agents (seismic, atmosphere, ocean, wildfire, air quality, RAG, causal chain, simulation).
- **`area/gateway`**: Tasks related to FastAPI endpoints, middleware, authentication, or rate limiting.
- **`area/ops`**: Tasks related to Docker Compose, Redis, RQ background workers, disaster recovery, or alerting.
- **`area/eval`**: Tasks related to evaluation harness benchmarks and metrics.

For specific guidelines on contributing new domain risk agents, read the [Domain Agent Contribution Guide](docs/CONTRIBUTING_AGENTS.md).

---

## 3. Label Taxonomy

GaiaOS uses standard issue and pull request labels to organize community contributions:

| Label | Description |
| ----- | ----------- |
| `good first issue` | Good for newcomers; small scope and clear acceptance criteria. |
| `help wanted` | Extra attention or community contribution requested. |
| `bug` | Confirmed bug or unexpected system behavior. |
| `enhancement` | New feature, performance improvement, or capability addition. |
| `documentation` | Improvements to guides, README, API docs, or code comments. |
| `security` | Security hardening, dependency vulnerabilities, or security policies. |
| `triage` | Newly submitted issue awaiting maintainer review. |

---

## 4. Response Expectations

Maintainers review incoming issues, security reports, and pull requests on a best-effort basis as time permits.

Please remain respectful and constructive in all community interactions, as outlined in our [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

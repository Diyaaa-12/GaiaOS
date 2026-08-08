# GaiaOS CLI Wizard (`gaiaos-cli`)

Official Command-Line Interface for the **GaiaOS Agentic Planetary Risk Intelligence Platform**.

## Installation

Install `gaiaos-cli` from the local workspace:

```bash
pip install -e cli/
```

Or directly from PyPI (when published):

```bash
pip install gaiaos-cli
```

## Quick Start & Core Commands

### 1. Authentication & Credentials

Log in to a GaiaOS server instance and persist your Bearer token locally:

```bash
gaiaos auth login
```

Check authentication status:

```bash
gaiaos auth status
```

Log out and clear saved credentials:

```bash
gaiaos auth logout
```

### 2. Planetary Risk Investigations

Submit a new investigation and stream real-time execution events:

```bash
gaiaos investigate "Assess seismic and ocean anomaly correlation in the Pacific Rim" --stream
```

Fetch status and findings for an existing investigation:

```bash
gaiaos investigate get <investigation_id>
```

Fetch node/edge execution graph for a trace:

```bash
gaiaos investigate trace <investigation_id>
```

### 3. Plugin Agent Scaffolding

Scaffold a new domain agent plugin directory, implementation, and test suite:

```bash
gaiaos plugin scaffold hydrology
```

### 4. Admin API Key Management

Generate a new API key:

```bash
gaiaos admin api-keys create --name "CI Production Key"
```

List active API keys:

```bash
gaiaos admin api-keys list
```

Revoke an API key:

```bash
gaiaos admin api-keys revoke <key_id>
```

### 5. Version & Server Compatibility

Show CLI version and validate target server compatibility:

```bash
gaiaos version
```

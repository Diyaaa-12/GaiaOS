# GaiaOS Phase 4 — Milestone 2: Security Review & Authentication Hardening

## 1. Overview
Milestone 2 performs a formal security review and hardening of the authentication package (`auth/email_service.py`, `auth/password_hashing.py`, `app/api/v1/auth.py`), addressing unreviewed extensions identified during prior audits before building administrative dashboard capabilities on top of identity management.

---

## 2. Implemented Security Controls

### 2.1 Password Reset Protocol
- **Persistence:** Created the `password_reset_tokens` table (`0015_password_reset_tokens.py`) mapping user IDs to SHA-256 token digests (`hashed_token`).
- **Token Entropy:** Raw tokens generated via `secrets.token_urlsafe(32)` (256-bit cryptographic entropy). Raw tokens are never stored in the database.
- **Single-Use Enforcement:** `used_at` timestamp is set upon consumption. Attempting to reuse a consumed token yields HTTP 400 (`invalid_or_expired_token`).
- **Time-Bound Expiry:** Reset tokens expire after a configurable validity window (`Settings.password_reset_expiry_minutes`, default 15 minutes).
- **Global Token Invalidation on Password Update:** Resetting a password automatically marks **all** active reset tokens for that `user_id` as used (`used_at = now()`), ensuring previously requested links cannot be replayed.

---

### 2.2 Host-Header Injection Immunity
Generated reset link URLs strictly consume `Settings.app_base_url` (configured via environment variable `APP_BASE_URL`). The incoming HTTP `Host` header is ignored during URL construction, preventing password reset link poisoning attacks.

---

### 2.3 Account Non-Enumeration Protection
- `POST /api/v1/auth/request-reset` returns HTTP 202 Accepted with identical generic message (`"If an account with this email exists, a password reset link has been sent."`) regardless of account existence.
- Non-existent account requests execute dummy token generation and SHA-256 hashing to equalize execution latency without artificial `sleep()` calls.

---

### 2.4 Dedicated Rate Limiting Scope
- Integrated a dedicated `password_reset` rate limiter scope in `RedisRateLimiter` targeting `/api/v1/auth/request-reset`.
- Configured via explicit settings (`PASSWORD_RESET_RATE_LIMIT_REQUESTS=3`, `PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS=900`). Requests exceeding the quota return HTTP 429 Too Many Requests.

---

### 2.5 Sanitized Telemetry & Logging
- Zero raw tokens or token previews are logged.
- Log context is strictly restricted to `user_id`, `email`, or request identifiers.

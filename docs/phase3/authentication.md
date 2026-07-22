# GaiaOS Phase 3 — Authentication & Authorization Architecture

## Overview

Milestone 1 introduces identity, authentication, user lifecycle management, and role-based authorization to GaiaOS while preserving the Gateway abstraction (`AuthProvider` Protocol).

---

## 1. Identity & Data Model

User records are persisted in the `users` table:
- **`id`**: Unique UUID primary key.
- **`email`**: User email address (unique index, lowercased).
- **`hashed_password`**: Argon2id password hash.
- **`role`**: Role string (`user`, `researcher`, `admin`).
- **`is_active`**: Lifecycle flag. Inactive users are rejected at authentication time.
- **`is_verified`**: Email verification flag. Unverified accounts cannot log in.
- **`hashed_verification_token`**: SHA-256 hash of the URL verification token. Plaintext tokens are never stored.
- **`verification_token_expires_at`**: 24-hour expiration window.
- **`last_login_at`**: Timestamp of last successful login.
- **`deleted_at`**: Soft-delete timestamp.
- **`investigations.user_id`**: Foreign key pointing to `users.id` with `ON DELETE RESTRICT`.

---

## 2. JWT Claim Schema

Issued access tokens use `HS256` (configurable via `JWT_ALGORITHM`) with the following claim payload:

| Claim | Type | Description | Example |
|---|---|---|---|
| `sub` | string | Subject User UUID | `"c2b4d8a1-1234-4567-89ab-cdef01234567"` |
| `role` | string | User access role | `"user"` / `"researcher"` / `"admin"` |
| `iat` | integer | Issued at timestamp (UTC seconds) | `1784764800` |
| `exp` | integer | Expiration timestamp (UTC seconds) | `1784768400` |
| `iss` | string | Issuer claim | `"gaiaos"` |
| `aud` | string | Audience claim | `"gaiaos-api"` |

Decoders explicitly validate signature, expiration, `iss`, and `aud`.

---

## 3. Email Verification Flow

1. **Registration** (`POST /api/v1/auth/register`):
   - Validates password against policy (min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char).
   - Returns `409 Conflict` if email already exists.
   - Generates secure random token `raw_token`.
   - Stores `SHA-256(raw_token)` in `users.hashed_verification_token`.
   - Dispatches verification URL via `DevEmailService` log delivery.
2. **Verification** (`GET /api/v1/auth/verify-email?token=...`):
   - Computes `SHA-256(input_token)` and looks up matching user.
   - Verifies expiration window.
   - Updates `is_verified = True` and clears verification token fields.

---

## 4. Administrative Bootstrap

Initial administrator accounts are created out-of-band via `tools/create_admin.py` to prevent "first user wins" auto-promotion vulnerabilities:

```bash
python tools/create_admin.py --email admin@gaiaos.ai --password 'AdminSecureP@ss1' --full-name 'System Administrator'
```

---

## 5. Gateway Seam & Security

- `JWTAuthProvider` implements `gateway.auth_stub.AuthProvider` protocol.
- Gateway middleware intercepts incoming requests without inspecting JWT payload internals.
- No passwords, JWT secrets, or tokens are ever logged.
- Failed authentications return generic client responses server-side.

# GaiaOS Phase 3 — Milestone 2: Real Rate Limiting

**Status:** Implemented and Verified  
**Package:** `gateway/rate_limiter_redis.py`  
**Protocol:** Satisfies `gateway.rate_limit_stub.RateLimiter` (`async def check(request: Request) -> None`)

---

## 1. Architectural Summary

Phase 3 Milestone 2 replaces the no-op `RateLimitStub` with `RedisRateLimiter`, a high-performance token-bucket rate limiter. 

Rate limiting is enforced at the `GatewayMiddleware` layer before request dispatch, protecting submission endpoints (`POST /api/v1/investigations`) and auth routes from flood abuse.

---

## 2. Key Technical Features

### Token Bucket Algorithm (Redis Lua Script)
- Rate limiting uses an atomic Lua script (`TOKEN_BUCKET_LUA`) executed in Redis via `EVALSHA` (with `EVAL` fallback).
- Performs token replenishment, cost deduction, and expiry calculation atomically in a single Redis transaction.
- Sets an explicit TTL on Redis rate-limit keys equal to full bucket replenishment duration, preventing stale key buildup.

### Identity & Role Quotas
- **Authenticated Requests:** Uses `user:<user_id>` derived from `request.state.user.id`.
- **Unauthenticated Requests:** Uses `ip:<client_ip>` derived from `X-Forwarded-For` or `request.client.host`.
- **Role Quotas:**
  - `public` (Unauthenticated): 10 req/min, burst 5
  - `user`: 60 req/min, burst 15
  - `researcher`: 180 req/min, burst 30
  - `admin`: 1000 req/min, burst 100

### Fail-Open Policy
- If Redis infrastructure is unreachable or raises a connection error during evaluation, `RedisRateLimiter` logs a structured warning (`gateway.ratelimit.fail_open`) and permits the request to proceed.
- Prevents cache infrastructure outages from escalating into total API downtime.

---

## 3. Configuration Parameters (`config/settings.py`)

| Environment Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENABLE_RATE_LIMITING` | `bool` | `True` | Set to `true` to enable rate limiting middleware. |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `int` | `60` | Base rate limit in requests per minute. |
| `RATE_LIMIT_BURST` | `int` | `15` | Maximum burst capacity (tokens) above steady rate. |

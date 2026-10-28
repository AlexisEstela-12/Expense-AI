# Local authentication: phase 3

Three auth endpoints are registered, in addition to the 24 original operations.
This phase does **not** protect financial/chat endpoints and is not ready for
public ingress. Existing loopback restrictions on the chat remain unchanged.

## Explicit runtime configuration

- `APP_ENV`: `development`, `test`, or `production`.
- `AUTH_ALLOWED_ORIGINS`: exact comma-separated origins, without paths, trailing
  slashes, whitespace or wildcards. HTTPS is required outside development.
- `AUTH_CSRF_KEY`: a cryptographically random 32-byte key encoded in URL-safe
  Base64. Supply through runtime secrets; never commit it. Every replica must use
  the same key. Rotation invalidates existing CSRF tokens, not session cookies;
  an authenticated client must fetch `/auth/session` again.

These settings never read dotenv, even in development. No default key exists.
Missing/invalid auth configuration or missing tables returns a generic 503.
Migration and initial account creation remain explicit administrative actions.
They have not been run against a real database.

## Endpoint contracts

- `POST /auth/login`: JSON with exactly `username` and `password`, an allowed
  `Origin`, and `X-CSRF-Token: login`. The public marker is deliberately not a
  session secret: exact-origin enforcement, mandatory JSON and the custom header
  protect this unauthenticated request against browser CSRF. Limit body to 4096
  bytes. Invalid request: 400; rejected origin/header: 403; incorrect credentials:
  generic 401. Success returns `user`, `csrf_token`, `expires_at` and sets a new
  session cookie. No raw session identifier is returned in JSON.
- `GET /auth/session`: cookie required. Returns the same identity/CSRF/expiry
  fields. An explicit Origin must be allowed; absent Origin supports same-origin
  browser GETs. Explicit cross-site fetches are rejected. Invalid/expired/revoked
  session: 401. A successful call refreshes idle expiry, capped by absolute expiry.
- `POST /auth/logout`: valid cookie, allowed Origin and the session's
  `X-CSRF-Token` required. Atomically revokes the row, returns `{"status":"ok"}`
  and expires the cookie. Wrong CSRF/origin: 403 without modifying the session.

All responses, including errors, use `Cache-Control: no-store`. Cookies use Path
`/`, HttpOnly, SameSite=Lax and no Domain. Test/production use Secure and
`__Host-expense_session`; development alone uses `expense_session_dev` without
Secure. Sessions expire after 30 minutes idle or 12 hours absolute. Only SHA-256
digests are stored. CSRF is HMAC-SHA256 bound to the cookie and shared key.

## Shared login throttling

Fixed 15-minute windows: five attempts per peer and 20 globally. Both successful
and incorrect credentials consume attempts. A 429 includes `Retry-After`; windows
expire without permanent account lockout. Conditional UPDATEs reserve counters
atomically, and a savepoint/PK handles concurrent first insertion. Both counter
claims share one transaction: a denied claim rolls them back together. Forwarded
headers are not read here; configure Uvicorn/proxy trust explicitly before public
ingress. A reverse proxy may make several clients share one peer limit.

Attempts are deliberately committed before issuing a session. If session creation
fails, the attempt remains counted, no partial session persists and no cookie is
issued. Database failures are sanitized. SQL Server locking/deadlock behavior
still needs a disposable SQL Server concurrency test; SQLite tests do not certify
that behavior. Limit counters are not reset by successful logins.

No session token, password, CSRF token or key is logged. Frontend/CORS integration,
financial endpoint protection, chat guard transition and container packaging are
later phases. In particular, production CORS is still the existing local policy.

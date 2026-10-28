# Local authentication frontend (phase 5)

Run the offline tests from `frontend/` with `node --test tests/auth.test.mjs`.
They replace fetch, prohibit browser storage, and use React server rendering;
they never call the backend. Build with `npm.cmd run build`.

The application first checks `/auth/session`. Financial screens and the chat mount
only after a valid response/login. Session cookie handling belongs to the browser;
the CSRF token exists only in a module closure. Every request includes credentials,
and private POSTs include the in-memory CSRF token. JavaScript never sets Origin.
The financial resource URLs, methods and bodies remain unchanged.

A 401 clears identity/CSRF and removes the entire financial/chat subtree. A new
session uses a new React key, preventing reuse of old form data or chat history.
Responses from earlier session generations are discarded. Existing chat cleanup
aborts its pending request when unmounted. Navigating between authenticated pages
continues to keep the chat mounted. No financial POST is retried on 401 or 403.

Logout calls the backend before clearing local state. If revocation cannot be
confirmed, the UI reports failure and does not claim the server session was
revoked. A backend 401 means the session is already invalid and clears local state.

## Pending browser integration

The API URL remains `http://127.0.0.1:8000`. For cross-origin browser requests from
Vite, the backend now permits credentials for its explicit AUTH_ALLOWED_ORIGINS
list, also used for CSRF. Development defaults to `http://127.0.0.1:5173`.
Use the same hostname consistently (do not mix localhost and
127.0.0.1), and development cookies require APP_ENV=development. Production Secure
cookies require HTTPS and the appropriate same-site/same-origin deployment.

No real browser/backend login has been validated, and no real user or migration
has been created/executed. Browser focus, responsive visuals, cookie attributes,
and live chat mount/unmount behavior remain to be tested with isolated HTTP
fixtures. React server-rendering tests do not replace those browser checks.

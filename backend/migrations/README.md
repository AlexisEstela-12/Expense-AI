# Local authentication, phase 2

`001_local_auth.sql` is an explicit, single-use migration for Azure SQL. It creates
only `dbo.auth_user`, `dbo.auth_session` and `dbo.auth_login_limit`, plus their
constraints/indexes, in one transaction. It intentionally fails if objects already
exist. Review the target schema and back up before an authorized execution. It has
not been executed against Azure. Do not run it from FastAPI or `create_all`.

Authentication uses separate `AuthBase.metadata`; financial `db.base.Base` and its
tables are unchanged. All authentication timestamps are UTC, stored without an
offset as `DATETIME2(6)`. Digests are lowercase SHA-256 hex, never session tokens.
The login-limit table only provides storage; atomic throttling is a later phase.

After a separately authorized migration, run from the project root:

```powershell
python -m backend.security.admin create-user
```

Set `APP_ENV` explicitly beforehand; database variables follow existing policy.
The command prompts for a username (ASCII letters/digits, `_`, `.`, `-`) and twice
for a hidden password. Passwords follow phase 1 policy (15 characters minimum,
1024 UTF-8 bytes maximum), with no trimming. No values are passed on the command
line or printed. There are no defaults, registration endpoint, or automatic
bootstrap. Missing schema/configuration is an error, never an invitation to create
tables. A second account is rejected, including by the database constraint.

Do not run this command against a real database during offline tests. Tests inject
a SQLite in-memory session factory and fictitious interactive input. This phase
does not enable authentication or protect existing HTTP operations. Container
packaging of security/admin modules is deferred; the existing image is unchanged.

-- Explicit additive Azure SQL migration. Never invoked by application startup.
-- Run once by an administrator after review/backup, before create-user.
-- Existing auth objects cause failure; do not silently accept schema drift.
SET XACT_ABORT ON;
BEGIN TRY
    BEGIN TRANSACTION;
    CREATE TABLE dbo.auth_user (
        id INT NOT NULL,
        username NVARCHAR(128) NOT NULL,
        password_hash VARCHAR(512) NOT NULL,
        active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2(6) NOT NULL,
        password_changed_at DATETIME2(6) NOT NULL,
        CONSTRAINT pk_auth_user PRIMARY KEY (id),
        CONSTRAINT uq_auth_user_username UNIQUE (username),
        CONSTRAINT ck_auth_user_singleton CHECK (id = 1),
        CONSTRAINT ck_auth_user_argon2id CHECK (password_hash LIKE '$argon2id$%'),
        CONSTRAINT ck_auth_user_dates CHECK (password_changed_at >= created_at)
    );
    CREATE TABLE dbo.auth_session (
        token_hash VARCHAR(64) NOT NULL,
        user_id INT NOT NULL,
        created_at DATETIME2(6) NOT NULL,
        last_seen_at DATETIME2(6) NOT NULL,
        idle_expires_at DATETIME2(6) NOT NULL,
        expires_at DATETIME2(6) NOT NULL,
        revoked_at DATETIME2(6) NULL,
        CONSTRAINT pk_auth_session PRIMARY KEY (token_hash),
        CONSTRAINT fk_auth_session_user FOREIGN KEY (user_id) REFERENCES dbo.auth_user(id),
        CONSTRAINT ck_auth_session_digest CHECK (DATALENGTH(token_hash) = 64 AND token_hash COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'),
        CONSTRAINT ck_auth_session_dates CHECK (last_seen_at >= created_at AND expires_at >= last_seen_at AND idle_expires_at >= last_seen_at),
        CONSTRAINT ck_auth_session_revoked CHECK (revoked_at IS NULL OR revoked_at >= created_at)
    );
    CREATE INDEX ix_auth_session_user ON dbo.auth_session(user_id);
    CREATE INDEX ix_auth_session_expires ON dbo.auth_session(expires_at);
    CREATE INDEX ix_auth_session_idle_expires ON dbo.auth_session(idle_expires_at);
    CREATE TABLE dbo.auth_login_limit (
        key_hash VARCHAR(64) NOT NULL,
        window_started_at DATETIME2(6) NOT NULL,
        window_expires_at DATETIME2(6) NOT NULL,
        attempts INT NOT NULL DEFAULT 0,
        next_allowed_at DATETIME2(6) NULL,
        CONSTRAINT pk_auth_login_limit PRIMARY KEY (key_hash),
        CONSTRAINT ck_auth_login_limit_digest CHECK (DATALENGTH(key_hash) = 64 AND key_hash COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'),
        CONSTRAINT ck_auth_login_limit_attempts CHECK (attempts >= 0),
        CONSTRAINT ck_auth_login_limit_window CHECK (window_expires_at > window_started_at)
    );
    CREATE INDEX ix_auth_login_limit_expires ON dbo.auth_login_limit(window_expires_at);
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;

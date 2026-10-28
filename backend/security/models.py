"""Authentication metadata is separate from financial Base and app startup.

All timestamps are naive UTC, stored as DATETIME2(6) on SQL Server.
No sessions, engines or schema operations are created by importing this file.
"""
import re
from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey,
                        Index, Integer, MetaData, String, Unicode, text)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import DeclarativeBase, validates


class AuthBase(DeclarativeBase):
    metadata = MetaData(schema='dbo')


UTC_DATETIME = DateTime().with_variant(DATETIME2(precision=6), 'mssql')


def digest_checks(column, name):
    # Dialect-specific length/hex checks; binary collation is important on SQL
    # Server, where default collations commonly ignore case.
    return (
        CheckConstraint(f"length({column}) = 64 AND {column} NOT GLOB '*[^0-9a-f]*'",
                        name=name).ddl_if(dialect='sqlite'),
        CheckConstraint(f"DATALENGTH({column}) = 64 AND {column} COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9a-f]%'",
                        name=name).ddl_if(dialect='mssql'),
    )


class AuthUser(AuthBase):
    __tablename__ = 'auth_user'
    id = Column(Integer, primary_key=True, autoincrement=False)
    username = Column(Unicode(128), nullable=False, unique=True)
    password_hash = Column(String(512), nullable=False)
    active = Column(Boolean, nullable=False, server_default=text('1'))
    created_at = Column(UTC_DATETIME, nullable=False)
    password_changed_at = Column(UTC_DATETIME, nullable=False)
    __table_args__ = (
        CheckConstraint('id = 1', name='ck_auth_user_singleton'),
        CheckConstraint("password_hash LIKE '$argon2id$%'", name='ck_auth_user_argon2id'),
        CheckConstraint('password_changed_at >= created_at', name='ck_auth_user_dates'),
    )

    @validates('password_hash')
    def validate_password_hash(self, key, value):
        from argon2 import Type, extract_parameters
        from argon2.exceptions import InvalidHashError
        try:
            if not isinstance(value, str) or len(value) > 512:
                raise ValueError
            if extract_parameters(value).type != Type.ID:
                raise ValueError
        except (ValueError, InvalidHashError):
            raise ValueError('Hash de contrasena invalido.') from None
        return value


class AuthSession(AuthBase):
    __tablename__ = 'auth_session'
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey('dbo.auth_user.id'), nullable=False)
    created_at = Column(UTC_DATETIME, nullable=False)
    last_seen_at = Column(UTC_DATETIME, nullable=False)
    idle_expires_at = Column(UTC_DATETIME, nullable=False)
    expires_at = Column(UTC_DATETIME, nullable=False)
    revoked_at = Column(UTC_DATETIME, nullable=True)
    __table_args__ = (
        *digest_checks('token_hash', 'ck_auth_session_digest'),
        CheckConstraint('last_seen_at >= created_at AND expires_at >= last_seen_at AND idle_expires_at >= last_seen_at', name='ck_auth_session_dates'),
        CheckConstraint('revoked_at IS NULL OR revoked_at >= created_at', name='ck_auth_session_revoked'),
        Index('ix_auth_session_user', 'user_id'),
        Index('ix_auth_session_expires', 'expires_at'),
        Index('ix_auth_session_idle_expires', 'idle_expires_at'),
    )

    @validates('token_hash')
    def validate_digest(self, key, value):
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('Hash de sesion invalido.')
        return value


class AuthLoginLimit(AuthBase):
    __tablename__ = 'auth_login_limit'
    key_hash = Column(String(64), primary_key=True)
    window_started_at = Column(UTC_DATETIME, nullable=False)
    window_expires_at = Column(UTC_DATETIME, nullable=False)
    attempts = Column(Integer, nullable=False, server_default=text('0'))
    next_allowed_at = Column(UTC_DATETIME, nullable=True)
    __table_args__ = (
        *digest_checks('key_hash', 'ck_auth_login_limit_digest'),
        CheckConstraint('attempts >= 0', name='ck_auth_login_limit_attempts'),
        CheckConstraint('window_expires_at > window_started_at', name='ck_auth_login_limit_window'),
        Index('ix_auth_login_limit_expires', 'window_expires_at'),
    )

    @validates('key_hash')
    def validate_digest(self, key, value):
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('Clave de control invalida.')
        return value

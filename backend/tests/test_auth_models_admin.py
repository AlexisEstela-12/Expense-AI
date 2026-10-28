"""Phase 2 tests: SQLite memory, fake interactive input and static T-SQL QA."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta
import io
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from security import admin
from security.models import AuthBase, AuthUser, AuthSession, AuthLoginLimit
from security.primitives import hash_password, verify_password, generate_session_token, hash_session_token

PASSWORD = 'Fictitious phase two password'
ROOT = Path(__file__).resolve().parents[1]


class AuthModelsAdminTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoded = hash_password(PASSWORD)

    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:',
                                    execution_options={'schema_translate_map': {'dbo': None}})
        self.addCleanup(self.engine.dispose)

        @event.listens_for(self.engine, 'connect')
        def foreign_keys(connection, record):
            connection.execute('PRAGMA foreign_keys=ON')

        AuthBase.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.now = datetime(2026, 10, 27)

    def user(self, id=1):
        return AuthUser(id=id, username='fictitious', password_hash=self.encoded,
                        created_at=self.now, password_changed_at=self.now)

    def session_values(self, token_hash=None, user_id=1):
        return dict(token_hash=token_hash or hash_session_token(generate_session_token()), user_id=user_id,
                    created_at=self.now, last_seen_at=self.now,
                    idle_expires_at=self.now+timedelta(minutes=30),
                    expires_at=self.now+timedelta(hours=12))

    def test_metadata_separate_from_financial_and_imports_have_no_connections(self):
        from db.base import Base
        from db import models
        self.assertIsNot(AuthBase.metadata, Base.metadata)
        self.assertFalse(set(AuthBase.metadata.tables) & set(Base.metadata.tables))
        self.assertEqual(set(inspect(self.engine).get_table_names()),
                         {'auth_user','auth_session','auth_login_limit'})
        self.assertNotIn('db.session', sys.modules)
        self.assertNotIn('main', sys.modules)

    def test_create_initial_user_only_stores_argon2id(self):
        with self.sessions() as session:
            admin.create_initial_user(session,'fictitious',PASSWORD)
        with self.sessions() as session:
            user=session.get(AuthUser,1)
            self.assertTrue(user.active)
            self.assertNotEqual(user.password_hash,PASSWORD)
            self.assertTrue(verify_password(PASSWORD,user.password_hash))
            self.assertNotIn(PASSWORD,repr(user))
            self.assertNotIn('password',AuthUser.__table__.c)

    def test_initial_user_does_not_change_financial_rows(self):
        from datetime import date
        from decimal import Decimal
        from db.base import Base
        from db.models import Movement
        Base.metadata.create_all(self.engine)
        with self.sessions() as session:
            session.add(Movement(date=date(2026,10,27),kind='income',currency='PEN',
                                 amount=Decimal('123.45'),category='Ficticio'))
            session.commit()
        def snapshot():
            with self.engine.connect() as connection:
                return {table.name:list(connection.execute(select(table)))
                        for table in Base.metadata.sorted_tables}
        before=snapshot()
        with self.sessions() as session:
            admin.create_initial_user(session,'fictitious',PASSWORD)
        self.assertEqual(snapshot(),before)

    def test_second_account_rejected_by_command_and_database(self):
        with self.sessions() as session:
            admin.create_initial_user(session,'fictitious',PASSWORD)
        with self.sessions() as session:
            with self.assertRaises(admin.AdministrationError):
                admin.create_initial_user(session,'another',PASSWORD)
        for id in (1,2,0):
            with self.sessions() as session:
                session.add(self.user(id))
                with self.assertRaises(IntegrityError):
                    session.commit()
        with self.sessions() as session:
            self.assertEqual(len(session.scalars(select(AuthUser)).all()),1)

    def test_plaintext_password_and_raw_session_token_rejected(self):
        with self.assertRaises(ValueError):
            AuthUser(password_hash=PASSWORD)
        with self.assertRaises(ValueError):
            AuthSession(token_hash=generate_session_token())
        with self.engine.begin() as connection:
            with self.assertRaises(IntegrityError):
                connection.execute(AuthUser.__table__.insert(),dict(id=1,username='fake',
                                   password_hash=PASSWORD,created_at=self.now,password_changed_at=self.now))

    def test_sessions_store_digest_and_enforce_foreign_key(self):
        token=generate_session_token()
        digest=hash_session_token(token)
        with self.sessions() as session:
            session.add(self.user())
            session.commit()
            session.add(AuthSession(**self.session_values(digest)))
            session.commit()
        with self.sessions() as session:
            saved=session.get(AuthSession,digest)
            self.assertEqual(saved.user_id,1)
            self.assertNotIn('token',AuthSession.__table__.c)
            self.assertNotIn(token,repr(saved))
        with self.sessions() as session:
            session.add(AuthSession(**self.session_values(user_id=999)))
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_digest_and_date_constraints_at_database_boundary(self):
        with self.sessions() as session:
            session.add(self.user())
            session.commit()
        for changes in ({'token_hash':'x'*64},{'token_hash':'A'*64},{'token_hash':'a'*63},
                        {'expires_at':self.now-timedelta(seconds=1)},
                        {'revoked_at':self.now-timedelta(seconds=1)}):
            with self.engine.begin() as connection:
                with self.assertRaises(IntegrityError):
                    connection.execute(AuthSession.__table__.insert(),self.session_values()|changes)

    def test_login_limit_constraints_and_indexes(self):
        values=dict(key_hash='a'*64,window_started_at=self.now,
                    window_expires_at=self.now+timedelta(minutes=15),attempts=1)
        with self.engine.begin() as connection:
            connection.execute(AuthLoginLimit.__table__.insert(),values)
        for changes in ({'key_hash':'b'*64,'attempts':-1},
                        {'key_hash':'b'*64,'window_expires_at':self.now}, {'key_hash':'z'*64}):
            with self.engine.begin() as connection:
                with self.assertRaises(IntegrityError):
                    connection.execute(AuthLoginLimit.__table__.insert(),values|changes)
        for table in AuthBase.metadata.tables.values():
            self.assertEqual({i.name for i in table.indexes},
                             {i['name'] for i in inspect(self.engine).get_indexes(table.name)})

    def test_admin_interactive_input_hidden_and_no_secret_output(self):
        output=io.StringIO()
        with patch('builtins.input',return_value='fictitious'), \
             patch('getpass.getpass',side_effect=[PASSWORD,PASSWORD]) as hidden, redirect_stdout(output):
            self.assertEqual(admin.main(['create-user'],session_factory=self.sessions),0)
            self.assertEqual(hidden.call_count,2)
        self.assertNotIn(PASSWORD,output.getvalue())

    def test_admin_mismatch_visible_fallback_and_invalid_input_write_nothing(self):
        for username,secrets in [('fictitious',[PASSWORD,'different']),
                                 ('bad username',[PASSWORD,PASSWORD]),('fictitious',['short','short'])]:
            with patch('builtins.input',return_value=username), \
                 patch('getpass.getpass',side_effect=secrets), redirect_stdout(io.StringIO()):
                self.assertEqual(admin.main(['create-user'],session_factory=self.sessions),1)
        import getpass
        with patch('builtins.input',return_value='fictitious'), \
             patch('getpass.getpass',side_effect=getpass.GetPassWarning()), redirect_stdout(io.StringIO()):
            self.assertEqual(admin.main(['create-user'],session_factory=self.sessions),1)
        with self.sessions() as session:
            self.assertEqual(session.scalars(select(AuthUser)).all(),[])

    def test_missing_schema_does_not_trigger_ddl_or_leak_sql(self):
        empty=create_engine('sqlite+pysqlite:///:memory:',
                            execution_options={'schema_translate_map': {'dbo': None}})
        try:
            with sessionmaker(bind=empty)() as session:
                with self.assertRaises(admin.AdministrationError) as caught:
                    admin.create_initial_user(session,'fictitious',PASSWORD)
                self.assertNotIn(PASSWORD,str(caught.exception))
            self.assertEqual(inspect(empty).get_table_names(),[])
        finally:
            empty.dispose()

    def test_migration_is_additive_and_matches_mssql_metadata(self):
        sql=(ROOT/'migrations/001_local_auth.sql').read_text()
        sql=re.sub(r'--[^\n]*','',sql)
        self.assertNotRegex(sql.upper(),r'\b(DROP|DELETE|ALTER|INSERT|UPDATE)\b')
        self.assertEqual(set(re.findall(r'CREATE TABLE dbo\.(\w+)',sql)),
                         {table.name for table in AuthBase.metadata.tables.values()})
        self.assertIn('SET XACT_ABORT ON',sql)
        self.assertIn('ROLLBACK TRANSACTION',sql)
        self.assertIn('THROW;',sql)
        for table in AuthBase.metadata.sorted_tables:
            ddl=str(CreateTable(table).compile(dialect=mssql.dialect()))
            self.assertIn('CREATE TABLE',ddl)
            self.assertNotIn('GLOB',ddl)
            for column in table.columns:
                column_type=str(column.type.compile(dialect=mssql.dialect()))
                if column_type == 'INTEGER':
                    column_type = 'INT'
                self.assertRegex(sql,rf'\b{column.name}\s+{re.escape(column_type)}\b' if '(' not in column_type
                                 else rf'\b{column.name}\s+{re.escape(column_type)}')
            for constraint in table.constraints:
                if constraint.name and 'sqlite' not in str(constraint._ddl_if):
                    self.assertIn(constraint.name,sql)
            for index in table.indexes:
                self.assertIn(index.name,sql)

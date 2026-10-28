"""Fictitious SQL settings only: no dotenv file or DBAPI connection is used."""
import importlib.util
import io
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
from urllib.parse import unquote_plus

from core.config import ConfigurationError, load_database_settings

ROOT = Path(__file__).resolve().parents[1]
FAKE = dict(DB_SERVER='fictional.invalid', DB_NAME='fictional_db',
            DB_USER='fictional_user', DB_PASSWORD='fictional_password')


class SqlConfigTest(unittest.TestCase):
    def test_missing_invalid_environment_never_reads_file(self):
        with patch('dotenv.dotenv_values', side_effect=AssertionError('File forbidden')):
            for environ in ({}, {'APP_ENV': ''}, {'APP_ENV': 'not-a-secret'},
                            {'APP_ENV': 'Production'}):
                with self.subTest(environ=environ), self.assertRaises(ConfigurationError) as caught:
                    load_database_settings(environ=FAKE | environ)
                self.assertNotIn('not-a-secret', str(caught.exception))
                self.assertIn('APP_ENV', str(caught.exception))

    def test_test_and_production_skip_dotenv_entirely(self):
        with patch('dotenv.dotenv_values', side_effect=AssertionError('File forbidden')) as read:
            for env in ('test', 'production'):
                result = load_database_settings(environ=FAKE | {'APP_ENV': env})
                self.assertEqual(result.app_env, env)
            read.assert_not_called()

    def test_explicit_environment_precedes_process_and_cannot_come_from_file(self):
        with patch('dotenv.dotenv_values', return_value=FAKE | {'APP_ENV': 'production'}) as read:
            self.assertEqual(load_database_settings(app_env='development', environ={}).app_env,
                             'development')
            read.assert_called_once()
        with patch('dotenv.dotenv_values', side_effect=AssertionError('File forbidden')):
            with self.assertRaises(ConfigurationError):
                load_database_settings(environ={})
            self.assertEqual(load_database_settings(app_env='test', environ=FAKE | {'APP_ENV': 'bad'}).app_env,
                             'test')

    def test_development_loads_optional_file_without_mutating_process(self):
        with patch('dotenv.dotenv_values', return_value=FAKE) as read, \
             patch.dict('os.environ', {'APP_ENV': 'development', 'DB_USER': 'process_user'}, clear=True):
            result = load_database_settings()
            self.assertEqual(result.user, 'process_user')
            import os
            self.assertNotIn('DB_PASSWORD', os.environ)
            read.assert_called_once_with(ROOT / '.env', interpolate=False)
        with patch('dotenv.dotenv_values', return_value={}):
            self.assertEqual(load_database_settings(app_env='development', environ=FAKE).name,
                             FAKE['DB_NAME'])

    def test_missing_empty_and_whitespace_values_are_sanitized(self):
        for key in FAKE:
            for bad in (None, '', '   '):
                with self.subTest(key=key, bad=bad), self.assertRaises(ConfigurationError) as caught:
                    load_database_settings(app_env='test', environ=FAKE | {key: bad})
                self.assertIn(key, str(caught.exception))
                for value in FAKE.values():
                    self.assertNotIn(value, str(caught.exception))
        with patch('dotenv.dotenv_values', side_effect=ValueError(FAKE['DB_PASSWORD'])):
            with self.assertRaises(ConfigurationError) as caught:
                load_database_settings(app_env='development', environ={})
            self.assertNotIn(FAKE['DB_PASSWORD'], str(caught.exception))
            self.assertTrue(caught.exception.__suppress_context__)

    def test_password_preserved_and_odbc_delimiters_escaped(self):
        # Decode the braced PWD value with an independent character scanner.
        for password in (' a;b}c ${DB_USER} ', '}}', '{x}', ' x ', '${MISSING}'):
            with self.subTest(case='fictitious special characters'):
                settings = load_database_settings(app_env='test', environ=FAKE | {'DB_PASSWORD': password})
                self.assertEqual(settings.password, password)
                self.assertNotIn(password, repr(settings))
                self.assertNotIn(password, str(settings))
                encoded = settings.odbc_connection_string().split('PWD=', 1)[1]
                self.assertEqual(encoded[0], '{')
                decoded, index = '', 1
                while index < len(encoded):
                    if encoded[index:index+2] == '}}':
                        decoded += '}'
                        index += 2
                    elif encoded[index] == '}':
                        break
                    else:
                        decoded += encoded[index]
                        index += 1
                self.assertEqual(decoded, password)
                self.assertTrue(encoded[index+1:].startswith(';Encrypt=yes;TrustServerCertificate=no;'))

    def test_development_preserves_literal_interpolation_and_spaces(self):
        from dotenv import dotenv_values
        local = dotenv_values(stream=io.StringIO('DB_PASSWORD=" a;}} ${DB_USER} "\n'), interpolate=False)
        with patch('dotenv.dotenv_values', return_value=FAKE | local):
            settings = load_database_settings(app_env='development', environ={})
        self.assertEqual(settings.password, ' a;}} ${DB_USER} ')

    def test_import_config_has_no_configuration_or_engine_side_effects(self):
        spec = importlib.util.spec_from_file_location('_config_import_probe', ROOT / 'core/config.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {spec.name: module}), \
             patch('dotenv.dotenv_values', side_effect=AssertionError('File forbidden')), \
             patch('sqlalchemy.create_engine', side_effect=AssertionError('Engine forbidden')), \
             patch.dict('os.environ', {}, clear=True):
            spec.loader.exec_module(module)

    def test_session_exports_and_engine_options_without_real_engine(self):
        # Execute the real module with both supported package import styles.
        for package in ('db', 'backend.db'):
            module = ModuleType('_session_probe')
            module.__package__ = package
            module.__file__ = str(ROOT / 'db/session.py')
            fake_engine, fake_sessions = object(), object()
            aliases = {'backend.core.config': sys.modules['core.config']}
            with patch.dict(sys.modules, aliases), \
                 patch.dict('os.environ', FAKE | {'APP_ENV': 'production'}, clear=True), \
                 patch('dotenv.dotenv_values', side_effect=AssertionError('File forbidden')), \
                 patch('sqlalchemy.create_engine', return_value=fake_engine) as engine, \
                 patch('sqlalchemy.orm.sessionmaker', return_value=fake_sessions) as sessions:
                exec(compile((ROOT / 'db/session.py').read_text(encoding='utf-8'), module.__file__, 'exec'), module.__dict__)
            engine.assert_called_once_with(module.DB_URL, pool_pre_ping=True)
            sessions.assert_called_once_with(bind=fake_engine)
            self.assertIs(module.engine, fake_engine)
            self.assertIs(module.SessionLocal, fake_sessions)
            self.assertEqual(unquote_plus(module.DB_URL.split('odbc_connect=', 1)[1]), module.connection_string)
            for setting in ('DRIVER={ODBC Driver 18 for SQL Server};', ',1433}',
                            'Encrypt=yes;', 'TrustServerCertificate=no;', 'Connection Timeout=30;'):
                self.assertIn(setting, module.connection_string)

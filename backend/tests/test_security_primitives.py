"""Phase 1 only: fictitious secrets, no database, API or external services."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
import hashlib
import io
import unittest
from unittest.mock import patch

from argon2 import Type, extract_parameters
from core.config import ConfigurationError
from security.config import load_security_settings
from security import primitives as security

PASSWORD = 'Fictitious password; } ${literal} '


class SecurityPrimitivesTest(unittest.TestCase):
    def test_argon2id_policy_random_salt_and_verification(self):
        first = security.hash_password(PASSWORD)
        second = security.hash_password(PASSWORD)
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith('$argon2id$v=19$m=65536,t=3,p=1$'))
        parameters = extract_parameters(first)
        self.assertEqual((parameters.type, parameters.salt_len, parameters.hash_len), (Type.ID,16,32))
        self.assertTrue(security.verify_password(PASSWORD, first))
        self.assertFalse(security.verify_password('Incorrect fictitious password', first))
        self.assertFalse(security.verify_password(PASSWORD.rstrip(), first))

    def test_invalid_passwords_and_utf8_size_limits(self):
        for value in (None, b'not a password', '', 'short', ' '*20, 'x'*1025,
                      '\u00e9'*513, '\ud800'*20):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(security.InvalidSecurityInput):
                    security.hash_password(value)
                self.assertFalse(security.verify_password(value, '$invalid'))
        self.assertTrue(security.verify_password('x'*1024, security.hash_password('x'*1024)))

    def test_invalid_phc_and_excessive_cost_rejected_before_verification(self):
        valid = security.hash_password(PASSWORD)
        for value in (None, '', '$invalid', 'x'*513,
                      valid.replace('m=65536', 'm=999999999'), valid.replace('argon2id','argon2i')):
            with patch.object(security.PasswordHasher, 'verify', side_effect=AssertionError('Cost guard failed')):
                self.assertFalse(security.verify_password(PASSWORD, value))

    def test_session_generation_uses_32_random_bytes(self):
        with patch.object(security.secrets, 'token_urlsafe', return_value='mock') as random:
            self.assertEqual(security.generate_session_token(),'mock')
            random.assert_called_once_with(32)
        tokens = {security.generate_session_token() for _ in range(1000)}
        self.assertEqual(len(tokens),1000)
        self.assertTrue(all(len(token)==43 for token in tokens))

    def test_session_hash_and_constant_time_comparison(self):
        token = security.generate_session_token()
        other = security.generate_session_token()
        digest = security.hash_session_token(token)
        self.assertEqual(digest, hashlib.sha256(token.encode('ascii')).hexdigest())
        self.assertEqual(len(digest),64)
        self.assertTrue(security.tokens_equal(token,token))
        self.assertFalse(security.tokens_equal(token,other))
        self.assertTrue(security.hashes_equal(digest,digest))
        self.assertFalse(security.hashes_equal(digest,security.hash_session_token(other)))
        with patch.object(security.hmac,'compare_digest',return_value=True) as comparison:
            security.tokens_equal(token,other)
            comparison.assert_called_once_with(token,other)

    def test_invalid_tokens_and_digests(self):
        for value in (None, b'x', '', 'x'*10000, '\u00e9'*43, 'A'*42+'B'):
            with self.assertRaises(security.InvalidSecurityInput):
                security.hash_session_token(value)
            self.assertFalse(security.tokens_equal(value,value))
            self.assertFalse(security.hashes_equal(value,value))

    def test_idle_and_absolute_expiry_boundaries(self):
        start = datetime(2026,10,27,tzinfo=timezone.utc)
        self.assertFalse(security.session_expired(created_at=start,last_seen_at=start,
                                                 now=start+timedelta(minutes=29,seconds=59)))
        self.assertTrue(security.session_expired(created_at=start,last_seen_at=start,
                                                now=start+timedelta(minutes=30)))
        self.assertTrue(security.session_expired(created_at=start,last_seen_at=start+timedelta(hours=12),
                                                now=start+timedelta(hours=12)))
        self.assertFalse(security.session_expired(created_at=start,last_seen_at=start+timedelta(hours=11,minutes=59),
                                                 now=start+timedelta(hours=11,minutes=59)))
        for seen,now in ((start-timedelta(seconds=1),start),(start,start-timedelta(seconds=1)),
                         (start,start.replace(tzinfo=None))):
            with self.assertRaises(security.InvalidSecurityInput):
                security.session_expired(created_at=start,last_seen_at=seen,now=now)

    def test_cookie_policy_all_environments_never_reads_dotenv(self):
        with patch('dotenv.dotenv_values',side_effect=AssertionError('File forbidden')):
            for env in ('development','test','production'):
                settings=load_security_settings(environ={'APP_ENV':env})
                self.assertEqual(settings.cookie_secure,env!='development')
                self.assertEqual(settings.cookie_name,'expense_session_dev' if env=='development' else '__Host-expense_session')
                self.assertTrue(settings.cookie_httponly)
                self.assertEqual((settings.cookie_samesite,settings.cookie_path,settings.cookie_domain),('lax','/',None))
                self.assertEqual((settings.idle_timeout,settings.absolute_timeout),(timedelta(minutes=30),timedelta(hours=12)))
            for env in (None,'',PASSWORD):
                with self.assertRaises(ConfigurationError) as caught:
                    load_security_settings(environ={} if env is None else {'APP_ENV':env})
                self.assertNotIn(PASSWORD,str(caught.exception))
            self.assertEqual(load_security_settings(app_env='test',environ={'APP_ENV':'bad'}).app_env,'test')

    def test_no_secret_output_or_error_representation(self):
        output=io.StringIO()
        with redirect_stdout(output),redirect_stderr(output):
            hashed=security.hash_password(PASSWORD)
            security.verify_password(PASSWORD,hashed)
            token=security.generate_session_token()
            security.hash_session_token(token)
            for value in (PASSWORD*100, token*100):
                try:
                    security.hash_session_token(value)
                except security.InvalidSecurityInput as error:
                    self.assertNotIn(value,repr(error))
        self.assertEqual(output.getvalue(),'')

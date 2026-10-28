"""Provider/configuration regression with fictitious keys and a mocked SDK."""
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from core.config import ConfigurationError, load_openai_api_key
from llm import openai_provider as provider

KEY = 'fictional-key-not-a-credential'
ROOT = Path(__file__).resolve().parents[1]


class OpenAIConfigTest(unittest.TestCase):
    def call(self, tools=False):
        if tools:
            return provider.create_tool_response(input_items=[{'role': 'user', 'content': 'Fictitious'}],
                                                 instructions='Fictitious', tools=[], tool_choice='auto')
        return provider.ask_llm('Fictitious')

    def test_development_loads_simulated_file_for_both_provider_methods(self):
        for tools in (False, True):
            with self.subTest(tools=tools), \
                 patch.dict('os.environ', {'APP_ENV': 'development'}, clear=True), \
                 patch('dotenv.dotenv_values', return_value={'OPENAI_API_KEY': KEY}) as read, \
                 patch.object(provider, 'OpenAI') as client:
                self.call(tools)
                read.assert_called_once_with(ROOT / '.env', interpolate=False)
                self.assertEqual(client.call_args.kwargs['api_key'], KEY)

    def test_test_and_production_never_load_file(self):
        for env in ('test', 'production'):
            for tools in (False, True):
                with self.subTest(env=env, tools=tools), \
                     patch.dict('os.environ', {'APP_ENV': env, 'OPENAI_API_KEY': KEY}, clear=True), \
                     patch('dotenv.dotenv_values', side_effect=AssertionError('File forbidden')) as read, \
                     patch.object(provider, 'OpenAI'):
                    self.call(tools)
                    read.assert_not_called()

    def test_process_priority_and_existing_key_trimming(self):
        with patch('dotenv.dotenv_values', return_value={'OPENAI_API_KEY': 'fictional-file-key'}):
            self.assertEqual(load_openai_api_key(app_env='development',
                             environ={'OPENAI_API_KEY': ' ' + KEY + ' '}), KEY)
            with self.assertRaises(ConfigurationError):
                load_openai_api_key(app_env='development', environ={'OPENAI_API_KEY': ''})

    def test_missing_invalid_environment_and_keys_fail_before_sdk_without_leaks(self):
        cases = ({}, {'APP_ENV': KEY}, {'APP_ENV': 'test'},
                 {'APP_ENV': 'production', 'OPENAI_API_KEY': ''},
                 {'APP_ENV': 'test', 'OPENAI_API_KEY': '   '})
        for values in cases:
            for tools in (False, True):
                output = io.StringIO()
                with self.subTest(case=list(values), tools=tools), \
                     patch.dict('os.environ', values, clear=True), \
                     patch('dotenv.dotenv_values', side_effect=AssertionError('File forbidden')), \
                     patch.object(provider, 'OpenAI') as client, \
                     redirect_stdout(output), redirect_stderr(output):
                    with self.assertRaises(provider.LLMProviderError) as caught:
                        self.call(tools)
                    self.assertEqual(caught.exception.code, 'configuration_error')
                    self.assertNotIn(KEY, repr(caught.exception))
                    self.assertTrue(caught.exception.__suppress_context__)
                    client.assert_not_called()
                self.assertEqual(output.getvalue(), '')

    def test_local_load_failure_is_sanitized(self):
        with patch.dict('os.environ', {'APP_ENV': 'development'}, clear=True), \
             patch('dotenv.dotenv_values', side_effect=ValueError(KEY)), \
             patch.object(provider, 'OpenAI') as client:
            with self.assertRaises(provider.LLMProviderError) as caught:
                self.call()
            self.assertEqual(str(caught.exception), 'configuration_error')
            self.assertNotIn(KEY, repr(caught.exception))
            client.assert_not_called()

    def test_request_parameters_and_return_values_are_preserved(self):
        for tools in (False, True):
            with self.subTest(tools=tools), \
                 patch.dict('os.environ', {'APP_ENV': 'test', 'OPENAI_API_KEY': KEY}, clear=True), \
                 patch.object(provider, 'OpenAI') as constructor:
                client = constructor.return_value.__enter__.return_value
                response = client.responses.create.return_value
                result = self.call(tools)
                constructor.assert_called_once_with(api_key=KEY, base_url='https://api.openai.com/v1',
                                                    timeout=30.0, max_retries=0)
                expected = dict(model='gpt-4.1-mini', input='Fictitious', max_output_tokens=200, store=False)
                if tools:
                    expected.update(input=[{'role': 'user', 'content': 'Fictitious'}],
                                    instructions='Fictitious', tools=[], tool_choice='auto',
                                    parallel_tool_calls=False)
                client.responses.create.assert_called_once_with(**expected)
                self.assertIs(result, response if tools else response.output_text)

    def test_existing_sdk_error_mapping_is_preserved(self):
        request = object()
        response = MagicMock(request=request, status_code=400, headers={})
        errors = [
            (provider.AuthenticationError(KEY, response=response, body=None), 'authentication_error'),
            (provider.RateLimitError(KEY, response=response, body=None), 'rate_limit_error'),
            (provider.APITimeoutError(request=request), 'timeout'),
            (provider.APIConnectionError(request=request), 'connection_error'),
            (provider.OpenAIError(KEY), 'provider_error'),
        ]
        for tools in (False, True):
            cases = errors + [(provider.BadRequestError(KEY, response=response, body=None),
                               'provider_bad_request' if tools else 'provider_error')]
            for error, code in cases:
                with self.subTest(tools=tools, code=code), \
                     patch.dict('os.environ', {'APP_ENV': 'test', 'OPENAI_API_KEY': KEY}, clear=True), \
                     patch.object(provider, 'OpenAI', side_effect=error):
                    with self.assertRaises(provider.LLMProviderError) as caught:
                        self.call(tools)
                    self.assertEqual(str(caught.exception), code)
                    self.assertNotIn(KEY, repr(caught.exception))

    def test_import_provider_has_no_io_or_configuration_side_effects(self):
        for package in ('llm', 'backend.llm'):
            spec = importlib.util.spec_from_file_location('_provider_probe', ROOT / 'llm/openai_provider.py')
            module = importlib.util.module_from_spec(spec)
            module.__package__ = package
            import sys
            with patch.dict(sys.modules, {'backend.core.config': sys.modules['core.config']}), \
                 patch.dict('os.environ', {}, clear=True), \
                 patch('builtins.open', side_effect=AssertionError('File forbidden')), \
                 patch('dotenv.dotenv_values', side_effect=AssertionError('File forbidden')), \
                 patch('openai.OpenAI', side_effect=AssertionError('SDK forbidden')):
                spec.loader.exec_module(module)

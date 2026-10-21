"""Standalone text provider. No financial services or database access."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)


MODEL = 'gpt-4.1-mini'


class LLMProviderError(RuntimeError):
    """Provider failure exposing only a fixed, non-sensitive category."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def ask_llm(message: str) -> str:
    """Send caller-provided, non-sensitive text and return only response text.

    Configuration is loaded only when called. The caller must not include
    credentials, financial records, or Azure SQL information in the message.
    """
    if not isinstance(message, str) or not message.strip():
        raise ValueError('El mensaje debe ser un texto no vacío.')

    try:
        load_dotenv(
            dotenv_path=Path(__file__).resolve().parents[1] / '.env',
            override=False,
            interpolate=False,
        )
        api_key = os.getenv('OPENAI_API_KEY', '').strip()
    except Exception:
        raise LLMProviderError('configuration_error') from None
    if not api_key:
        raise LLMProviderError('configuration_error')

    try:
        with OpenAI(
            api_key=api_key,
            base_url='https://api.openai.com/v1',
            timeout=30.0,
            max_retries=0,
        ) as client:
            response = client.responses.create(
                model=MODEL,
                input=message,
                max_output_tokens=200,
                store=False,
            )
            return response.output_text
    except AuthenticationError:
        raise LLMProviderError('authentication_error') from None
    except RateLimitError:
        raise LLMProviderError('rate_limit_error') from None
    except APITimeoutError:
        raise LLMProviderError('timeout') from None
    except APIConnectionError:
        raise LLMProviderError('connection_error') from None
    except OpenAIError:
        raise LLMProviderError('provider_error') from None


def create_tool_response(*, input_items: list, instructions: str, tools: list, tool_choice: str):
    """Return Responses output items without executing any requested tool."""
    try:
        load_dotenv(
            dotenv_path=Path(__file__).resolve().parents[1] / '.env',
            override=False,
            interpolate=False,
        )
        api_key = os.getenv('OPENAI_API_KEY', '').strip()
    except Exception:
        raise LLMProviderError('configuration_error') from None
    if not api_key:
        raise LLMProviderError('configuration_error')

    try:
        with OpenAI(
            api_key=api_key,
            base_url='https://api.openai.com/v1',
            timeout=30.0,
            max_retries=0,
        ) as client:
            return client.responses.create(
                model=MODEL,
                input=input_items,
                instructions=instructions,
                tools=tools,
                tool_choice=tool_choice,
                parallel_tool_calls=False,
                max_output_tokens=200,
                store=False,
            )
    except AuthenticationError:
        raise LLMProviderError('authentication_error') from None
    except RateLimitError:
        raise LLMProviderError('rate_limit_error') from None
    except APITimeoutError:
        raise LLMProviderError('timeout') from None
    except APIConnectionError:
        raise LLMProviderError('connection_error') from None
    except BadRequestError:
        raise LLMProviderError('provider_bad_request') from None
    except OpenAIError:
        raise LLMProviderError('provider_error') from None

"""Balance chat contracts and aggregate-only explanations."""

import json
import logging
import re
import unicodedata
from time import perf_counter
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)
ExplanationReason = Literal[
    'configuration_error', 'authentication_error', 'rate_limit_error',
    'timeout', 'connection_error', 'provider_error', 'provider_unavailable',
    'empty_response', 'validation_rejected_digits', 'internal_error', 'unsupported',
]


class BalanceChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000, pattern=r'\S')


class BalanceChatResponse(BaseModel):
    answer: str
    financial_data: dict[str, dict[str, str]] | None
    explanation_source: Literal['llm', 'fallback', 'unsupported']
    explanation_reason: ExplanationReason | None = 'unsupported'
    diagnostic_id: str = Field(default_factory=lambda: uuid4().hex)


def is_balance_question(message: str) -> bool:
    """Accept only the small set of balance questions supported initially."""
    normalized = ''.join(
        char for char in unicodedata.normalize('NFD', message.lower())
        if unicodedata.category(char) != 'Mn'
    )
    normalized = re.sub(r'[^a-z\s]', ' ', normalized)
    normalized = ' '.join(normalized.split())
    return bool(re.fullmatch(
        r'(?:cuanto (?:dinero )?tengo(?: disponible| reservado)?'
        r'|(?:cual es|cuales son|consulta|consultar|muestra|mostrar|dime) '
        r'(?:mi |mis |el |los )?saldos?(?: total| reservado| disponible)?'
        r'|saldos?(?: total| reservado| disponible)?)'
        r'(?: en (?:soles(?: y dolares)?|dolares|pen(?: y usd)?|usd))?',
        normalized,
    ))


def explain_balances(financial_data: dict[str, dict[str, str]]) -> BalanceChatResponse:
    """Send only the six aggregate amounts and fixed instructions to the LLM."""
    started = perf_counter()
    diagnostic_id = uuid4().hex
    aggregates = {
        name: {currency: financial_data[name][currency] for currency in ('PEN', 'USD')}
        for name in ('balances', 'reserved', 'spendable')
    }
    fallback = (
        'El saldo total incluye el dinero reservado para metas de ahorro. '
        'El saldo reservado está apartado para esas metas y el disponible '
        'es el que puedes gastar. Los importes exactos de PEN y USD '
        'se muestran por separado en financial_data.'
    )
    source = 'fallback'
    answer = fallback
    reason = None
    try:
        # Lazy import also permits the fallback if the SDK is unavailable.
        if __package__.startswith('backend.'):
            from ..llm.openai_provider import LLMProviderError, ask_llm
        else:
            from llm.openai_provider import LLMProviderError, ask_llm

        try:
            explanation = ask_llm(
                'Responde en español con un único párrafo breve, sin listas '
                'ni enumeraciones. Explica únicamente la diferencia entre saldo '
                'total (balances), reservado para metas de ahorro (reserved) '
                'y disponible para gastar (spendable). No incluyas listas '
                'numeradas, cantidades, porcentajes, fechas, dígitos ni cifras '
                'financieras, tampoco números escritos en palabras. No calcules, '
                'conviertas monedas ni inventes datos. '
                'Remite a los importes exactos de financial_data, separados en PEN '
                'y USD. No añadas recomendaciones ni afirmaciones ajenas a estos datos. '
                'Saldos agregados: ' + json.dumps(aggregates, ensure_ascii=False)
            )
        except LLMProviderError as error:
            # Allowlist codes rather than copying arbitrary exception contents.
            reason = error.code if error.code in (
                'configuration_error', 'authentication_error', 'rate_limit_error',
                'timeout', 'connection_error', 'provider_error',
            ) else 'provider_error'
        else:
            if not explanation.strip():
                reason = 'empty_response'
            elif re.search(r'\d', explanation):
                reason = 'validation_rejected_digits'
            else:
                answer = explanation.strip()
                source = 'llm'
    except ImportError:
        reason = 'provider_unavailable'
    except Exception:
        reason = 'internal_error'

    # Only these three fields are logged; no exception or content is attached.
    logger.log(
        logging.INFO if source == 'llm' else logging.WARNING,
        json.dumps({
            'diagnostic_id': diagnostic_id,
            'outcome': reason or 'success',
            'duration_ms': round((perf_counter() - started) * 1000),
        }),
    )

    return BalanceChatResponse(
        answer=answer,
        financial_data=aggregates,
        explanation_source=source,
        explanation_reason=reason,
        diagnostic_id=diagnostic_id,
    )

"""Responses cache boundaries and content-free, per-call usage accounting.

Policy and Standard/global prices verified 2026-10-28:
https://developers.openai.com/api/docs/guides/prompt-caching
https://developers.openai.com/api/docs/pricing
"""
from __future__ import annotations

import json
import logging
import os


# Explicitly supported IDs only; custom/older models keep their original request.
_MODELS = frozenset({'gpt-6-sol', 'gpt-6-astra', 'gpt-6-luna', 'gpt-6.1-sol',
                     'gpt-6.1-terra', 'gpt-5.6', 'gpt-5.6-sol', 'gpt-5.6-cyber'})
# Input, cached read, output USD / million tokens. Unknown prices stay unknown.
_PRICES = {'gpt-6-sol': (2, .2, 10), 'gpt-6-astra': (10, 1, 50),
           'gpt-6.1-sol': (2, .1, 10), 'gpt-5.6-sol': (4, .4, 20)}
# Inherit the server's configured INFO handler; local supervisor persists this log.
_LOG = logging.getLogger('uvicorn.error.openai_usage')


def enabled(model: str, base_url: str) -> bool:
    return (model in _MODELS and base_url.rstrip('/') == 'https://api.openai.com/v1'
            and os.getenv('OPENAI_PROMPT_CACHE', '1') == '1')


def request_fields(model: str, instructions: str, content, *, base_url: str,
                   reusable: bool = True, reference: dict | None = None) -> dict:
    """Cache only authored instructions/reference data, never the changing suffix.

    Dynamic-schema/short-prefix operations use explicit mode without a marker:
    they pay ordinary input instead of writing a mostly one-use prompt to cache.
    """
    original = {'instructions': instructions, 'input': content}
    if not enabled(model, base_url):
        return original
    options = {'mode': 'explicit', 'ttl': '30m'}
    if not reusable:
        return {**original, 'prompt_cache_options': options}
    prefix = instructions
    if reference is not None:
        prefix += '\n\nFixed reference data (catalogue, session_fields, activation_signals):\n'
        prefix += json.dumps(reference, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    # Callers using multimodal input already provide complete user messages.
    messages = ([{'role': 'user', 'content': content}] if isinstance(content, str) else content)
    return {'prompt_cache_options': options, 'input': [
        {'role': 'developer', 'content': [{'type': 'input_text', 'text': prefix,
                                         'prompt_cache_breakpoint': {'mode': 'explicit'}}]},
        *messages,
    ]}


def _count(value):
    return value if type(value) is int and value >= 0 else None


def usage_record(body, *, model: str, operation: str, base_url: str) -> dict | None:
    """Keep only numeric usage; malformed/missing billing metadata cannot fail care."""
    if not isinstance(body, dict) or not isinstance(body.get('usage'), dict):
        return None
    usage = body['usage']
    details = usage.get('input_tokens_details')
    details = details if isinstance(details, dict) else {}
    record = {'operation': operation, 'model': model,
              'input_tokens': _count(usage.get('input_tokens')),
              'output_tokens': _count(usage.get('output_tokens')),
              'cached_tokens': _count(details.get('cached_tokens')),
              'cache_write_tokens': _count(details.get('cache_write_tokens')),
              'estimated_standard_cost_usd': None}
    counts = [record[key] for key in ('input_tokens', 'output_tokens', 'cached_tokens', 'cache_write_tokens')]
    if any(value is None for value in counts):
        return record
    incoming, outgoing, cached, written = counts
    if (incoming < cached + written or incoming > 272_000 or outgoing > 128_000 or model not in _PRICES
            or base_url.rstrip('/') != 'https://api.openai.com/v1'
            or body.get('service_tier', 'default') not in ('default', 'standard')):
        return record
    breakdown = details.get('cache_write_tokens_details')
    if written == 0:
        short, long = 0, 0
    elif isinstance(breakdown, dict):
        short, long = (_count(breakdown.get(key)) for key in ('ttl_30m_tokens', 'ttl_12h_tokens'))
        if short is None or long is None or short + long != written:
            return record
    else:
        # Every request in this app uses the default or explicit 30-minute TTL.
        short, long = written, 0
    record.update(cache_write_30m_tokens=short, cache_write_12h_tokens=long)
    ordinary = incoming - cached - written
    price, read_price, output_price = _PRICES[model]
    record['estimated_standard_cost_usd'] = round(
        (ordinary * price + cached * read_price + short * price * 1.25
         + long * price * 2.5 + outgoing * output_price) / 1_000_000, 10)
    record['pricing_date'] = '2026-10-28'
    return record


def record_usage(body, *, model: str, operation: str, base_url: str) -> None:
    record = usage_record(body, model=model, operation=operation, base_url=base_url)
    if record is not None:
        _LOG.info('openai_usage %s', json.dumps(record, sort_keys=True))

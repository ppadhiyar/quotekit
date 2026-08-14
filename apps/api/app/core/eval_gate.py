"""Groundedness scoring for the eval gate.

Uses azure-ai-evaluation's GroundednessEvaluator (LLM-judge, scored 1-5,
normalized here to 0-1). The same evaluator runs offline against the golden
dataset in evals/run_evals.py — one metric, two contexts: per-request gating
and CI regression testing.
"""

import logging

from ..config import get_settings

logger = logging.getLogger(__name__)

_evaluator = None


def _get_evaluator():
    global _evaluator
    if _evaluator is None:
        from azure.ai.evaluation import (
            AzureOpenAIModelConfiguration,
            GroundednessEvaluator,
        )

        s = get_settings()
        model_config = AzureOpenAIModelConfiguration(
            azure_endpoint=s.azure_openai_endpoint,
            api_key=s.azure_openai_api_key,
            api_version=s.azure_openai_api_version,
            azure_deployment=s.azure_openai_chat_deployment,
        )
        _evaluator = GroundednessEvaluator(model_config)
    return _evaluator


def score_groundedness(query: str, context: str, answer: str) -> float:
    """Return groundedness normalized to 0-1. Fails closed: scoring errors
    return 0.0 so an unscorable answer can never auto-approve."""
    try:
        result = _get_evaluator()(query=query, context=context, response=answer)
        raw = float(result["groundedness"])  # 1-5 scale
        return round((raw - 1.0) / 4.0, 3)
    except Exception:
        logger.exception("Groundedness scoring failed — failing closed")
        return 0.0

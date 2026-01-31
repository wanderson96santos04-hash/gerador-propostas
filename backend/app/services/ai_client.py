from __future__ import annotations

import re
from typing import Dict

from app.config import settings
from app.services.prompts import SYSTEM_PROMPT, build_user_prompt


# Assinatura white-label FINAL (imutável)
WHITE_LABEL_SIGNATURE = "Atenciosamente,\n\nEquipe Comercial"


def _remove_placeholders(text: str) -> str:
    """
    Remove placeholders clássicos que o GPT costuma inserir.
    """
    if not text:
        return text

    patterns = [
        r"\[Seu Nome\].*",
        r"\[Seu Cargo\].*",
        r"\[Seu Contato\].*",
        r"\[Telefone\].*",
        r"\[Email\].*",
        r"\[Nome da Empresa\].*",
        r"\[Nome da Sua Empresa\].*",
    ]

    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return text.strip()


def _force_white_label_signature(text: str) -> str:
    """
    Blindagem total:
    - Remove qualquer assinatura gerada pelo GPT
    - Remove placeholders
    - Recoloca assinatura white-label fixa
    """
    if not text:
        return WHITE_LABEL_SIGNATURE

    t = text.strip().replace("\r\n", "\n").replace("\r", "\n")

    # Remove blocos de assinatura comuns
    signature_markers = [
        r"\n\s*atenciosamente[:,]?\s*\n.*$",
        r"\n\s*cordialmente[:,]?\s*\n.*$",
        r"\n\s*assinatura[:,]?\s*\n.*$",
        r"\n\s*assinado[:,]?\s*\n.*$",
        r"\n\s*att[:,]?\s*\n.*$",
    ]

    for marker in signature_markers:
        t = re.sub(marker, "", t, flags=re.IGNORECASE | re.DOTALL)

    # Remove placeholders restantes
    t = _remove_placeholders(t)

    # Limpa excesso de linhas no final
    t = re.sub(r"\n{3,}$", "\n\n", t).strip()

    # Força assinatura final
    return f"{t}\n\n{WHITE_LABEL_SIGNATURE}\n"


def generate_with_gpt(data: Dict[str, str]) -> str:
    """
    Gera proposta usando GPT + pós-processamento white-label obrigatório.
    """

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY não configurada. "
            "Defina a variável de ambiente ou use AI_MODE=stub."
        )

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "Biblioteca openai não instalada. "
            "Instale manualmente apenas se for usar AI_MODE=gpt."
        )

    client = OpenAI(api_key=settings.openai_api_key)

    user_prompt = build_user_prompt(data)

    # Reforço extra (mesmo que o GPT ignore, o pós-processamento resolve)
    system_prompt = SYSTEM_PROMPT + """

REGRAS FINAIS (OBRIGATÓRIO):
- NÃO inclua campos como [Seu Nome], [Seu Cargo], [Telefone], [Email].
- NÃO inclua bloco de assinatura.
- Finalize apenas com uma chamada clara para ação.
"""

    response = client.chat.completions.create(
        model=settings.openai_model or "gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=1200,
    )

    text = response.choices[0].message.content
    if not text or not text.strip():
        raise RuntimeError("Resposta vazia da IA.")

    # 🔒 BLINDAGEM FINAL (o que resolve tudo)
    return _force_white_label_signature(text)

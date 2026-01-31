from __future__ import annotations

from typing import Dict

from app.config import settings
from app.services.prompts import SYSTEM_PROMPT, build_user_prompt


FORBIDDEN_SIGNATURE_MARKERS = [
    "[seu nome]",
    "[seu cargo]",
    "[seu contato]",
    "[nome da empresa]",
    "[email]",
    "[telefone]",
]


def _force_white_label(text: str) -> str:
    """
    Remove qualquer assinatura indevida gerada pelo GPT
    e força assinatura white-label neutra.
    """
    lower = text.lower()

    for marker in FORBIDDEN_SIGNATURE_MARKERS:
        if marker in lower:
            # corta tudo a partir do primeiro marcador encontrado
            idx = lower.find(marker)
            text = text[:idx].rstrip()
            break

    # Remove assinaturas comuns
    for sign in ["atenciosamente,", "atenciosamente", "assinatura"]:
        if sign in text.lower():
            text = text[: text.lower().rfind(sign)].rstrip()
            break

    # Assinatura final FIXA
    text += "\n\nAtenciosamente,\n\nEquipe Comercial"

    return text.strip()


def generate_with_gpt(data: Dict[str, str]) -> str:
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
            "Instale apenas se for usar AI_MODE=gpt."
        )

    client = OpenAI(api_key=settings.openai_api_key)

    user_prompt = build_user_prompt(data)

    response = client.chat.completions.create(
        model=settings.openai_model or "gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=1200,
    )

    text = response.choices[0].message.content or ""
    text = text.strip()

    if not text:
        raise RuntimeError("Resposta vazia da IA.")

    # 🔥 PÓS-PROCESSAMENTO DEFINITIVO
    return _force_white_label(text)

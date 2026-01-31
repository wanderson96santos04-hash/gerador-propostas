from __future__ import annotations

from typing import Dict
import re

from app.config import settings


FINAL_SIGNATURE = "Atenciosamente,\nEquipe Comercial"


def sanitize_proposal_text(text: str) -> str:
    """
    Sanitização FINAL e obrigatória.
    Nenhuma assinatura pessoal ou placeholder sobrevive.
    """

    if not text:
        return FINAL_SIGNATURE

    # 1) Remove QUALQUER conteúdo entre colchetes
    text = re.sub(r"\[.*?\]", "", text, flags=re.DOTALL)

    # 2) Remove tudo após qualquer variação de "Próximos passos"
    text = re.split(
        r"(\*\*\s*)?(##\s*)?próximos passos(\s*\*\*)?:?",
        text,
        flags=re.IGNORECASE
    )[0]

    # 3) Remove tentativas de assinatura ou linguagem pessoal
    forbidden_markers = [
        "atenciosamente",
        "cordialmente",
        "assinado",
        "assine",
        "aguardo",
        "estou à disposição",
        "fico à disposição",
        "qualquer dúvida",
        "entre em contato",
        "emitido em",
    ]

    lower = text.lower()
    for marker in forbidden_markers:
        idx = lower.rfind(marker)
        if idx != -1:
            text = text[:idx]
            lower = text.lower()

    # 4) Limpeza visual final
    text = text.rstrip(" \n\r-—")

    # 5) Normaliza linhas em branco
    cleaned = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(line)

    text = "\n".join(cleaned).strip()

    # 6) Encerramento neutro fixo
    if not text:
        return FINAL_SIGNATURE

    return f"{text}\n\n{FINAL_SIGNATURE}"


def _stub_generate(data: Dict[str, str]) -> str:
    """
    Stub LIMPO.
    Não contém assinatura, placeholders ou próximos passos.
    """

    service = data.get("service", "Serviço")
    client = data.get("client_name", "")

    greeting = f"Prezado(a) {client}," if client else "Prezado(a),"

    return f"""
Proposta Comercial — {service}

{greeting}

Esta proposta descreve as condições gerais para a execução do serviço solicitado,
incluindo escopo, prazos e investimento, conforme alinhado previamente.
""".strip()


def generate_proposal_text(data: Dict[str, str]) -> str:
    """
    Geração + sanitização FINAL centralizada.
    """

    mode = (settings.ai_mode or "stub").lower()

    if mode == "gpt":
        from app.services.ai_client import generate_with_gpt
        raw = generate_with_gpt(data)
    else:
        raw = _stub_generate(data)

    return sanitize_proposal_text(raw)

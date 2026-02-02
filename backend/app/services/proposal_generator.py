from __future__ import annotations

from typing import Dict
import re

from app.config import settings


def sanitize_proposal_text(text: str) -> str:
    """
    Sanitização SEM assinatura:
    - Remove colchetes [ ... ]
    - Remove qualquer trecho após 'Próximos passos'
    - Remove frases de fechamento humanas
    - NÃO adiciona assinatura
    """
    if not text:
        return ""

    t = (text or "")
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ").strip()

    # remove colchetes
    t = re.sub(r"\[.*?\]", "", t, flags=re.DOTALL).strip()

    # corta tudo após "Próximos passos"
    t = re.split(
        r"(?is)(\*\*próximos passos\*\*|##\s*próximos passos|próximos passos)\s*:?",
        t,
        maxsplit=1,
    )[0].strip()

    # remove frases humanas / assinatura acidental
    forbidden_markers = [
        "atenciosamente",
        "cordialmente",
        "assinado",
        "estou à disposição",
        "fico à disposição",
        "qualquer dúvida",
        "entre em contato",
        "aguardo retorno",
        "emitido em",
        "prezado",
        "prezada",
    ]

    lower = t.lower()
    for marker in forbidden_markers:
        idx = lower.rfind(marker)
        if idx != -1:
            t = t[:idx]
            lower = t.lower()

    # limpa quebras duplicadas
    t = re.sub(r"\n{3,}", "\n\n", t).strip()

    return t


def apply_scope_guardrails(text: str, scope: str) -> str:
    if not scope:
        return text

    if "O que está incluso:" in text or "O que NÃO está incluso:" in text:
        return text

    block = (
        "O que está incluso:\n"
        f"- {scope.strip()}\n\n"
        "O que NÃO está incluso:\n"
        "- Demandas fora do escopo descrito acima\n"
        "- Custos externos, licenças ou investimentos de terceiros\n"
        "- Solicitações fora do fluxo acordado\n\n"
        "Dependências do cliente:\n"
        "- Envio de informações e aprovações dentro do prazo acordado\n"
    )

    return f"{text}\n\n{block}"


def apply_revision_policy(text: str, tone: str) -> str:
    if "Revisões:" in text or "Política de revisões:" in text:
        return text

    revisions = 2

    blocks = {
        "formal": (
            "Política de revisões:\n"
            f"- Estão inclusas até {revisions} rodadas de ajustes dentro do escopo contratado\n"
            "- Ajustes adicionais poderão ser orçados separadamente\n"
        ),
        "amigável": (
            "Revisões:\n"
            f"- Até {revisions} rodadas de ajustes inclusas\n"
            "- Ajustes extras podem ser combinados posteriormente\n"
        ),
        "direto": (
            "Revisões:\n"
            f"- Até {revisions} rodadas de ajustes dentro do escopo\n"
            "- Demandas adicionais serão avaliadas à parte\n"
        ),
    }

    block = blocks.get((tone or "").lower(), blocks["direto"])
    return f"{text}\n\n{block}"


def apply_value_framing(text: str, price: str, objective: str) -> str:
    if not price:
        return text

    frames = {
        "alto ticket": (
            f"O investimento de {price} reflete o nível de especialização, "
            "estrutura técnica e responsabilidade envolvidos na execução."
        ),
        "fechar rápido": (
            f"O investimento proposto ({price}) contempla uma entrega objetiva "
            "com foco em implementação eficiente."
        ),
        "qualificar": (
            f"O valor de {price} corresponde ao escopo definido e poderá ser ajustado "
            "caso haja ampliação de demandas."
        ),
    }

    frame = frames.get((objective or "").lower())
    if frame and frame.lower() not in text.lower():
        return f"{text}\n\n{frame}"

    return text


def apply_smart_closing(text: str, tone: str) -> str:
    """
    Fechamento NEUTRO.
    Nada de assinatura, nada de frase humana.
    """
    closings = {
        "formal": "Após a aprovação desta proposta, serão alinhados os próximos passos para início da execução.",
        "amigável": "Com a aprovação da proposta, já é possível alinhar o início do trabalho.",
        "direto": "Com a aprovação desta proposta, a execução poderá ser iniciada.",
    }

    closing = closings.get((tone or "").lower(), closings["direto"])

    if closing.lower() in text.lower():
        return text

    return f"{text}\n\n{closing}"


def _stub_generate(data: Dict[str, str]) -> str:
    service = (data.get("service") or "Serviço").strip()

    return (
        f"Proposta Comercial\n\n"
        f"Segue proposta comercial para a prestação do serviço de {service}, "
        "contemplando escopo, prazos e condições conforme descrito a seguir."
    )


def generate_proposal_text(data: Dict[str, str]) -> str:
    mode = (settings.ai_mode or "stub").lower()

    if mode == "gpt":
        from app.services.ai_client import generate_with_gpt
        raw = generate_with_gpt(data)
    else:
        raw = _stub_generate(data)

    # ordem correta
    raw = apply_scope_guardrails(raw, data.get("scope") or "")
    raw = apply_revision_policy(raw, data.get("tone") or "")
    raw = apply_value_framing(raw, data.get("price") or "", data.get("objective") or "")
    raw = apply_smart_closing(raw, data.get("tone") or "")

    return sanitize_proposal_text(raw)

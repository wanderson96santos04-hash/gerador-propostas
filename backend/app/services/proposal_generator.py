from __future__ import annotations

from typing import Dict
import re

from app.config import settings


NEXT_STEPS_BLOCK = (
    "Próximos passos\n"
    "- Aprovação desta proposta\n"
    "- Confirmação das condições comerciais\n"
    "- Agendamento da reunião inicial"
)


def _normalize(text: str) -> str:
    t = (text or "")
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    return t


def sanitize_proposal_text(text: str) -> str:
    """
    Sanitização SEM assinatura:
    - Remove colchetes [ ... ]
    - Remove assinaturas (Atenciosamente/Cordialmente etc.) caso apareçam
    - NÃO corta o texto antes de "Próximos passos" (isso é tratado fora)
    - NÃO adiciona assinatura
    """
    if not text:
        return ""

    t = _normalize(text).strip()

    # remove colchetes / placeholders
    t = re.sub(r"\[.*?\]", "", t, flags=re.DOTALL).strip()

    # remove qualquer bloco de assinatura se aparecer (do marcador até o fim)
    # Aceita assinatura no início de uma linha OU no início do texto
    sig_pattern = re.compile(
        r"(?is)(?:^|\n)\s*(atenciosamente|cordialmente|assinado|att\.?)\b.*$",
        re.MULTILINE,
    )
    t = re.sub(sig_pattern, "", t).strip()

    # limpa pontas comuns
    t = t.rstrip(" \n\r-—•")

    # limpa quebras duplicadas
    t = re.sub(r"\n{3,}", "\n\n", t).strip()

    return t


def remove_next_steps_and_below(text: str) -> str:
    """
    Remove qualquer 'Próximos passos' existente e tudo que vem depois,
    pra evitar duplicar ou ficar '9.' solto no final.
    """
    if not text:
        return ""

    t = _normalize(text)

    # pega "Próximos passos" com variações (com numeração, markdown, etc.)
    # e remove tudo dali pra baixo (aceita início de linha OU início do texto)
    pattern = re.compile(
        r"(?is)(?:^|\n)\s*(\d+\.\s*)?(\*\*)?(##\s*)?próximos passos(\*\*)?\s*:?.*$",
        re.MULTILINE,
    )
    t = re.sub(pattern, "", t).strip()

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
    Fechamento NEUTRO (sem assinatura).
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


def apply_next_steps(text: str) -> str:
    """
    Garante o final padrão com Próximos passos (sem duplicação).
    """
    base = remove_next_steps_and_below(text)
    base = sanitize_proposal_text(base)

    if not base:
        return NEXT_STEPS_BLOCK

    return f"{base}\n\n{NEXT_STEPS_BLOCK}"


def _stub_generate(data: Dict[str, str]) -> str:
    service = (data.get("service") or "Serviço").strip()

    return (
        "Proposta Comercial\n\n"
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

    # ordem correta (mantém o que já funciona)
    raw = apply_scope_guardrails(raw, data.get("scope") or "")
    raw = apply_revision_policy(raw, data.get("tone") or "")
    raw = apply_value_framing(raw, data.get("price") or "", data.get("objective") or "")
    raw = apply_smart_closing(raw, data.get("tone") or "")

    # FINAL: força Próximos passos padrão e elimina duplicações
    return apply_next_steps(raw)

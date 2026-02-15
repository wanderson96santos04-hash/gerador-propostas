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

# ✅ Bloco de autoridade (pedido)
AUTHORITY_BLOCK = (
    "Com experiência em criação de peças estratégicas voltadas para posicionamento e conversão, "
    "desenvolvo criativos que unem estética e resultado."
)


def _normalize(text: str) -> str:
    t = (text or "")
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    t = t.replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\u2060", "")
    return t


def sanitize_proposal_text(text: str) -> str:
    if not text:
        return ""

    t = _normalize(text).strip()

    t = re.sub(r"\[.*?\]", "", t, flags=re.DOTALL).strip()

    sig_pattern = re.compile(
        r"(?is)(?:^|\n)\s*(atenciosamente|cordialmente|assinado|att\.?)\b.*$",
        re.MULTILINE,
    )
    t = re.sub(sig_pattern, "", t).strip()

    t = t.rstrip(" \n\r-—•")
    t = re.sub(r"\n{3,}", "\n\n", t).strip()

    return t


def remove_next_steps_and_below(text: str) -> str:
    if not text:
        return ""

    t = _normalize(text)

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

    frame = (
        f"O investimento mensal de {price} está diretamente relacionado "
        "à responsabilidade estratégica, gestão contínua e acompanhamento próximo "
        "necessários para a execução consistente do escopo proposto."
    )

    if frame.lower() not in text.lower():
        return f"{text}\n\n{frame}"

    return text


def apply_smart_closing(text: str, tone: str) -> str:
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
    base = remove_next_steps_and_below(text)
    base = sanitize_proposal_text(base)

    if not base:
        return NEXT_STEPS_BLOCK

    return f"{base}\n\n{NEXT_STEPS_BLOCK}"


def _stub_generate(data: Dict[str, str]) -> str:
    service = (data.get("service") or "Serviço").strip()

    return (
        "Proposta Comercial\n\n"
        f"Esta proposta foi elaborada para estruturar e profissionalizar a prestação do serviço de {service}, "
        "com foco em clareza de escopo, previsibilidade operacional e responsabilidade sobre a entrega."
    )


def apply_authority_block(text: str) -> str:
    """
    Insere o bloco de autoridade antes do 'Diagnóstico e contexto' (ou variações),
    sem alterar o restante do conteúdo.

    Regras:
    - Se já existir o texto do bloco, não duplica.
    - Se encontrar o título 'Diagnóstico e contexto' (ou variações), injeta imediatamente antes.
    - Se não encontrar, adiciona após a abertura (primeiro parágrafo) de forma segura.
    """
    if not text:
        return text

    if AUTHORITY_BLOCK.lower() in text.lower():
        return text

    t = _normalize(text)

    # tenta achar o heading "Diagnóstico e contexto" (flexível)
    pattern = re.compile(
        r"(?im)^(?:\s*(?:##\s*)?)diagn[oó]stico\s+e\s+contexto\s*$"
    )

    m = pattern.search(t)
    if m:
        insert_at = m.start()
        before = t[:insert_at].rstrip()
        after = t[insert_at:].lstrip("\n")
        return f"{before}\n\n{AUTHORITY_BLOCK}\n\n{after}"

    # fallback: após o primeiro bloco (primeiro parágrafo)
    parts = re.split(r"\n\s*\n", t, maxsplit=1)
    if len(parts) == 2:
        first, rest = parts[0].rstrip(), parts[1].lstrip()
        return f"{first}\n\n{AUTHORITY_BLOCK}\n\n{rest}"

    # fallback final: só append
    return f"{t.rstrip()}\n\n{AUTHORITY_BLOCK}"


def generate_proposal_text(data: Dict[str, str]) -> str:
    mode = (settings.ai_mode or "stub").lower()

    if mode == "gpt":
        from app.services.ai_client import generate_with_gpt
        raw = generate_with_gpt(data)
    else:
        raw = _stub_generate(data)

    # ✅ adiciona bloco de autoridade (sem mexer no resto)
    raw = apply_authority_block(raw)

    # Ajuste CIRÚRGICO do objetivo (somente se aparecer a forma genérica)
    raw = re.sub(
        r"O objetivo é .*?\.",
        "O objetivo deste serviço é assumir a responsabilidade estratégica e operacional da entrega, "
        "transformando investimento em ações executáveis e resultados mensuráveis.",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )

    raw = apply_scope_guardrails(raw, data.get("scope") or "")
    raw = apply_revision_policy(raw, data.get("tone") or "")
    raw = apply_value_framing(raw, data.get("price") or "", data.get("objective") or "")
    raw = apply_smart_closing(raw, data.get("tone") or "")

    return apply_next_steps(raw)

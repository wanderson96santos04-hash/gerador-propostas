from __future__ import annotations

from typing import Dict
import re

from app.config import settings


FINAL_SIGNATURE = "Atenciosamente,\nEquipe Comercial"


def sanitize_proposal_text(text: str) -> str:
    if not text:
        return FINAL_SIGNATURE

    text = re.sub(r"\[.*?\]", "", text, flags=re.DOTALL)

    text = re.split(
        r"(\*\*\s*)?(##\s*)?próximos passos(\s*\*\*)?:?",
        text,
        flags=re.IGNORECASE
    )[0]

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

    text = text.rstrip(" \n\r-—")

    cleaned = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(line)

    text = "\n".join(cleaned).strip()

    if not text:
        return FINAL_SIGNATURE

    return f"{text}\n\n{FINAL_SIGNATURE}"


def apply_scope_guardrails(text: str, scope: str) -> str:
    if not scope:
        return text

    if "O que NÃO está incluso:" in text or "O que está incluso:" in text:
        return text

    block = (
        "O que está incluso:\n"
        f"- {scope.strip()}\n\n"
        "O que NÃO está incluso:\n"
        "- Demandas fora do escopo descrito acima\n"
        "- Custos externos, licenças ou investimentos de terceiros\n"
        "- Solicitações urgentes fora do fluxo acordado\n\n"
        "Dependências do cliente:\n"
        "- Envio de informações e aprovações dentro do prazo para não impactar a entrega\n"
    )

    return f"{text}\n\n{block}"


def apply_revision_policy(text: str, service: str, tone: str) -> str:
    """
    Inteligência de REVISÕES:
    - Define um limite padrão (evita abuso)
    - Define regra de extra (evita “escopo infinito”)
    - Linguagem ajustada conforme tom
    """

    if "Revisões:" in text or "Política de revisões:" in text:
        return text

    # regra simples e segura
    default_revisions = 2

    lines = {
        "direto": (
            f"Revisões:\n"
            f"- Até {default_revisions} rodadas de ajustes dentro do escopo\n"
            f"- Ajustes adicionais serão orçados à parte\n"
        ),
        "formal": (
            f"Política de revisões:\n"
            f"- Estão inclusas até {default_revisions} rodadas de ajustes, desde que dentro do escopo contratado\n"
            f"- Solicitações adicionais serão avaliadas e, se necessário, orçadas separadamente\n"
        ),
        "amigável": (
            f"Revisões:\n"
            f"- Até {default_revisions} ajustes inclusos 😊\n"
            f"- Se passar disso, a gente combina um valor extra antes de continuar\n"
        ),
    }

    tone_key = (tone or "").lower()
    block = lines.get(tone_key, lines["direto"])

    return f"{text}\n\n{block}"


def apply_value_framing(text: str, price: str, objective: str) -> str:
    if not price:
        return text

    frames = {
        "fechar rápido": (
            f"O investimento proposto ({price}) contempla uma entrega objetiva "
            f"e focada em resultado imediato."
        ),
        "alto ticket": (
            f"O investimento de {price} reflete um nível elevado de especialização, "
            f"atenção estratégica e impacto direto nos resultados do negócio."
        ),
        "qualificar": (
            f"O valor de {price} corresponde ao escopo definido e pode ser ajustado "
            f"conforme necessidades adicionais."
        ),
    }

    frame = frames.get((objective or "").lower())
    if not frame:
        return text

    if frame.lower() in text.lower():
        return text

    return f"{text}\n\n{frame}"


def apply_smart_closing(text: str, tone: str) -> str:
    closings = {
        "direto": (
            "Se estiver de acordo, podemos iniciar imediatamente após a aprovação desta proposta."
        ),
        "formal": (
            "Permanecemos à disposição para quaisquer esclarecimentos e aguardamos a validação para prosseguirmos."
        ),
        "amigável": (
            "Ficando tudo ok, é só me dar um retorno para começarmos 😊"
        ),
    }

    closing = closings.get((tone or "").lower(), closings["direto"])

    if closing.lower() in text.lower():
        return text

    return f"{text}\n\n{closing}"


def _stub_generate(data: Dict[str, str]) -> str:
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
    mode = (settings.ai_mode or "stub").lower()

    if mode == "gpt":
        from app.services.ai_client import generate_with_gpt
        raw = generate_with_gpt(data)
    else:
        raw = _stub_generate(data)

    # 🔥 INTELIGÊNCIA (ordem importa)
    raw = apply_scope_guardrails(
        raw,
        data.get("scope"),
    )

    raw = apply_revision_policy(
        raw,
        data.get("service"),
        data.get("tone"),
    )

    raw = apply_value_framing(
        raw,
        data.get("price"),
        data.get("objective"),
    )

    raw = apply_smart_closing(
        raw,
        data.get("tone"),
    )

    return sanitize_proposal_text(raw)

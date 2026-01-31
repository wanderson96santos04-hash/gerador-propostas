from __future__ import annotations

from datetime import datetime
from typing import Dict

from app.config import settings


def _normalize_tone(tone: str) -> str:
    t = (tone or "").strip().lower()
    if t in ("formal", "direto", "amigável", "amigavel"):
        return "amigável" if t == "amigavel" else t
    return "direto"


def _normalize_objective(obj: str) -> str:
    o = (obj or "").strip().lower()
    if o in ("fechar rápido", "fechar rapido", "qualificar", "alto ticket"):
        return "fechar rápido" if o == "fechar rapido" else o
    return "fechar rápido"


def _money_hint(price: str) -> str:
    p = (price or "").strip()
    if not p:
        return "a combinar"
    return p


def _stub_generate(data: Dict[str, str]) -> str:
    """
    Gerador local (sem IA). Produz uma proposta “boa o suficiente” usando regras e templates.
    Assinatura final é neutra (white-label): 'Equipe Comercial'.
    """
    client = data["client_name"]
    service = data["service"]
    scope = data.get("scope", "")
    deadline = data.get("deadline", "")
    price = _money_hint(data.get("price", ""))
    payment = data.get("payment_terms", "")
    differentiators = data.get("differentiators", "")
    warranty = data.get("warranty_support", "")
    tone = _normalize_tone(data.get("tone", ""))
    objective = _normalize_objective(data.get("objective", ""))

    # Ajustes de linguagem por tom
    if tone == "formal":
        greeting = f"Prezado(a) {client},"
        closing = "Permaneço à disposição para quaisquer esclarecimentos."
        call_to_action = "Caso aprove, posso iniciar imediatamente após a confirmação."
    elif tone == "amigável":
        greeting = f"Olá, {client}!"
        closing = "Se quiser, eu te explico tudo rapidinho e ajusto o que precisar 🙂"
        call_to_action = "Se fizer sentido pra você, eu já deixo tudo encaminhado pra começar."
    else:  # direto
        greeting = f"{client},"
        closing = "Se estiver ok, seguimos."
        call_to_action = "Me confirme e eu inicio."

    # Ajuste por objetivo
    if objective == "alto ticket":
        angle = (
            "O foco aqui é entregar um resultado acima da média, com atenção a detalhes, qualidade e previsibilidade."
        )
        next_step = "Próximo passo: alinhamos um briefing de 15 minutos e eu envio o cronograma final."
    elif objective == "qualificar":
        angle = (
            "Antes de fechar, proponho um alinhamento rápido para confirmar prioridade, restrições e expectativas."
        )
        next_step = "Próximo passo: você responde 3 perguntas-chave e eu ajusto a proposta final."
    else:  # fechar rápido
        angle = "Proposta objetiva para você aprovar rápido e a gente começar sem enrolação."
        next_step = "Próximo passo: aprovou, eu inicio e te envio o primeiro retorno dentro do prazo combinado."

    # Campos opcionais
    scope_block = f"\n\n**Escopo**\n{scope}" if scope else ""
    payment_block = f"\n\n**Condições de pagamento**\n{payment}" if payment else ""
    diff_block = f"\n\n**Diferenciais**\n{differentiators}" if differentiators else ""
    warranty_block = f"\n\n**Garantia / Suporte**\n{warranty}" if warranty else ""

    deadline_line = f"{deadline}" if deadline else "a combinar"

    text = f"""# Proposta de Serviço — {service}

{greeting}

Segue uma proposta para **{service}**.

{angle}

## Resumo
- **Cliente:** {client}
- **Serviço:** {service}
- **Prazo:** {deadline_line}
- **Investimento:** {price}

{scope_block}

## Entregáveis (padrão)
- Planejamento e definição do que será feito
- Execução do serviço conforme o escopo
- Revisões alinhadas (para garantir que fique como você quer)
- Entrega final organizada e pronta para uso

{payment_block}
{diff_block}
{warranty_block}

## Prazos e início
- Início: após confirmação/aceite
- Prazo estimado: **{deadline_line}**

## Investimento
- Valor: **{price}**

## Próximos passos
{next_step}

{call_to_action}

{closing}

Atenciosamente,

Equipe Comercial
"""
    return text.strip()


def generate_proposal_text(data: Dict[str, str]) -> str:
    """
    Decide se usa stub (grátis/local) ou modo GPT por variável de ambiente.
    AI_MODE=stub (padrão) ou AI_MODE=gpt
    """
    mode = (settings.ai_mode or "stub").strip().lower()

    if mode == "gpt":
        # Import lazy pra não quebrar o MVP se você não configurar API.
        from app.services.ai_client import generate_with_gpt

        return generate_with_gpt(data)

    return _stub_generate(data)

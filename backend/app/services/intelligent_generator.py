# backend/app/services/intelligent_generator.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List
import re

from app.templates.proposal_catalog import TEMPLATES, PROPOSAL_BLOCKS, SALES_COPY


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


def _sanitize_no_signature(text: str) -> str:
    """
    Sanitização mínima:
    - remove assinatura/fechamento (Atenciosamente/Cordialmente/Att.) se aparecer
    - NÃO adiciona assinatura
    """
    if not text:
        return ""

    t = _normalize(text).strip()

    sig_pattern = re.compile(
        r"(?is)(?:^|\n)\s*(atenciosamente|cordialmente|assinado|att\.?)\b.*$",
        re.MULTILINE,
    )
    t = re.sub(sig_pattern, "", t).strip()

    t = t.rstrip(" \n\r-—•")
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


def _remove_next_steps_and_below(text: str) -> str:
    """
    Remove qualquer 'Próximos passos' existente e tudo que vem depois
    (evita duplicação e garante o padrão no final).
    """
    if not text:
        return ""

    t = _normalize(text)

    pattern = re.compile(
        r"(?is)(?:^|\n)\s*(\d+\.\s*)?(\*\*)?(##\s*)?próximos passos(\*\*)?\s*:?.*$",
        re.MULTILINE,
    )
    t = re.sub(pattern, "", t).strip()
    return t


def _apply_next_steps(text: str) -> str:
    """
    Força final padrão:
    - remove assinatura
    - remove qualquer Próximos passos anterior
    - termina exatamente no bloco obrigatório
    """
    base = _remove_next_steps_and_below(text)
    base = _sanitize_no_signature(base)

    if not base:
        return NEXT_STEPS_BLOCK

    return f"{base}\n\n{NEXT_STEPS_BLOCK}"


def _fmt_list(items: List[str], ctx: Dict[str, Any]) -> List[str]:
    out = []
    for it in items:
        out.append(it.format(**ctx))
    return out


def _fmt_text(text: str, ctx: Dict[str, Any]) -> str:
    return text.format(**ctx)


def generate_intelligent_proposal(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload esperado:
    {
      "template_id": "social_marketing",
      "subtype": "trafego_pago",
      "tone": "premium",
      "ctx": {...}  # parametros para preencher {placeholders}
    }
    """
    template_id = payload["template_id"]
    subtype = payload.get("subtype")
    tone = payload.get("tone", "direto")
    ctx = payload.get("ctx", {})

    tpl = TEMPLATES.get(template_id)
    if not tpl:
        raise ValueError("template_id inválido")

    st = tpl["subtype_content"].get(subtype) if subtype else None
    if not st:
        # fallback: pega o primeiro subtype disponível
        first_sub = tpl["subtypes"][0]
        st = tpl["subtype_content"].get(first_sub) or {}
        subtype = first_sub

    defaults = tpl.get("defaults", {})
    # garante defaults no ctx (sem sobrescrever o que usuário enviou)
    for k, v in defaults.items():
        ctx.setdefault(k, v)

    # placeholders que sempre ajudam o copy
    ctx.setdefault("dor_principal", "organizar e executar com previsibilidade")
    ctx.setdefault("resultado", "um resultado claro com entregas e prazos definidos")
    ctx.setdefault("materiais_acessos", "materiais e acessos necessários")
    ctx.setdefault("data_inicio", "___/___/____")
    ctx.setdefault("data_aprovacao", "___/___/____")
    ctx.setdefault("proxima_janela", "___/___/____")
    ctx.setdefault("data_materiais", "___/___/____")

    escopo = st.get("escopo", "").format(**ctx)
    entregaveis = _fmt_list(st.get("entregaveis", []), ctx)
    clausulas = _fmt_list(st.get("clausulas", []), ctx)

    copy = SALES_COPY.get(tone, SALES_COPY["direto"])
    sales_section = {
        "tone": tone,
        "intro": _sanitize_no_signature(_fmt_text(copy["intro"], ctx)),
        "valor": _sanitize_no_signature(_fmt_text(copy["valor"], ctx)),
        "proximo_passo": _sanitize_no_signature(_fmt_text(copy["proximo_passo"], ctx)),
        "urgencia": _sanitize_no_signature(_fmt_text(copy["urgencia"], ctx)),
        # fechamento deve SEMPRE terminar no bloco padrão (sem assinatura)
        "fechamento": _apply_next_steps(_fmt_text(copy["fechamento"], ctx)),
    }

    blocks_keys = tpl.get("recommended_blocks", [])
    blocks = []
    for key in blocks_keys:
        b = PROPOSAL_BLOCKS[key]
        blocks.append({
            "key": key,
            "title": b["title"],
            "text": _sanitize_no_signature(_fmt_text(b["text"], ctx)),
        })

    # JSON final (isso aqui você pluga no seu gerador de PDF)
    return {
        "template_id": template_id,
        "template_name": tpl["name"],
        "subtype": subtype,
        "escopo": escopo,
        "entregaveis": entregaveis,
        "clausulas": clausulas,
        "sales_copy": sales_section,
        "blocks": blocks,
        "meta": {
            "revisoes_por_entrega": ctx.get("revisoes_por_entrega"),
            "sla_feedback_dias_uteis": ctx.get("sla_feedback_dias_uteis"),
            "validade_proposta_dias": ctx.get("validade_proposta_dias"),
        }
    }

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

# ✅ Bloco fixo (para todos os serviços) — precisa existir no pipeline inteligente também,
# pois o PDF está sendo alimentado por este gerador (direta ou indiretamente).
AUTHORITY_BLOCK = (
    "Autoridade\n"
    "Com experiência em criação de peças estratégicas voltadas para posicionamento e conversão, "
    "desenvolvo criativos que unem estética e resultado."
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


def _apply_authority_block_before_diagnosis(blocks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    ✅ Insere o bloco de Autoridade IMEDIATAMENTE antes do bloco "Diagnóstico e contexto".
    Regras:
    - Insere uma única vez.
    - Só insere se existir Diagnóstico e contexto (com variações).
    - Se não existir, não insere em lugar nenhum.
    - Não duplica (por título OU pelo texto do bloco fixo).

    Teste mental (sem framework):
    1) Gere proposta via fluxo inteligente (template/subtype).
    2) Gere/baixe PDF.
    3) Confirme que no conteúdo aparece:
       "... \n\nAutoridade\n[texto]\n\nDiagnóstico e contexto\n..."
       e que "Autoridade" aparece apenas 1 vez.
    4) Gere de novo (ou salve histórico/regenere) e confirme que não duplicou.
    """
    if not blocks:
        return blocks

    # Deduplicação segura
    authority_text_key = _normalize(AUTHORITY_BLOCK).strip().lower()
    for b in blocks:
        title = (b.get("title") or "").strip().lower()
        text = (b.get("text") or "").strip().lower()
        if title == "autoridade":
            return blocks
        if authority_text_key and authority_text_key in (f"{title}\n{text}"):
            return blocks
        # trava extra (frase-chave) — útil caso o título venha diferente
        if "criação de peças estratégicas" in text:
            return blocks

    # Encontra Diagnóstico e contexto (variações comuns)
    diag_re = re.compile(r"(?i)\bdiagn[oó]stico\s*(?:e|&)\s*contexto\b")
    diag_idx = None
    for i, b in enumerate(blocks):
        title = (b.get("title") or "").strip()
        if title and diag_re.search(title):
            diag_idx = i
            break

    if diag_idx is None:
        return blocks  # regra: não inventar lugar

    authority_block = {
        "key": "authority_block",  # key interna; não depende do catalog
        "title": "Autoridade",
        "text": _sanitize_no_signature(AUTHORITY_BLOCK),
    }

    return blocks[:diag_idx] + [authority_block] + blocks[diag_idx:]


def _build_plaintext_from_intelligent(result: Dict[str, Any]) -> str:
    """
    Constrói uma string única (proposal_text) a partir do JSON inteligente.
    - NÃO muda o fluxo existente: só adiciona um campo opcional para facilitar plugar no PDF.
    - Mantém headings simples (título em linha) e espaçamento consistente.
    """
    parts: List[str] = []

    template_name = (result.get("template_name") or "").strip()
    subtype = (result.get("subtype") or "").strip()
    if template_name:
        parts.append("Proposta Comercial")
        parts.append("")
        # linha curta pra contextualizar sem inventar dados
        if subtype:
            parts.append(f"Template: {template_name} — {subtype}")
        else:
            parts.append(f"Template: {template_name}")
        parts.append("")

    sales = result.get("sales_copy") or {}
    # só inclui campos que existirem
    for key, title in [
        ("intro", "Introdução"),
        ("valor", "Valor"),
        ("proximo_passo", "Próximo passo"),
        ("urgencia", "Urgência"),
    ]:
        txt = (sales.get(key) or "").strip()
        if txt:
            parts.append(title)
            parts.append(txt)
            parts.append("")

    blocks = result.get("blocks") or []
    for b in blocks:
        title = (b.get("title") or "").strip()
        text = (b.get("text") or "").strip()
        if title:
            parts.append(title)
        if text:
            parts.append(text)
        parts.append("")

    # fechamento já termina em NEXT_STEPS_BLOCK via _apply_next_steps
    fechamento = (sales.get("fechamento") or "").strip()
    if fechamento:
        parts.append("Fechamento")
        parts.append(fechamento)
        parts.append("")

    # normaliza quebras
    out = "\n".join(parts).strip()
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


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
    blocks: List[Dict[str, str]] = []
    for key in blocks_keys:
        b = PROPOSAL_BLOCKS[key]
        blocks.append({
            "key": key,
            "title": b["title"],
            "text": _sanitize_no_signature(_fmt_text(b["text"], ctx)),
        })

    # ✅ Inserção do bloco de Autoridade no pipeline inteligente (antes do Diagnóstico)
    blocks = _apply_authority_block_before_diagnosis(blocks)

    # JSON final (isso aqui você pluga no seu gerador de PDF)
    result = {
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

    # ✅ Campo opcional (não quebra nada): facilita alimentar o PDF com 1 string consistente
    result["proposal_text"] = _build_plaintext_from_intelligent(result)

    return result

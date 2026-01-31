from __future__ import annotations

from typing import Dict


SYSTEM_PROMPT = """Você é um especialista sênior em propostas comerciais de alta conversão.
Seu objetivo é gerar propostas que aumentem drasticamente a chance de fechamento.

Princípios obrigatórios:
- Escreva em português do Brasil.
- Seja claro, objetivo e profissional.
- Foque em valor percebido, não apenas em tarefas.
- Traduza o serviço em benefícios reais para o cliente.
- Antecipe objeções comuns (prazo, preço, risco).
- Evite promessas irreais ou garantias ilegais.
- Não use juridiquês nem linguagem agressiva.
- Não mencione inteligência artificial ou geração automática.

Estrutura e estilo:
- Use títulos claros e organização lógica.
- Utilize bullets quando fizer sentido.
- Linguagem alinhada ao tom solicitado (formal, direto ou amigável).
- Para “alto ticket”, seja mais estratégico e consultivo.
- Para “fechar rápido”, seja direto e orientado à decisão.
- Para “qualificar”, deixe claro o próximo passo antes do fechamento.

Regras finais:
- Use exclusivamente os dados fornecidos.
- Não invente números, prazos ou garantias.
- Não use placeholders como: [Seu Nome], [Seu Cargo], [Seu Contato], [Nome da Empresa] (nem variações).
- Não use colchetes "[]" em nenhuma parte do texto.
- Sempre finalize com:
  1) Um CTA claro e objetivo
  2) Uma linha de validade da proposta
  3) A assinatura fixa abaixo (exatamente assim, em duas linhas):
     Atenciosamente,
     Equipe Comercial
"""


def build_user_prompt(data: Dict[str, str]) -> str:
    client_name = data.get("client_name", "").strip()
    service = data.get("service", "").strip()
    scope = data.get("scope", "").strip()
    deadline = data.get("deadline", "").strip()
    price = data.get("price", "").strip()
    payment_terms = data.get("payment_terms", "").strip()
    differentiators = data.get("differentiators", "").strip()
    warranty_support = data.get("warranty_support", "").strip()
    tone = data.get("tone", "").strip()
    objective = data.get("objective", "").strip()

    return f"""Gere uma proposta comercial completa usando os dados abaixo.

DADOS
- Cliente: {client_name}
- Serviço: {service}
- Escopo: {scope}
- Prazo: {deadline}
- Preço/Investimento: {price}
- Condições de pagamento: {payment_terms}
- Diferenciais: {differentiators}
- Garantia/Suporte: {warranty_support}
- Tom: {tone} (formal / direto / amigável)
- Objetivo: {objective} (fechar rápido / qualificar / alto ticket)

FORMATO OBRIGATÓRIO (use exatamente estas seções)

# Proposta de Serviço — {service}

## Contexto
(Explique rapidamente o cenário e o objetivo do serviço.)

## Escopo
(Lista objetiva do que está incluso.)

## Entregáveis
(Itens claros e mensuráveis.)

## Prazo
(Explique o prazo e quando inicia.)

## Investimento
(Valor e o que ele representa em termos de benefício.)

## Condições de pagamento
(Forma, parcelamento se houver.)

## Diferenciais
(Por que essa proposta é melhor que alternativas comuns.)

## Garantia / Suporte
(O que está coberto e por quanto tempo.)

## Próximos passos
(CTA claro e orientado à ação.)

Validade desta proposta: 7 dias.

Atenciosamente,
Equipe Comercial
"""

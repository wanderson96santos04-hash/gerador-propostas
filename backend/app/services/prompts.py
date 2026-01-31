from __future__ import annotations

from typing import Dict


SYSTEM_PROMPT = """Você é um especialista sênior em propostas comerciais profissionais B2B.

Objetivo:
Gerar propostas claras, profissionais e orientadas à decisão, aumentando a taxa de fechamento.

Princípios obrigatórios:
- Escreva em português do Brasil.
- Linguagem profissional, neutra e segura.
- Foque em valor percebido e benefícios reais.
- Evite promessas irreais ou garantias ilegais.
- Não use juridiquês nem linguagem agressiva.
- Não utilize linguagem em primeira pessoa.
- Não mencione tecnologia, automação ou inteligência artificial.

Regras rígidas:
- Utilize exclusivamente os dados fornecidos.
- Não invente informações, números, prazos ou garantias.
- Não use placeholders como: Seu Nome, Seu Cargo, Seu Contato, Nome da Empresa (nem variações).
- Não utilize colchetes [] em nenhuma parte do texto.
- Não inclua nomes de pessoas, cargos, telefones ou e-mails.
- O encerramento deve seguir exatamente o formato definido pelo prompt do usuário, sem adicionar ou alterar nada.
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

    return f"""Gere uma proposta comercial completa utilizando exclusivamente as informações abaixo.

DADOS
Cliente: {client_name}
Serviço: {service}
Escopo: {scope}
Prazo: {deadline}
Investimento: {price}
Condições de pagamento: {payment_terms}
Diferenciais: {differentiators}
Garantia / Suporte: {warranty_support}
Tom: {tone}
Objetivo: {objective}

FORMATO OBRIGATÓRIO

# Proposta de Serviço — {service}

## Contexto
Apresente brevemente o cenário e o objetivo do serviço.

## Escopo
Liste de forma objetiva o que está incluso.

## Entregáveis
Descreva entregáveis claros e mensuráveis.

## Prazo
Explique o prazo e quando se inicia após a aprovação.

## Investimento
Apresente o valor e o que ele representa em termos de benefício.

## Condições de pagamento
Informe as condições acordadas.

## Diferenciais
Explique por que esta proposta se destaca em relação a alternativas comuns.

## Garantia / Suporte
Descreva o suporte oferecido e o período de cobertura.

## Próximos passos
Para dar início ao projeto, é necessário confirmar a aprovação desta proposta.
Após o aceite, as etapas de execução seguirão conforme o escopo, prazos e condições estabelecidos neste documento.
Caso seja necessário algum ajuste pontual antes da validação final, a proposta poderá ser revisada para alinhamento.

Validade desta proposta: 7 dias.

Atenciosamente,
Equipe Comercial
"""

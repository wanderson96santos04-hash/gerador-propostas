# backend/app/templates/proposal_catalog.py
from __future__ import annotations

PROPOSAL_BLOCKS = {
    "inclui": {
        "title": "O que está incluso",
        "text": (
            "• Planejamento + execução conforme escopo\n"
            "• Entregas nos formatos combinados\n"
            "• Alinhamentos conforme rotina definida\n"
            "• Revisões dentro do limite descrito\n"
        ),
    },
    "nao_inclui": {
        "title": "O que NÃO está incluso",
        "text": (
            "• Itens não descritos no escopo/entregáveis\n"
            "• Custos de terceiros (mídia paga, hospedagem, domínio, ferramentas, materiais)\n"
            "• Produção presencial (foto/vídeo) se não contratada\n"
            "• Retrabalho por mudança de direção após aprovações\n"
        ),
    },
    "processo": {
        "title": "Processo de trabalho",
        "text": (
            "1) Kickoff e alinhamento do objetivo\n"
            "2) Coleta de materiais e acessos (checklist)\n"
            "3) Primeira entrega / primeira etapa\n"
            "4) Revisões (dentro do limite)\n"
            "5) Entrega final e orientações\n"
        ),
    },
    "prazo_dependencias": {
        "title": "Prazo e dependências do cliente",
        "text": (
            "• Envio de materiais/acessos: até {data_materiais}\n"
            "• Feedback por rodada: até {sla_feedback} dias úteis\n"
            "• Atrasos no envio de materiais/feedback movem o cronograma automaticamente.\n"
        ),
    },
    "confidencialidade": {
        "title": "Confidencialidade",
        "text": (
            "Informações, acessos e materiais trocados serão usados apenas para execução do projeto. "
            "Não divulgarei dados sensíveis sem autorização por escrito."
        ),
    },
    "cancelamento": {
        "title": "Cancelamento e reembolso",
        "text": (
            "Se o cliente cancelar após início, cobra-se o proporcional do que já foi executado + custos comprometidos. "
            "Se eu precisar cancelar por motivo justificado, devolvo o valor do que não foi executado."
        ),
    },
}

SALES_COPY = {
    "direto": {
        "intro": "Preparei uma proposta simples e clara pra resolver {dor_principal} e entregar {resultado}.",
        "valor": "O foco aqui é tirar do caminho o que trava e colocar um processo que gera entrega contínua — sem retrabalho.",
        "proximo_passo": "Se fizer sentido, eu inicio assim que você confirmar e enviar {materiais_acessos}.",
        "urgencia": "Consigo começar até {data_inicio} se aprovar até {data_aprovacao}.",
        "fechamento": "Posso seguir com essa opção? Se sim, me confirme por aqui e já te envio o checklist de início.",
    },
    "premium": {
        "intro": "Estruturei esta proposta para entregar uma experiência completa — com método, previsibilidade e padrão de qualidade.",
        "valor": "Você não está contratando entregas soltas. Está contratando um processo que reduz risco, evita ruído e acelera resultado.",
        "proximo_passo": "Com a aprovação, iniciamos com um kickoff rápido e em seguida você recebe o cronograma e os primeiros entregáveis.",
        "urgencia": "Minha agenda comporta início até {data_inicio}. Depois disso, a próxima janela é {proxima_janela}.",
        "fechamento": "Se estiver alinhado com o que você busca, me sinalize a aprovação e eu reservo a janela de execução.",
    },
    "amigavel": {
        "intro": "Montei uma proposta bem prática pra gente chegar em {resultado} sem complicação.",
        "valor": "Eu vou te guiando no processo — e você sempre vai saber o que está acontecendo e o que vem depois.",
        "proximo_passo": "Aprovando, você me manda {materiais_acessos} e eu já começo a primeira etapa.",
        "urgencia": "Se aprovar até {data_aprovacao}, dá pra começar {data_inicio} e manter o prazo total.",
        "fechamento": "Curtiu esse formato? Quer que eu siga com essa opção ou prefere ajustar algum ponto?",
    },
}

TEMPLATES = {
    "social_marketing": {
        "name": "Social / Tráfego / Design / Sites",
        "subtypes": ["social_media", "trafego_pago", "design", "sites"],
        "defaults": {
            "prazo_inicio_dias_uteis": 3,
            "revisoes_por_entrega": 2,
            "sla_feedback_dias_uteis": 2,
            "validade_proposta_dias": 7,
        },
        "subtype_content": {
            "social_media": {
                "escopo": "Planejamento e execução do conteúdo para redes sociais, com rotina de alinhamento e entregas previsíveis.",
                "entregaveis": [
                    "Calendário editorial (mensal)",
                    "Criação de {qtd_posts} posts/mês (feed)",
                    "Criação de {qtd_stories_semana} stories/semana",
                    "Copy e legendas",
                    "Diretrizes de design (padrão visual)",
                    "Relatório mensal (métricas + insights)",
                ],
                "clausulas": [
                    "Materiais e informações do produto são responsabilidade do cliente.",
                    "Atrasos de feedback movem o cronograma.",
                ],
            },
            "trafego_pago": {
                "escopo": "Estruturação e gestão de campanhas, com otimizações contínuas e relatório.",
                "entregaveis": [
                    "Setup e estrutura de campanhas",
                    "Criação de {qtd_variacoes_anuncios} variações de anúncios",
                    "Otimizações semanais",
                    "Relatório {frequencia_relatorio}",
                    "Pixel/Tags e eventos (se aplicável)",
                ],
                "clausulas": [
                    "Investimento em mídia paga não está incluso (por conta do cliente).",
                    "Não há garantia de métricas específicas: resultados dependem de oferta, público, verba e página.",
                ],
            },
            "design": {
                "escopo": "Criação de peças e criativos com padrão visual consistente e entregas prontas para uso.",
                "entregaveis": [
                    "{qtd_pecas} peças (banners/criativos/carrosséis)",
                    "1 direção visual + variações",
                    "Arquivos finais nos formatos combinados",
                ],
                "clausulas": [
                    "Mudanças de direção após aprovações podem gerar aditivo.",
                ],
            },
            "sites": {
                "escopo": "Criação de landing page/site com foco em clareza, conversão e base técnica organizada.",
                "entregaveis": [
                    "Wireframe + layout",
                    "Desenvolvimento {tipo_site}",
                    "Responsivo + SEO básico",
                    "Integrações (formulário/WhatsApp/Pixel)",
                ],
                "clausulas": [
                    "Hospedagem/domínio/ferramentas são por conta do cliente (se não contratado).",
                ],
            },
        },
        "recommended_blocks": ["inclui", "nao_inclui", "processo", "prazo_dependencias", "confidencialidade", "cancelamento"],
    },

    "obras_tecnico": {
        "name": "Obras / Manutenção / Serviços Técnicos",
        "subtypes": ["obra", "manutencao", "instalacao"],
        "defaults": {
            "revisoes_por_entrega": 0,
            "sla_feedback_dias_uteis": 1,
            "validade_proposta_dias": 5,
        },
        "subtype_content": {
            "obra": {
                "escopo": "Execução do serviço conforme itens descritos, com organização do local ao final.",
                "entregaveis": [
                    "Execução dos itens do escopo",
                    "Lista de materiais (incluso x cliente)",
                    "Testes e validação final",
                ],
                "clausulas": [
                    "Problemas estruturais ocultos podem gerar aditivo.",
                    "Cliente garante acesso ao local e infraestrutura necessária (energia/água quando aplicável).",
                ],
            }
        },
        "recommended_blocks": ["inclui", "nao_inclui", "prazo_dependencias", "cancelamento"],
    },

    "consultoria": {
        "name": "Consultoria / Mentoria",
        "subtypes": ["consultoria", "mentoria"],
        "defaults": {
            "revisoes_por_entrega": 1,
            "sla_feedback_dias_uteis": 2,
            "validade_proposta_dias": 7,
        },
        "subtype_content": {
            "consultoria": {
                "escopo": "Diagnóstico, plano de ação e acompanhamento para destravar e orientar execução.",
                "entregaveis": [
                    "Kickoff (60–90 min)",
                    "Mapa de problemas e oportunidades",
                    "Plano de ação (documento)",
                    "{qtd_encontros} encontros de acompanhamento",
                    "Revisão final + próximos passos",
                ],
                "clausulas": [
                    "Execução operacional não está inclusa (pode ser contratada à parte).",
                    "Resultados dependem da implementação pelo cliente.",
                ],
            }
        },
        "recommended_blocks": ["inclui", "processo", "prazo_dependencias", "confidencialidade", "cancelamento"],
    },

    "recorrente": {
        "name": "Serviço Recorrente (Mensal)",
        "subtypes": ["retainer"],
        "defaults": {
            "revisoes_por_entrega": 1,
            "sla_feedback_dias_uteis": 2,
            "validade_proposta_dias": 7,
        },
        "subtype_content": {
            "retainer": {
                "escopo": "Execução mensal recorrente com entregas previsíveis e otimizações contínuas.",
                "entregaveis": [
                    "Pacote mensal: {pacote_mensal}",
                    "Reunião mensal de alinhamento",
                    "Relatório mensal",
                    "Suporte assíncrono (dentro do combinado)",
                ],
                "clausulas": [
                    "Escopo funciona como caixa mensal: fora do pacote vira extra.",
                    "Itens não utilizados no mês não acumulam para o próximo ciclo (salvo acordo).",
                ],
            }
        },
        "recommended_blocks": ["inclui", "nao_inclui", "processo", "prazo_dependencias", "cancelamento"],
    },
}

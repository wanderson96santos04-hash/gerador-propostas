# backend/app/templates/intelligent_presets.py
from __future__ import annotations

PRESETS = {

    # ==================================================
    # MARKETING
    # ==================================================

    "social_media": {
        "label": "Social Media Premium",
        "service": "Gestão de Social Media Premium",
        "scope": (
            "Gestão estratégica de redes sociais com foco em posicionamento de marca, "
            "engajamento qualificado e apoio aos objetivos comerciais.\n\n"
            "Entregáveis:\n"
            "• Planejamento editorial mensal\n"
            "• Criação de conteúdo para feed e stories (conforme pacote)\n"
            "• Redação de copies estratégicas\n"
            "• Direção visual e padronização da identidade\n"
            "• Monitoramento de engajamento e desempenho\n"
            "• Relatório mensal com análises e recomendações\n\n"
            "Limites e condições:\n"
            "• Informações, materiais e insumos fornecidos pelo cliente\n"
            "• Alterações após aprovação podem gerar ajustes de escopo\n"
        ),
        "differentiators": (
            "Conteúdo planejado com visão estratégica, consistência visual "
            "e clareza na comunicação."
        ),
        "warranty_support": (
            "Até duas rodadas de ajustes por entrega. Suporte assíncrono em horário comercial."
        ),
    },

    "trafego_pago": {
        "label": "Tráfego Pago",
        "service": "Gestão de Tráfego Pago",
        "scope": (
            "Gestão profissional de campanhas de mídia paga com foco em performance, "
            "otimização contínua e maximização do retorno sobre investimento.\n\n"
            "Entregáveis:\n"
            "• Estruturação e configuração de campanhas\n"
            "• Criação e testes de anúncios (variações)\n"
            "• Otimização contínua de públicos, criativos e orçamento\n"
            "• Monitoramento de métricas e desempenho\n"
            "• Relatórios periódicos com análises e próximos passos\n\n"
            "Limites e condições:\n"
            "• Verba de mídia não inclusa (responsabilidade do cliente)\n"
            "• Resultados dependem de fatores como mercado, oferta e orçamento\n"
        ),
        "differentiators": (
            "Gestão orientada por dados, decisões estratégicas e foco em resultados mensuráveis."
        ),
        "warranty_support": (
            "Acompanhamento contínuo durante o período contratado, com ajustes estratégicos."
        ),
    },

    "design": {
        "label": "Design / Criativos",
        "service": "Criação de Design e Criativos",
        "scope": (
            "Desenvolvimento de peças visuais com foco em comunicação clara, "
            "estética profissional e alinhamento ao posicionamento da marca.\n\n"
            "Entregáveis:\n"
            "• Peças para campanhas, anúncios e redes sociais\n"
            "• Definição de direção visual com variações\n"
            "• Entrega de arquivos finais nos formatos acordados\n\n"
            "Limites e condições:\n"
            "• Revisões dentro do escopo contratado\n"
            "• Mudanças de direção visual podem gerar aditivos\n"
        ),
        "differentiators": (
            "Design estratégico voltado à clareza da mensagem e impacto visual."
        ),
        "warranty_support": (
            "Até duas rodadas de revisão por entrega. Arquivos finais conforme combinado."
        ),
    },

    # ==================================================
    # WEB
    # ==================================================

    "sites": {
        "label": "Criação de Site",
        "service": "Criação de Site Profissional",
        "scope": (
            "Desenvolvimento de site institucional com foco em apresentação profissional, "
            "organização da informação e presença digital.\n\n"
            "Entregáveis:\n"
            "• Estrutura e organização das páginas\n"
            "• Design responsivo\n"
            "• Conteúdo institucional estruturado\n"
            "• SEO básico on-page\n\n"
            "Limites e condições:\n"
            "• Hospedagem, domínio e ferramentas externas não inclusos\n"
        ),
        "differentiators": (
            "Site com hierarquia clara de informações e apresentação profissional."
        ),
        "warranty_support": (
            "Até duas rodadas de ajustes. Suporte durante a publicação, se aplicável."
        ),
    },

    "landing_page": {
        "label": "Landing Page",
        "service": "Criação de Landing Page",
        "scope": (
            "Criação de landing page focada em conversão, captação de leads "
            "e comunicação objetiva.\n\n"
            "Entregáveis:\n"
            "• Estrutura persuasiva orientada à conversão\n"
            "• Design responsivo\n"
            "• Copy clara e orientada à ação\n"
            "• Integrações com formulário, WhatsApp ou pixel\n"
            "• Testes básicos de usabilidade\n\n"
            "Limites e condições:\n"
            "• Ferramentas externas não inclusas, salvo acordo\n"
        ),
        "differentiators": (
            "Página desenvolvida com foco em conversão e clareza da proposta."
        ),
        "warranty_support": (
            "Suporte por até 15 dias após a entrega para ajustes pontuais."
        ),
    },

    # ==================================================
    # SERVIÇOS
    # ==================================================

    "consultoria": {
        "label": "Consultoria",
        "service": "Consultoria Estratégica",
        "scope": (
            "Diagnóstico estratégico do cenário atual, análise de oportunidades, "
            "definição de prioridades e elaboração de plano de ação com acompanhamento consultivo.\n\n"
            "Entregáveis:\n"
            "• Reunião inicial de diagnóstico\n"
            "• Análise de cenário e oportunidades\n"
            "• Plano de ação estruturado\n"
            "• Sessões de acompanhamento consultivo\n\n"
            "Limites e condições:\n"
            "• Execução operacional não inclusa\n"
        ),
        "differentiators": (
            "Clareza estratégica, direcionamento prático e foco em decisões eficientes."
        ),
        "warranty_support": (
            "Suporte consultivo entre sessões em horário comercial."
        ),
    },

    "prestador_local": {
        "label": "Prestador Local",
        "service": "Serviço Local (Prestador)",
        "scope": (
            "Prestação de serviço pontual com escopo definido, "
            "prazos acordados e entrega objetiva.\n\n"
            "Entregáveis:\n"
            "• Execução do serviço conforme escopo combinado\n"
            "• Cumprimento dos prazos estabelecidos\n"
            "• Comunicação clara durante a execução\n"
            "• Entrega final conforme acordado\n\n"
            "Limites e condições:\n"
            "• Alterações fora do escopo devem ser renegociadas\n"
        ),
        "differentiators": (
            "Objetividade, clareza de escopo e compromisso com a entrega."
        ),
        "warranty_support": (
            "Suporte conforme combinado para ajustes pós-entrega."
        ),
    },

    # ==================================================
    # CONTRATOS / RECORRENTES
    # ==================================================

    "mensal": {
        "label": "Contrato Mensal",
        "service": "Contrato Mensal de Serviços",
        "scope": (
            "Prestação mensal recorrente de serviços com entregas previsíveis "
            "e acompanhamento contínuo.\n\n"
            "Entregáveis:\n"
            "• Pacote mensal de entregas conforme escopo\n"
            "• Reunião mensal de alinhamento\n"
            "• Relatório de acompanhamento\n\n"
            "Limites e condições:\n"
            "• Demandas fora do pacote são tratadas como extras\n"
        ),
        "differentiators": (
            "Previsibilidade, organização e continuidade no atendimento."
        ),
        "warranty_support": (
            "Suporte assíncrono em horário comercial durante a vigência do contrato."
        ),
    },

    "contrato_fechado": {
        "label": "Contrato Fechado",
        "service": "Projeto com Escopo Fechado",
        "scope": (
            "Projeto com escopo fechado, fases definidas, "
            "entregas claras e critérios objetivos de aceite.\n\n"
            "Entregáveis:\n"
            "• Definição das fases do projeto\n"
            "• Entregas conforme cronograma acordado\n"
            "• Validação e aceite por etapa\n\n"
            "Limites e condições:\n"
            "• Alterações após aceite podem gerar aditivos\n"
        ),
        "differentiators": (
            "Segurança comercial, clareza contratual e previsibilidade de entrega."
        ),
        "warranty_support": (
            "Suporte conforme previsto em contrato para ajustes pós-entrega."
        ),
    },
}

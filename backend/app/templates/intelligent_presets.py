# backend/app/templates/intelligent_presets.py
from __future__ import annotations

PRESETS = {
    "trafego_pago": {
        "label": "Tráfego Pago (Gestão Mensal)",
        "service": "Gestão de Tráfego Pago",
        "scope": (
            "Estruturação e gestão de campanhas com foco em conversão.\n\n"
            "Entregáveis:\n"
            "• Setup e estrutura de campanhas\n"
            "• Criação de anúncios (variações)\n"
            "• Otimizações semanais\n"
            "• Relatório quinzenal/mensal\n"
            "• Pixel/Tags e eventos (se aplicável)\n\n"
            "Limites e cláusulas:\n"
            "• Investimento em mídia paga não incluso (por conta do cliente)\n"
            "• Sem garantia de métricas específicas: resultados dependem de oferta, público e verba\n"
        ),
        "differentiators": (
            "Processo com rotina de otimização e decisões baseadas em dados.\n"
            "Comunicação clara e relatório com próximos passos."
        ),
        "warranty_support": "Suporte em horário comercial. Ajustes e otimizações contínuas durante o período contratado.",
    },

    "social_media": {
        "label": "Social Media (Conteúdo Mensal)",
        "service": "Social Media / Gestão de Conteúdo",
        "scope": (
            "Planejamento e execução do conteúdo para redes sociais com entregas previsíveis.\n\n"
            "Entregáveis:\n"
            "• Calendário editorial (mensal)\n"
            "• Posts feed + stories (conforme pacote)\n"
            "• Copy e legendas\n"
            "• Direção visual e padronização\n"
            "• Relatório mensal com insights\n\n"
            "Limites e cláususlas:\n"
            "• Materiais e informações do produto por conta do cliente\n"
            "• Mudanças de direção após aprovações podem gerar aditivo\n"
        ),
        "differentiators": "Conteúdo com consistência visual e foco em clareza da mensagem.",
        "warranty_support": "2 rodadas de revisão por entrega. Suporte assíncrono em horário comercial.",
    },

    "design": {
        "label": "Design (Peças e Criativos)",
        "service": "Criação de Design e Criativos",
        "scope": (
            "Criação de peças com padrão visual consistente e prontas para uso.\n\n"
            "Entregáveis:\n"
            "• Peças para campanhas e redes sociais\n"
            "• 1 direção visual + variações\n"
            "• Arquivos finais nos formatos combinados\n\n"
            "Limites:\n"
            "• Revisões dentro do limite; mudanças de direção podem gerar aditivo\n"
        ),
        "differentiators": "Design pensado para comunicação clara e estética alinhada ao posicionamento.",
        "warranty_support": "2 rodadas de revisão por entrega. Entrega em formatos combinados.",
    },

    "sites": {
        "label": "Site / Landing Page",
        "service": "Criação de Landing Page / Site",
        "scope": (
            "Criação de página com foco em clareza, conversão e base técnica organizada.\n\n"
            "Entregáveis:\n"
            "• Wireframe + layout\n"
            "• Desenvolvimento responsivo\n"
            "• SEO básico\n"
            "• Integrações (formulário/WhatsApp/Pixel)\n\n"
            "Limites:\n"
            "• Hospedagem/domínio/ferramentas por conta do cliente (se não contratado)\n"
        ),
        "differentiators": "Página com hierarquia de informação e CTA, pensada para conversão.",
        "warranty_support": "2 rodadas de revisão. Suporte durante a publicação (se aplicável).",
    },

    "consultoria": {
        "label": "Consultoria / Mentoria",
        "service": "Consultoria Estratégica",
        "scope": (
            "Diagnóstico do cenário + plano de ação com acompanhamento.\n\n"
            "Entregáveis:\n"
            "• Kickoff (60–90 min)\n"
            "• Diagnóstico e prioridades\n"
            "• Plano de ação (documento)\n"
            "• Encontros de acompanhamento\n\n"
            "Limites:\n"
            "• Execução operacional não inclusa (pode ser contratada à parte)\n"
        ),
        "differentiators": "Clareza de prioridades e plano executável, com orientação prática.",
        "warranty_support": "Suporte entre sessões (horário comercial). 1 rodada de ajuste no plano após apresentação.",
    },

    "recorrente": {
        "label": "Serviço Recorrente (Retainer)",
        "service": "Serviço Recorrente Mensal",
        "scope": (
            "Execução mensal recorrente com entregas previsíveis e otimizações contínuas.\n\n"
            "Entregáveis:\n"
            "• Pacote mensal de entregas\n"
            "• Reunião mensal de alinhamento\n"
            "• Relatório mensal\n\n"
            "Limites:\n"
            "• Escopo funciona como caixa mensal: fora do pacote vira extra\n"
            "• Itens não utilizados no mês não acumulam (salvo acordo)\n"
        ),
        "differentiators": "Previsibilidade de entrega e processo contínuo.",
        "warranty_support": "Suporte assíncrono em horário comercial. Revisões conforme pacote.",
    },
}

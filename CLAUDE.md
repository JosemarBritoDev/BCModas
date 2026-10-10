# CLAUDE.md — Contexto Geral e Diretrizes do ERP BC Modas

## 🚀 Comandos Rápidos
- **Ativar venv:** `source venv/bin/activate`
- **Servidor Dev:** `python manage.py runserver`
- **Migrações:** `python manage.py makemigrations` && `python manage.py migrate`
- **Criar Superusuario:** `python manage.py createsuperuser`
- **Testes:** `python manage.py test`

## 🏗️ Estrutura de Arquitetura
- **Framework:** Django 5.x + Django REST Framework + Django Unfold (Admin Tecnológico Clean).
- **Diretório das Apps:** Módulos dentro de `apps/` (`tenants`, `usuarios`, `produtos`, `pedidos`, `saas_admin`).
- **Modelo de Negócio:** ERP **mono-empresa** — instância única da fábrica (`Empresa.obter_fabrica()`).
- **User Model:** `usuarios.Usuario` (RBAC: SUPERADMIN, GERENTE, COMPRAS, VENDAS, FINANCEIRO).
- **Design & UI:** Minimalista, limpo e profissional (Dark/Light mode via Unfold).

## 🛡️ Regras de Ouro & Segurança
1. **Isolamento por Empresa:** Toda consulta a modelos operacionais DEVE filtrar por `empresa=request.user.empresa`.
2. **LGPD Auditoria:** Pedidos públicos devem gravar consentimento com IP, Data/Hora e versão dos termos.
3. **Assinatura Fixo Mandatória:** Todas as telas e renderizações devem exibir no rodapé:
   `"Desenvolvido por BritosCode Tecnologia | Josemar Brito"`

# BC Modas — ERP da Fábrica e Catálogo B2B

## 📌 Visão Geral

O **BC Modas** é um **ERP mono-empresa** (uma única confecção) que unifica o
**controle interno** (catálogo de peças, grade de SKUs, estoque e pedidos) com uma
**frente de vendas para lojistas** (catálogo white-label com checkout via WhatsApp).

O sistema é a instância operacional da própria fábrica: não há múltiplos clientes
nem planos de assinatura. O **SuperAdmin** e a equipe da confecção compartilham o
mesmo painel, com dados protegidos pelo mesmo isolamento por `empresa`.

> **Rodapé fixo obrigatório em todas as telas:**
> `"Desenvolvido por BritosCode Tecnologia | Josemar Brito"`

---

## 🏗️ Arquitetura e Stack

| Camada | Tecnologia |
| --- | --- |
| Framework | **Django 5.2** (Python) |
| Admin / UI | **Django Unfold** (sidebar, cards de KPI, dark/light mode) |
| API | **Django REST Framework** + SimpleJWT + django-cors-headers |
| Banco (dev) | **SQLite** |
| Banco (produção) | **PostgreSQL** (`psycopg2-binary`) |
| Imagens | **Pillow** |
| Servidor | **Gunicorn** |
| Container | **Docker / Docker Compose** |
| Python | 3.14 (venv local) |

### Princípios de engenharia

1. **Empresa única** — os dados da fábrica vivem em `Empresa` e são acessados via
   `Empresa.obter_fabrica()`; todo queryset operacional filtra por
   `empresa=request.user.empresa`.
2. **RBAC** — perfis `SUPERADMIN`, `GERENTE`, `COMPRAS`, `VENDAS`, `FINANCEIRO`
   controlam acesso a módulos.
3. **LGPD por design** — pedidos públicos gravam consentimento com **IP + data/hora +
   versão dos termos**.
4. **Admin minimalista** — interface Unfold limpa e orientada a usuários leigos.

---

## 📁 Estrutura de Módulos

```
apps/
├── tenants/      # Empresa (dados da confecção), identidade visual e catálogo
├── usuarios/     # Usuário (AbstractUser) + RBAC + comando create_initial_admin
├── produtos/     # Linha de vestuário: Modelo (6 fotos) e SKU (grade cor x tamanho)
├── pedidos/      # Pedido + ItemPedido + auditoria LGPD de aceite
└── saas_admin/   # Callback do dashboard (KPIs da fábrica)
core/             # settings, urls, wsgi, asgi
templates/admin/  # Template customizado do dashboard (cards de KPI)
templates/catalogo/  # Catálogo público white-label (loja B2B + checkout WhatsApp)
```

| Módulo | Modelos principais | Responsabilidade |
| --- | --- | --- |
| `tenants` | `Empresa` | Dados da confecção, identidade visual e catálogo |
| `usuarios` | `Usuario` | Equipe, perfis de acesso, senha do SuperAdmin |
| `produtos` | `Modelo`, `SKU` | Catálogo, matriz de grade, saldos de estoque |
| `pedidos` | `Pedido`, `ItemPedido` | Vendas, status do fluxo e consentimento LGPD |
| `saas_admin` | — | Dashboard e KPIs da fábrica |

---

## ▶️ Execução Local

```bash
# 1. Ambiente virtual
source venv/bin/activate

# 2. Dependências (já instaladas no ambiente atual)
pip install -r requirements.txt

# 3. Migrações
python manage.py makemigrations
python manage.py migrate

# 4. Dados iniciais
python manage.py create_initial_admin     # cria o superusuário josemar
python manage.py populate_demo_data       # (opcional) catálogo de demonstração

# 5. Servidor de desenvolvimento
python manage.py runserver
```

Acesse **http://127.0.0.1:8000/admin/** com o usuário criado por `create_initial_admin`.

### Comandos de gestão

| Comando | Descrição |
| --- | --- |
| `python manage.py create_initial_admin` | Cria/atualiza o SuperAdmin `josemar` (idempotente) |
| `python manage.py populate_demo_data` | Popula dados de demonstração (idempotente) |
| `python manage.py check` | Valida a configuração do projeto |
| `python manage.py test` | Executa a suíte de testes |

> **Segurança:** a senha do SuperAdmin pode ser definida pela variável de ambiente
> `DJANGO_INITIAL_ADMIN_PASSWORD` (ou pela flag `--password`). Nunca versione senhas.

---

## 📊 Painel (Django Unfold)

- **Sidebar** agrupada por módulos: **Vendas** (Pedidos), **Produtos** (Modelos,
  SKUs/Grade) e **Sistema** (Dados da Confecção, Usuários, Grupos).
- O item **Dados da Confecção** leva direto ao formulário da fábrica (CNPJ, logo,
  redes, WhatsApp e Termos LGPD) — a listagem redireciona automaticamente.
- **Dashboard** com cards de KPI: Pedidos, Faturamento Acumulado, Modelos e
  Pedidos Pendentes.

---

## 🗺️ Histórico e Visão Futura

### Entregue
- ERP mono-empresa (`tenants`, `usuarios`, `produtos`, `pedidos`).
- Admin Unfold com sidebar por módulos, RBAC e dashboard de KPIs.
- Auditoria LGPD nos pedidos (IP, data/hora e versão dos termos).
- **Catálogo público white-label** (`/catalogo/<slug>/`) com cores/logo da confecção,
  grade Cor × Tamanho, preços de **varejo e atacado** (por quantidade mínima), aceite
  obrigatório dos termos e checkout convertido em mensagem formatada para o WhatsApp
  (`wa.me`).
- Comandos de carga inicial (`create_initial_admin`, `populate_demo_data`).
- Documentação técnica (README e guia de uso `PASSO_A_PASSO.md`).

### Próximos passos
- **Bot de Atendimento Inteligente** no WhatsApp: triagem automática de pedidos,
  resposta a dúvidas sobre grade/estoque e status de entrega.
- Dashboard de métricas financeiras (ticket médio, curva ABC de peças).
- Deploy em Docker Compose + PostgreSQL e pipeline CI/CD.

---

## 🛡️ Segurança e Compliance

- **Isolamento de dados** por `empresa` em todas as consultas operacionais.
- **Status da fábrica** (`ATIVO`/`SUSPENSO`) como trava de negócio.
- **LGPD**: consentimento auditável e imutável no pedido.
- **RBAC**: permissões separadas para operação, compras, vendas e financeiro.

---

## 📄 Licença

Veja o arquivo [LICENSE](LICENSE) para detalhes.

---

<p align="center"><b>Desenvolvido por BritosCode Tecnologia | Josemar Brito</b></p>

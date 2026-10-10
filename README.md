# BC Modas — SaaS de Gestão e E-commerce para Confecções

## 📌 Visão Geral

O **BC Modas** é uma plataforma **SaaS multi-tenant B2B** para a gestão de confecções de
vestuário, unificando o **controle interno** (catálogo de peças, grade de SKUs, estoque e
pedidos) com uma **frente de vendas para lojistas** (catálogo white-label com checkout via
WhatsApp).

Cada confecção contratada é um **Tenant (Empresa)** com isolamento estrito de dados:
nenhum registro é acessível de uma empresa para outra. A plataforma é operada por um
**SuperAdmin (BritosCode)** que controla planos, empresas e métricas globais de negócio
(MRR, peças, pedidos).

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
| Container | **Docker / Docker Compose** (previsto) |
| Python | 3.14 (venv local) |

### Princípios de engenharia

1. **Multi-tenant por `empresa`** — todo queryset operacional é filtrado por
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
├── tenants/      # Núcleo do SaaS: Plano, Empresa (dados da confecção) e mixins de isolamento
├── usuarios/     # Usuário (AbstractUser) + RBAC + comando create_initial_admin
├── produtos/     # Linha de vestuário: Modelo (6 fotos) e SKU (grade cor x tamanho)
├── pedidos/      # Pedido + ItemPedido + auditoria LGPD de aceite
└── saas_admin/   # Callback do dashboard (KPIs) e futuras métricas globais
core/             # settings, urls, wsgi, asgi
templates/admin/  # Template customizado do dashboard (cards de KPI)
templates/catalogo/  # Catálogo público white-label (loja B2B + checkout WhatsApp)
```

| Módulo | Modelos principais | Responsabilidade |
| --- | --- | --- |
| `tenants` | `Plano`, `Empresa` | Assinaturas, cadastro da confecção, marca/identidade |
| `usuarios` | `Usuario` | Equipe, perfis de acesso, senha do SuperAdmin |
| `produtos` | `Modelo`, `SKU` | Catálogo, matriz de grade, saldos de estoque |
| `pedidos` | `Pedido`, `ItemPedido` | Vendas, status do fluxo e consentimento LGPD |
| `saas_admin` | — | Dashboard, KPIs e monitoramento global |

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
python manage.py seed_planos              # cria os 3 planos padrão
python manage.py create_initial_admin     # cria o superusuário josemar

# 5. Servidor de desenvolvimento
python manage.py runserver
```

Acesse **http://127.0.0.1:8000/admin/** com o usuário criado por `create_initial_admin`.

### Comandos de gestão

| Comando | Descrição |
| --- | --- |
| `python manage.py seed_planos` | Cria/atualiza os planos padrão (idempotente) |
| `python manage.py create_initial_admin` | Cria/atualiza o SuperAdmin `josemar` (idempotente) |
| `python manage.py check` | Valida a configuração do projeto |
| `python manage.py test` | Executa a suíte de testes |

> **Segurança:** a senha do SuperAdmin pode ser definida pela variável de ambiente
> `DJANGO_INITIAL_ADMIN_PASSWORD` (ou pela flag `--password`). Nunca versione senhas.

---

## 📊 Painel (Django Unfold)

- **Sidebar** agrupada por módulos: **Operação** (Modelos, SKUs, Pedidos),
  **Gestão** (Dados da Confecção, Usuários, Grupos) e **SaaS Global**
  (Empresas, Planos — visível apenas ao SuperAdmin).
- **Dashboard** com cards de KPI: Pedidos, Faturamento Acumulado, Modelos e
  Empresas Ativas (filtrados por tenant para usuários não-superadmins).

### Planos padrão

| Plano | Preço mensal | Usuários | Produtos |
| --- | --- | --- | --- |
| Starter | R$ 97,00 | 1 | 50 |
| Pro | R$ 197,00 | 5 | 300 |
| Enterprise | R$ 497,00 | 999 | 99.999 |

---

## 🗺️ Histórico e Visão Futura

### Entregue
- Modelagem multi-tenant (`tenants`, `usuarios`, `produtos`, `pedidos`).
- Admin Unfold com sidebar por módulos, RBAC e dashboard de KPIs.
- Auditoria LGPD nos pedidos (IP, data/hora e versão dos termos).
- **Catálogo público white-label** (`/catalogo/<slug>/`) com cores/logo da confecção,
  grade Cor × Tamanho, aceite obrigatório dos termos e checkout convertido em
  mensagem formatada para o WhatsApp (`wa.me`).
- Comandos de carga inicial (`seed_planos`, `create_initial_admin`).
- Documentação técnica (README e guia de uso `PASSO_A_PASSO.md`).

### Próximos passos
- **Bot de Atendimento Inteligente** no WhatsApp: triagem automática de pedidos,
  resposta a dúvidas sobre grade/estoque e status de entrega.
- Dashboard de métricas financeiras (MRR, ticket médio, curva ABC de peças).
- Deploy em Docker Compose + PostgreSQL e pipeline CI/CD.
- Validação de limites de plano no backend (bloqueio ao atingir usuários/produtos).

---

## 🛡️ Segurança e Compliance

- **Isolamento de dados** entre empresas em todas as consultas operacionais.
- **Status de assinatura** (`ATIVO`/`SUSPENSO`) como trava de negócio.
- **LGPD**: consentimento auditável e imutável no pedido.
- **RBAC**: permissões separadas para operação, compras, vendas e financeiro.

---

## 📄 Licença

Veja o arquivo [LICENSE](LICENSE) para detalhes.

---

<p align="center"><b>Desenvolvido por BritosCode Tecnologia | Josemar Brito</b></p>

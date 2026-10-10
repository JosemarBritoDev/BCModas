# 📘 PASSO A PASSO — BC Modas

Guia operacional completo do SaaS **BC Modas**, desde a visão do **SuperAdmin (BritosCode)**
até a rotina de uma **confecção cliente**. Nele você aprende a configurar a plataforma,
montar a linha de vestuário, operar a matriz de grade e entender o tratamento de dados
pessoais (LGPD).

> **Rodapé fixo obrigatório em todas as telas:**
> `"Desenvolvido por BritosCode Tecnologia | Josemar Brito"`

---

## 🚀 Primeiros Passos

1. Ative o ambiente virtual: `source venv/bin/activate`
2. Aplique as migrações: `python manage.py migrate`
3. Cadastre os planos: `python manage.py seed_planos`
4. Crie o SuperAdmin: `python manage.py create_initial_admin`
5. Suba o servidor: `python manage.py runserver`
6. Abra **http://127.0.0.1:8000/admin/** e faça login.

> **Credenciais padrão do SuperAdmin:** usuário `josemar`.
> A senha inicial é definida por `DJANGO_INITIAL_ADMIN_PASSWORD` (padrão `Admin123!`).
> **Altere-a imediatamente** após o primeiro acesso e mantenha-a fora do versionamento.

---

## 👑 Manual do SuperAdmin

O SuperAdmin administra a plataforma como um todo: planos, empresas (tenants),
monitoramento global e métricas.

### 1. Criar e gerenciar Planos

Acesse **SaaS Global → Planos**.

| Campo | Descrição |
| --- | --- |
| Nome | Identificação comercial (ex.: `Pro`) |
| Preço Mensal | Valor da assinatura em reais |
| Limite de Usuários | Máximo de contas naquela confecção |
| Limite de Produtos | Máximo de modelos cadastrados |

Os três planos padrão já são criados pelo comando `seed_planos`:

| Plano | Mensalidade | Usuários | Produtos |
| --- | --- | --- | --- |
| Starter | R$ 97,00 | 1 | 50 |
| Pro | R$ 197,00 | 5 | 300 |
| Enterprise | R$ 497,00 | 999 | 99.999 |

💡 O comando é **idempotente**: reexecutá-lo apenas atualiza os valores, sem duplicar
registros. Para criar um plano novo, clique em **Adicionar**.

### 2. Cadastrar uma Confecção (Empresa)

Acesse **SaaS Global → Empresas → Adicionar**.

**Dados da Empresa**
- Nome Fantasia, CNPJ (único), E-mail, WhatsApp Comercial, Instagram e Endereço de Origem.

**Identidade Visual** (usada no catálogo white-label)
- Logo e Favicon.

**Assinatura**
- **Plano**: escolha um dos planos cadastrados.
- **Status**: `Ativo` ou `Suspenso`. Ao suspenser, a confecção perde o acesso de operação.

**Documentos Legais**
- **Termos de Uso** e **Política de Privacidade**. A versão/texto registrado aqui é a
  referência exigida para o aceite de LGPD nos pedidos daquela empresa.

✅ Dica: cadastre a empresa antes de criar o usuário da confecção — o vínculo de
`empresa` é o que garante o isolamento de dados.

### 3. Monitorar o SaaS

A **página inicial (Dashboard)** exibe cards de KPI:

| Card | O que mostra |
| --- | --- |
| Pedidos | Total de pedidos registrados |
| Faturamento | Somatório de `valor_total` dos pedidos |
| Modelos | Modelos no catálogo |
| Empresas Ativas | Confecções com assinatura `Ativo` |

O SuperAdmin enxerga as métricas **globais**. Usuários de uma confecção enxergam apenas
as métricas da própria empresa. A seção **SaaS Global** (Empresas e Planos) só aparece
no sidebar de superadmins.

---

## 🏢 Manual da Confecção

Tudo abaixo acontece dentro da área da empresa: o sistema já filtra os dados por
`empresa`, então nenhuma confecção enxerga as informações da outra.

### 1. Cadastrar a Equipe (RBAC)

Acesse **Gestão → Usuários → Adicionar**.

- Preencha **username, e-mail, nome completo** e defina uma senha.
- **Empresa**: vínculo do usuário com a confecção (não deixe vazio para usuários internos).
- **Perfil de Acesso (`role`)**:

| Perfil | Recomendado para |
| --- | --- |
| `SUPERADMIN` | Operadores da BritosCode (visão global) |
| `GERENTE` | Dono/gerente da confecção (acesso geral) |
| `COMPRAS` | Equipe de produção e cadastro de peças |
| `VENDAS` | Atendimento e criação de pedidos |
| `FINANCEIRO` | Acompanhamento de valores e faturamento |

💡 Use **Gestão → Grupos** para agrupar permissões padrão do Django e associá-las aos
perfis.

### 2. Criar Modelos (a peça)

Acesse **Operação → Modelos → Adicionar**.

| Bloco | Campos |
| --- | --- |
| Identificação | Nome, Marca, Estampa/Logo |
| Comercial | Preço de Tabela, **Visível no Catálogo** |
| Ficha Técnica | Composição, Gramatura, Descrição, **Tabela de Medidas (JSON)** |
| Fotos | Foto 1 até Foto 6 (até 6 imagens por produto) |

- **Visível no Catálogo**: desmarque para manter a peça interna (não exposta no catálogo
  de lojistas).
- O campo **Tabela de Medidas** aceita um JSON com as medidas por tamanho, por exemplo:

```json
{
  "cabeca":   "P: 34 | M: 35 | G: 36 | GG: 37",
  "busto":    "P: 46 | M: 48 | G: 50 | GG: 52",
  "cintura":  "P: 38 | M: 40 | G: 42 | GG: 44",
  "comprimento": "P: 68 | M: 70 | G: 72 | GG: 74"
}
```

### 3. Gerenciar a Matriz de SKUs (Cor x Tamanho)

Cada combinação de **cor** e **tamanho** é um SKU, com seu próprio saldo de estoque.

- Ao salvar um Modelo, a grade é montada no **inline de SKUs** logo abaixo do formulário.
- **Cores**: informe o `nome da cor` e o `hexadecimal` (ex.: `Preto` / `#111111`) — o hex
  é usado como **swatch** visual na listagem.
- **Tamanhos**: `PP`, `P`, `M`, `G`, `GG`, `XG`, `XGG`.
- **Estoque** e **Código de Barras** são preenchidos por SKU.

Regras importantes:

- A combinação `Modelo + Cor + Tamanho` é **única** — o sistema bloqueia duplicidade.
- O campo `empresa` do SKU é copiado automaticamente do Modelo (proteção anti vazamento
  entre tenants).
- Para **atualização em lote de saldos**, abra **Operação → SKUs / Grade**, filtre por
  tamanho/cor e edite a coluna **Estoque** direto na listagem (alteração em lote).

### 4. Gerenciar Pedidos

Acesse **Operação → Pedidos → Adicionar**.

**Cabeçalho do pedido**
- Cliente: Nome, Documento, WhatsApp.
- Totais: Total de Itens e Valor Total.
- **Status** do fluxo:

```
PENDENTE → EM_SEPARACAO → FATURADO → ENVIADO → CONCLUIDO
```

**Itens** (inline)
- Adicione linhas com **SKU, Quantidade e Preço Unitário**; o **Subtotal** da linha é
  calculado automaticamente.

**Consentimento LGPD**
- Marque **Aceite LGPD** somente com o consentimento real do cliente.
- Os campos **IP do Aceite**, **Data do Aceite** e **Versão dos Termos** são
  **somente leitura** no admin: são gravados pela auditoria e não podem ser editados
  manualmente.

---

## 🔒 Guia de Privacidade e LGPD

### O que é registrado

Todo pedido captado com consentimento gera uma **trilha de auditoria** com:

| Campo | Conteúdo |
| --- | --- |
| `aceite_lgpd` | `true/false` — se o cliente aceitou |
| `ip_aceite` | Endereço IP de onde o aceite foi dado |
| `data_aceite` | Data e hora do aceite |
| `versao_termos` | Versão/texto dos termos aceitos |
| `created_at` | Data de criação do pedido |

Esses campos refletem o item de regra do projeto:

> *"Pedidos públicos devem gravar consentimento com IP, Data/Hora e versão dos termos."*

### Como os logs são "invioláveis"

1. **Somente leitura no admin** — `ip_aceite`, `data_aceite`, `versao_termos`,
   `created_at` e `updated_at` estão marcados como `readonly_fields` no admin, então
   nenhum operador consegue alterá-los pela interface.
2. **Campos nunca nulos por regra de negócio** — o backend deve gravá-los no momento da
   finalização do pedido; o consentimento não é editável depois de criado.
3. **Auditoria por empresa** — o pedido pertence a um `empresa`, preservando o
   rastreamento por tenant.

### Boas práticas operacionais

- 🚫 Não crie pedidos sem o aceite real do cliente.
- 📄 Mantenha os textos de **Termos de Uso** e **Política de Privacidade** da empresa
  sempre atualizados — é deles que nasce a `versao_termos`.
- 🧹 Não tente editar logs de aceite por scripts diretos no banco; preservar a
  integridade é requisito de compliance.
- 🔐 Restrinha o perfil de acesso dos operadores (RBAC) para minimizar acessos.

---

## 🧭 Referência de Caminhos do Admin

| Seção | URL |
| --- | --- |
| Dashboard | `/admin/` |
| Planos | `/admin/tenants/plano/` |
| Empresas | `/admin/tenants/empresa/` |
| Usuários | `/admin/usuarios/usuario/` |
| Modelos | `/admin/produtos/modelo/` |
| SKUs | `/admin/produtos/sku/` |
| Pedidos | `/admin/pedidos/pedido/` |
| Grupos | `/admin/auth/group/` |

---

## ⚠️ Limites e Melhorias em Andamento

- **Limites de plano** (`limite_usuarios` / `limite_produtos`) já estão cadastrados, mas a
  **trava automática de cadastro** no backend ainda será implementada.
- A segmentação fina de permissões por `role` (além do isolamento por empresa e do
  controle de superadmin) será refinada por grupo de permissões.
- Checkout público white-label e Bot de Atendimento no WhatsApp estão no roadmap.

---

<p align="center"><b>Desenvolvido por BritosCode Tecnologia | Josemar Brito</b></p>

# 📘 PASSO A PASSO — BC Modas

Guia operacional completo do ERP **BC Modas**: configuração da fábrica, montagem da
linha de vestuário, operação da matriz de grade, gestão de pedidos e tratamento de
dados pessoais (LGPD).

> **Rodapé fixo obrigatório em todas as telas:**
> `"Desenvolvido por BritosCode Tecnologia | Josemar Brito"`

---

## 🚀 Primeiros Passos

1. Ative o ambiente virtual: `source venv/bin/activate`
2. Aplique as migrações: `python manage.py migrate`
3. Crie o SuperAdmin: `python manage.py create_initial_admin`
4. (Opcional) Popule o catálogo de demonstração: `python manage.py populate_demo_data`
5. Suba o servidor: `python manage.py runserver`
6. Abra **http://127.0.0.1:8000/admin/** e faça login.

> **Credenciais padrão do SuperAdmin:** usuário `josemar`.
> A senha inicial é definida por `DJANGO_INITIAL_ADMIN_PASSWORD` (padrão `Admin123!`).
> **Altere-a imediatamente** após o primeiro acesso e mantenha-a fora do versionamento.

---

## 👑 Manual do Administrador

O ERP é **mono-empresa**: existe apenas o registro da própria fábrica. O administrador
cuida do cadastro da confecção, da equipe, do catálogo e dos pedidos.

### 1. Cadastrar os Dados da Confecção (Empresa)

Acesse **Sistema → Dados da Confecção**. A listagem redireciona automaticamente para o
formulário da fábrica.

**Dados da Fábrica**
- Nome Fantasia, CNPJ (único), E-mail, WhatsApp Comercial, Instagram e Endereço de Origem.
- **Slug do Catálogo**: gerado automaticamente a partir do nome fantasia (pode ser editado).

**Identidade Visual** (usada no catálogo white-label)
- Logo, Favicon e Cor Primária.

**Catálogo Público**
- Exibe o endereço `/catalogo/<slug>/` pronto para compartilhar com lojistas.

**Termos LGPD**
- **Termos de Uso** e **Política de Privacidade**. O texto registrado aqui é a referência
  exigida para o aceite de LGPD nos pedidos.

**Status**
- `Ativo` ou `Suspenso`. Ao suspender, o catálogo público passa a responder **403**.

✅ Só é possível cadastrar uma fábrica. Depois de criada, o botão de adicionar é
desabilitado e a listagem sempre abre o cadastro existente.

### 2. Cadastrar a Equipe (RBAC)

Acesse **Sistema → Usuários → Adicionar**.

- Preencha **username, e-mail, nome completo** e defina uma senha.
- **Empresa**: vínculo do usuário com a fábrica (não deixe vazio para usuários internos).
- **Perfil de Acesso (`role`)**:

| Perfil | Recomendado para |
| --- | --- |
| `SUPERADMIN` | Administração do ERP (visão geral) |
| `GERENTE` | Dono/gerente da fábrica (acesso geral) |
| `COMPRAS` | Equipe de produção e cadastro de peças |
| `VENDAS` | Atendimento e criação de pedidos |
| `FINANCEIRO` | Acompanhamento de valores e faturamento |

💡 Use **Sistema → Grupos** para agrupar permissões padrão do Django e associá-las aos
perfis.

### 3. Criar Modelos (a peça)

Acesse **Produtos → Modelos → Adicionar**.

| Bloco | Campos |
| --- | --- |
| Identificação | Nome, Marca, Estampa/Logo |
| Comercial | Preço de Varejo, Preço de Atacado, Qtd. Mínima p/ Atacado, **Visível no Catálogo** |
| Ficha Técnica | Composição, Gramatura, Descrição, **Tabela de Medidas (JSON)** |
| Fotos | Foto 1 até Foto 6 (até 6 imagens por produto) |

- **Preço de Atacado**: aplicado automaticamente quando a quantidade do item atinge a
  **Qtd. Mínima p/ Atacado** (padrão 6).
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

### 4. Gerenciar a Matriz de SKUs (Cor x Tamanho)

Cada combinação de **cor** e **tamanho** é um SKU, com seu próprio saldo de estoque.

- Ao salvar um Modelo, a grade é montada no **inline de SKUs** logo abaixo do formulário.
- **Cores**: informe o `nome da cor` e o `hexadecimal` (ex.: `Preto` / `#111111`) — o hex
  é usado como **swatch** visual na listagem.
- **Tamanhos**: `PP`, `P`, `M`, `G`, `GG`, `XG`, `XGG`.
- **Estoque** e **Código de Barras** são preenchidos por SKU.

Regras importantes:

- A combinação `Modelo + Cor + Tamanho` é **única** — o sistema bloqueia duplicidade.
- O campo `empresa` do SKU é copiado automaticamente do Modelo (proteção contra
  vazamento de dados).
- Para **atualização em lote de saldos**, abra **Produtos → SKUs / Grade**, filtre por
  tamanho/cor e edite a coluna **Estoque** direto na listagem (alteração em lote).

### 5. Gerenciar Pedidos

Acesse **Vendas → Pedidos → Adicionar**.

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

### 6. Catálogo Público (White-Label)

A fábrica tem um catálogo público em `/catalogo/<slug>/`, onde o `slug` é gerado
automaticamente a partir do nome fantasia (editável em **Sistema → Dados da Confecção**).
O administrador vê o endereço pronto no bloco **Catálogo Público**.

- **White-label**: a página usa a **logo**, a **cor primária** e os contatos
  (WhatsApp/Instagram) da confecção. Mude o **Status** para `Suspenso` para tirar o
  catálogo do ar — o acesso passa a responder **403**.
- **Grade Cor × Tamanho**: o lojista informa a quantidade desejada por SKU; o estoque
  é exibido e validado no envio (pedidos acima do saldo são recusados).
- **Preço de atacado**: ao atingir a quantidade mínima do modelo, o preço de atacado é
  aplicado automaticamente.
- **Aceite obrigatório**: sem marcar *Termos de Uso* e *Política de Privacidade* o
  checkout não é concluído.
- **Checkout via WhatsApp**: ao finalizar, o sistema cria um `Pedido` (status
  `PENDENTE`) com a trilha de auditoria LGPD e gera uma mensagem formatada, abrindo o
  link `wa.me` do WhatsApp comercial com todos os itens, total e dados do cliente.

> **Privacidade:** o link `wa.me` é gerado no servidor a partir do próprio pedido, e
> não a partir de parâmetros da URL, evitando manipulação externa.

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
3. **Auditoria por empresa** — o pedido pertence à fábrica, preservando o rastreamento.

### Boas práticas operacionais

- 🚫 Não crie pedidos sem o aceite real do cliente.
- 📄 Mantenha os textos de **Termos de Uso** e **Política de Privacidade** sempre
  atualizados — é deles que nasce a `versao_termos`.
- 🧹 Não tente editar logs de aceite por scripts diretos no banco; preservar a
  integridade é requisito de compliance.
- 🔐 Restrinja o perfil de acesso dos operadores (RBAC) para minimizar acessos.

---

## 🧭 Referência de Caminhos do Admin

| Seção | URL |
| --- | --- |
| Dashboard | `/admin/` |
| Dados da Confecção | `/admin/tenants/empresa/` |
| Usuários | `/admin/usuarios/usuario/` |
| Modelos | `/admin/produtos/modelo/` |
| SKUs | `/admin/produtos/sku/` |
| Pedidos | `/admin/pedidos/pedido/` |
| Grupos | `/admin/auth/group/` |
| Catálogo público | `/catalogo/<slug>/` |

---

## ⚠️ Limites e Melhorias em Andamento

- A segmentação fina de permissões por `role` (além do isolamento por empresa e do
  controle de superadmin) será refinada por grupo de permissões.
- O Bot de Atendimento no WhatsApp está no roadmap.

---

<p align="center"><b>Desenvolvido por BritosCode Tecnologia | Josemar Brito</b></p>

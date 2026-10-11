# Manual — Permissões e Roles (RBAC)

O ERP é **mono-empresa** e controla o acesso por **perfil (role)** do usuário, e não
pelas permissões nativas do Django. Cada módulo do painel exibe apenas o que o perfil
pode ver/editar.

## 1. Roles disponíveis
| Role (código) | Nome amigável | Escopo |
| --- | --- | --- |
| **SUPERADMIN** | Superadmin | Acesso total ao sistema (equivale ao administrador). |
| **GERENTE** | Gerente | Acesso total, incluindo dados cadastrais e financeiro. |
| **COMPRAS** | Compras | Produtos, catálogo e pedidos. Sem financeiro. |
| **VENDAS** | Vendas | Clientes, pedidos e catálogo. Sem financeiro. |
| **FINANCEIRO** | Financeiro | Somente o módulo Financeiro (contas e caixa). |
| **AUDITOR** | Auditor / Visitante | **Somente leitura**: enxerga todos os módulos, mas não cria, altera nem exclui. |

> Observação: no cadastro, "Vendas" corresponde ao papel de **Vendedor** e
> "Compras" ao papel de **Compras/Estoque**. Ambos **não** têm acesso ao financeiro.

## 2. Matriz de acesso por módulo
| Módulo | SUPERADMIN | GERENTE | VENDAS | COMPRAS | FINANCEIRO | AUDITOR |
| --- | --- | --- | --- | --- | --- | --- |
| Produtos / SKUs | ✅ | ✅ | ✅ | ✅ | ⛔ | 👁️ |
| Clientes | ✅ | ✅ | ✅ | — | ⛔ | 👁️ |
| Pedidos / Vendas | ✅ | ✅ | ✅ | ✅ | ⛔ | 👁️ |
| Financeiro / Caixa | ✅ | ✅ | ⛔ | ⛔ | ✅ | 👁️ |
| Usuários / Confecção | ✅ | ✅ | ⛔ | ⛔ | ⛔ | 👁️ |

Legenda: ✅ leitura e edição · 👁️ somente leitura · ⛔ sem acesso · — não exibido.

## 3. Regras gerais
- **Superusuário do Django** (`is_superuser`) sempre tem acesso total.
- O perfil **FINANCEIRO** enxerga exclusivamente o bloco Financeiro.
- O perfil **AUDITOR** é somente leitura: por definição, `has_add_permission`,
  `has_change_permission` e `has_delete_permission` retornam **False**; já
  `has_view_permission` retorna **True**.
- As telas de edição ficam bloqueadas (salvar/excluir) para readonly.

## 4. Assistente Silk e segurança
- O Assistente **Silk** respeita as roles: ao pedir ajuda de um módulo sem permissão,
  ele responde com uma mensagem educada de bloqueio.
- Exemplo: um usuário **VENDAS** pedindo ajuda no **Financeiro** recebe:
  *"Sua role Vendas não possui acesso às informações do módulo financeiro."*

## 5. Boas práticas
- Conceda o menor privilégio necessário para a função.
- Use **AUDITOR** para auditorias e visitas sem risco de alteração.
- Revise periodicamente os usuários e suas roles.

# Manual — Financeiro e Caixa

Módulo responsável pelo controle de **Contas a Receber**, **Contas a Pagar** e
**Movimentações de Caixa**. Acesso restrito aos perfis **SUPERADMIN**, **GERENTE**,
**FINANCEIRO** e **AUDITOR** (somente leitura).

## 1. Contas a Receber
- Menu: **Financeiro → Caixa de Pedidos**.
- Representa valores a receber de clientes ou de origem externa.
- Campos principais: **Cliente/Origem**, **Pedido** (quando vinculado),
  **Valor**, **Data de Vencimento**, **Data de Recebimento**, **Forma de Pagamento**
  e **Status**.
- Status: **Pendente**, **Recebido (Pago)**, **Faturado/Aprovado**, **Atrasado** e **Cancelado**.
- **Parcelas:** um pedido faturado pode gerar várias parcelas (contas a receber) com
  vencimentos distintos, somando o valor total do pedido.
- **Liberação do pedido:** contas **Pago** ou **Faturado/Aprovado** liberam o pedido
  para produção/expedição. Contas **Pendentes** mantêm a trava financeira.
- Contas vencidas e não pagas passam automaticamente para **Atrasado**.

## 2. Contas a Pagar
- Menu: **Financeiro → Contas a Pagar**.
- Despesas da fábrica (matéria-prima, folha, operacional, impostos).
- Categorias: **Matéria-Prima**, **Folha de Pagamento**, **Operacional**,
  **Impostos** e **Outros**.
- Campos principais: **Fornecedor/Credor**, **Descrição**, **Valor**,
  **Data de Vencimento**, **Data de Pagamento** e **Status**.
- Status: **Pendente**, **Pago**, **Atrasado** e **Cancelado**.

## 3. Caixa Diário e Movimentações
- Menu: **Financeiro → Caixa Diário** e **Financeiro → Movimentações**.
- O **Caixa Diário** é o caixa físico do dia: saldo inicial + entradas − saídas = saldo final.
- Cada lançamento é uma **Movimentação de Caixa**:
  - **Entrada** — recebimentos (vinculáveis a uma Conta a Receber ou a um Pedido).
  - **Saída** — pagamentos (vinculáveis a uma Conta a Pagar).
- O operador que lança a movimentação fica registrado no histórico.

## 4. Regras importantes
- Marcar uma conta a receber como **Recebida** gera automaticamente uma **entrada** no caixa.
- Marcar uma conta a pagar como **Paga** gera automaticamente uma **saída** no caixa.
- O status financeiro do pedido é **sincronizado** com a situação da Conta a Receber.
- Existe **um caixa por dia** (único por empresa e data).

## 5. Passo a passo rápido
1. Confirme o recebimento em **Caixa de Pedidos** (ou crie a conta avulsa).
2. Registre despesas em **Contas a Pagar** e marque como pagas quando quitadas.
3. Acompanhe o **Caixa Diário** e as **Movimentações** para fechar o dia.

## 6. Boas práticas
- Nunca receba sem dar baixa na Conta a Receber (mantém a auditoria).
- Confira o vínculo com o pedido para não divergir o valor total.
- Feche o caixa diariamente e registre observações de divergências.

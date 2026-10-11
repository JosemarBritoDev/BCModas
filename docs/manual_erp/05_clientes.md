# Manual — Clientes

Módulo responsável pelo cadastro dos compradores da fábrica. Os dados ficam
vinculados aos **Pedidos**, garantindo a auditoria (LGPD) de cada venda.

## 1. Cadastro do cliente
- Menu: **Clientes → Adicionar**.
- Campos principais: **Nome/Razão Social**, **Tipo de Pessoa** (PF ou PJ),
  **CPF/CNPJ**, **WhatsApp**, **E-mail** e **Ativo**.
- Endereço opcional: CEP, endereço, número, bairro, cidade e estado.

## 2. Pessoa Física vs Pessoa Jurídica
- **Pessoa Física (PF)** — cliente pessoa comum; documento é o **CPF**.
- **Pessoa Jurídica (PJ)** — empresa; documento é o **CNPJ**.
- O campo **Tipo de Pessoa** define qual documento é informado no registro.

## 3. Vínculo com pedidos
- O cliente é selecionado na criação do **Pedido**.
- Caso ainda não exista um cliente, é possível preencher nome, documento e
  WhatsApp manualmente no próprio pedido.
- O histórico do relacionamento fica registrado em todos os pedidos vinculados.

## 4. Ativar / inativar cliente
- O campo **Ativo** controla a disponibilidade do cliente no dia a dia.
- Desmarcar **Ativo** e salvar inativa o cliente sem apagar o cadastro nem o
  histórico de pedidos.

## 5. Auditoria
- **Criado em** e **Atualizado em** registram a data das alterações.
- **Último login** mostra quando o cliente acessou o catálogo (quando aplicável).
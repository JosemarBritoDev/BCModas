# Manual — Pedidos e Vendas

Este módulo cobre o ciclo de venda: criação do pedido, inclusão de itens,
vínculo com o cliente e o fluxo de status até a entrega.

## 1. Fluxo de status do pedido
| Status | Significado |
| --- | --- |
| **Aguardando Pagamento** (Pendente) | Pedido registrado, aguardando confirmação financeira. |
| **Pago / Liberado** | Pagamento confirmado; produção liberada. |
| **Em Produção** | Peça em fabricação/estamparia. |
| **Em Separação** | Peça pronta sendo separada. |
| **Pronto p/ Entrega** | Aguardando retirada/entrega. |
| **Enviado** | Enviado ao cliente. |
| **Entregue** | Recebido pelo cliente. |
| **Concluído** | Pedido encerrado. |
| **Cancelado** | Pedido cancelado. |

> **Trava financeira:** pedidos **não avançam** para produção, separação, entrega ou
> conclusão enquanto o pagamento não estiver confirmado (status financeiro
> **Pago / Liberado** ou **Faturado Atacado**, ou uma Conta a Receber **Paga/Faturada**).

## 2. Status financeiro
- **Aguardando Pagamento** — nada recebido.
- **Pago / Liberado** — pagamento à vista confirmado.
- **Faturado Atacado** — venda faturada (prazo/acordo), libera o pedido.
- **Cancelado** — sem movimentação financeira.

## 3. Criar um pedido
1. Menu: **Pedidos → Adicionar**.
2. Selecione o **Cliente** (ou preencha nome, documento e WhatsApp manualmente).
3. Escolha a **Forma de Pagamento** (Pix, Crédito, Débito) e o **Tipo de Entrega**
   (Retirar no Local ou Entrega a Combinar — esta aplica a taxa de entrega padrão).
4. Em **Itens**, adicione um ou mais SKUs informando **Quantidade** e **Preço Unitário**.
5. Confira o **Valor Total** e salve.

## 4. Inclusão de itens
- Cada item é um **SKU** (Modelo + Cor + Tamanho).
- O preço unitário pode ser ajustado; o sistema sugere varejo ou atacado conforme a
  quantidade e a **Qtd. Mínima Atacado** do modelo.
- O total de itens e o valor total são recalculados pelo pedido.

## 5. Vínculo com o cliente
- Ao escolher o Cliente, nome, documento e WhatsApp são preenchidos automaticamente.
- O vínculo com o cadastro do cliente mantém o histórico de compras e a auditoria (LGPD).

## 6. Emissão e financeiro
- Ao confirmar o recebimento, é gerada/atualizada a **Conta a Receber** vinculada ao pedido.
- Pedidos faturados geram **parcelas** em Contas a Receber (módulo Financeiro).

## 7. Boas práticas
- Confira o cadastro do cliente antes de fechar a venda.
- Use "Entrega a Combinar" apenas quando houver cobrança/negociação de frete.
- Avance o status somente após a confirmação financeira para manter o caixa correto.

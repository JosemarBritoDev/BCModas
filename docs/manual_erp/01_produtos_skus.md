# Manual — Produtos, Categorias e Grade de SKUs

Este módulo concentra o catálogo da confecção/estamparia: **Categorias**, **Modelos**
e a **Grade de SKUs** (variações de cor e tamanho com estoque).

## 1. Categorias
- Menu: **Produtos → Categorias**.
- A categoria organiza o menu de navegação do catálogo público.
- Campos principais: **Nome**, **Ordem** (menor aparece primeiro) e **Ativa**.
- Categorias sem produtos ativos são ocultadas automaticamente no catálogo.

## 2. Modelos (produtos)
- Menu: **Produtos → Modelos**.
- O Modelo representa o produto "pai" (ex.: *Camiseta Algodão Penteado 30.1*).
- Campos principais:
  - **Nome**, **Marca** e **Categoria**.
  - **Preço Varejo** (peça avulsa) e **Preço Atacado** (a partir da quantidade mínima).
  - **Qtd. Mínima Atacado** — quantidade necessária para aplicar o preço de atacado.
  - **Composição**, **Gramatura** e **Descrição** (exibidos no catálogo).
  - **Lançamento** — destaca o produto com selo e no menu.
  - **Fotos** (1 a 6) — usadas na vitrine.
- Regra de preço: se a quantidade do pedido atingir a **Qtd. Mínima Atacado** e houver
  preço de atacado cadastrado, o sistema aplica o valor de atacado automaticamente.

## 3. Grade de SKUs (variações)
- Menu: **Produtos → SKUs / Grade**.
- Cada **SKU** é uma combinação única de **Modelo + Cor + Tamanho**.
- Campos principais:
  - **Cor** (nome) e **Hex da Cor** (ex.: `#1E3A8A`) — usados como amostra visual.
  - **Tamanho** (PP, P, M, G, GG, XG, XGG).
  - **Estoque** (quantidade disponível da variação).
  - **Código de Barras** (opcional).
- Regra de unicidade: não é possível cadastrar dois SKUs com o mesmo
  Modelo + Cor + Tamanho.

## 4. Estoque e Variações
- O estoque é controlado **por variação (SKU)**, e não pelo modelo como um todo.
- Ao vender um item, a baixa ocorre no SKU vendido.
- Recomenda-se cadastrar pelo menos 2 a 3 variações (tamanhos/cores) por modelo.
- Para produtos sem grade (ex.: canecas), use a mesma estrutura com a cor/tamanho padrão.

## 5. Passo a passo rápido
1. Crie a **Categoria**.
2. Cadastre o **Modelo** (com preços varejo/atacado e fotos).
3. Gere a **Grade de SKUs** com cores e tamanhos e informe o **estoque**.
4. Marque o modelo como **Visível no Catálogo** para publicá-lo.

## 6. Boas práticas
- Padronize os nomes de cor (ex.: "Azul Marinho", "Verde Militar").
- Defina a **Qtd. Mínima Atacado** de acordo com a produção mínima da estamparia.
- Revise o estoque antes de campanhas para evitar pedidos sem disponibilidade.

# Auditoria e Controle de Estoque

Dashboard interativo para análise de divergências entre sistema e estoque físico, detecção de anomalias e classificação ABC de SKUs.

---

## Contexto

Empresas do setor varejista e food service enfrentam perdas operacionais causadas por divergências entre o estoque registrado no sistema e o estoque físico real. Este projeto simula um pipeline completo de auditoria de estoque — da ingestão dos dados brutos até um dashboard interativo — aplicando técnicas de análise exploratória, SQL analítico e detecção estatística de anomalias.

---

## Dataset

**Online Retail II** — UCI Machine Learning Repository  
Transações reais de um varejista britânico entre 2009 e 2011.  
Fonte: https://archive.ics.uci.edu/dataset/502/online+retail+ii  
Licença: CC BY 4.0

| Atributo | Valor |
|---|---|
| Linhas brutas | ~1.000.000 |
| Período | Dez/2009 – Dez/2011 |
| SKUs únicos | 4.727 |
| Notas fiscais | 36.216 |
| Receita total (UK) | £17.288.434 |

---

## Estrutura do Projeto

```
auditoria-estoque/
├── 01_ingestao_limpeza.py       # Ingestão, limpeza e padronização
├── 02_analise_estoque_sql.py    # Análise SQL com DuckDB
├── dashboard.py                 # Dashboard interativo (Streamlit + Plotly)
├── analise_estoque.xlsx         # Tabelas exportadas (5 abas)
├── dados_limpos_vendas.parquet
├── dados_limpos_cancelamentos.parquet
└── README.md
```

---

## Pipeline

### Etapa 1 — Ingestão e Limpeza
- Padronização de colunas e tipagem
- Identificação de notas canceladas (prefixo "C")
- Remoção de registros inválidos: datas nulas, preços negativos, quantidades zero, códigos de sistema
- Separação em duas bases: vendas normais e cancelamentos

### Etapa 2 — Análise SQL (DuckDB)
- **Giro de estoque por SKU** com classificação ABC
- **Taxa de cancelamento por produto** — proxy de divergência sistema vs físico
- **Reconciliação com saldo líquido** — identifica SKUs com mais cancelamentos do que vendas (divergência crítica)
- **Sazonalidade mensal** dos top 10 SKUs
- **Picos de movimentação** por dia da semana e hora

### Etapa 3 — Detecção de Anomalias
- Série temporal mensal por SKU
- Z-score por produto: anomalias com |z| > 3
- Exportação das anomalias para aba dedicada no Excel

### Dashboard (Streamlit + Plotly)
- KPIs executivos: receita, SKUs, notas fiscais, países
- Filtros interativos por ano e país
- Curva ABC com gráfico de barras colorido
- Sazonalidade mensal de vendas
- Top 20 SKUs por taxa de cancelamento
- Scatter plot de anomalias com linhas de threshold
- Tabela de SKUs com divergência crítica (saldo negativo)

---

## Como Rodar

**1. Instalar dependências**
```bash
pip install pandas numpy duckdb openpyxl pyarrow streamlit plotly
```

**2. Baixar o dataset**  
Acesse https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci  
Salve o arquivo `online_retail_II.csv` na pasta do projeto.

**3. Rodar o pipeline**
```bash
python 01_ingestao_limpeza.py
python 02_analise_estoque_sql.py
```

**4. Abrir o dashboard**
```bash
streamlit run dashboard.py
```

---

## Principais Resultados

- Classe A: 20% dos SKUs concentram ~58% da receita total
- Taxa média de cancelamento entre os produtos mais vendidos: ~8%
- SKUs com saldo líquido negativo identificados como divergências críticas para auditoria prioritária
- Anomalias detectadas via Z-score revelam picos sazonais e possíveis erros de lançamento

---

## Tecnologias

| Ferramenta | Uso |
|---|---|
| Python 3.14 | Pipeline geral |
| pandas | Manipulação de dados |
| DuckDB | SQL analítico in-memory |
| Streamlit | Dashboard interativo |
| Plotly | Visualizações |
| openpyxl | Export Excel |
| pyarrow | Serialização Parquet |

---

## Autor

Lucas Pinheiro Magalhães  
Estudante de Estatística — Universidade Federal do Ceará (UFC)

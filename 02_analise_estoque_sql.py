"""
Projeto: Auditoria e Controle de Estoque
Etapa 2: Análise de Estoque por SKU via SQL
Dataset: Online Retail II (UCI) — base limpa da Etapa 1
Dependências: pip install duckdb pandas pyarrow
"""

import duckdb
import pandas as pd

# ─────────────────────────────────────────────
# 1. CARREGAMENTO
# ─────────────────────────────────────────────
print("Carregando bases limpas...")
df_vendas     = pd.read_parquet("dados_limpos_vendas.parquet")
df_cancelados = pd.read_parquet("dados_limpos_cancelamentos.parquet")

# DuckDB lê DataFrames pandas diretamente — sem banco externo necessário
con = duckdb.connect()
con.register("vendas",     df_vendas)
con.register("cancelados", df_cancelados)

print(f"  vendas:      {len(df_vendas):,} linhas")
print(f"  cancelados:  {len(df_cancelados):,} linhas")


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────
def query(sql: str, titulo: str = "") -> pd.DataFrame:
    df = con.execute(sql).df()
    if titulo:
        print(f"\n{'='*55}")
        print(f"  {titulo}")
        print(f"{'='*55}")
        print(df.to_string(index=False))
    return df


# ─────────────────────────────────────────────
# 2. GIRO DE ESTOQUE POR SKU
# ─────────────────────────────────────────────
# Giro = total de unidades saídas no período.
# Classifica ABC: A = top 20% em volume, B = 20-50%, C = demais.

df_giro = query("""
    WITH saidas AS (
        SELECT
            stock_code,
            descricao,
            SUM(quantidade)                         AS unidades_vendidas,
            SUM(valor_total)                        AS receita_total,
            COUNT(DISTINCT invoice_no)              AS num_notas,
            MIN(data_nota)::DATE                    AS primeira_venda,
            MAX(data_nota)::DATE                    AS ultima_venda
        FROM vendas
        GROUP BY stock_code, descricao
    ),
    ranked AS (
        SELECT *,
            PERCENT_RANK() OVER (ORDER BY unidades_vendidas DESC) AS pct_rank
        FROM saidas
    )
    SELECT
        stock_code,
        descricao,
        unidades_vendidas,
        ROUND(receita_total, 2)                     AS receita_total,
        num_notas,
        primeira_venda,
        ultima_venda,
        CASE
            WHEN pct_rank <= 0.20 THEN 'A'
            WHEN pct_rank <= 0.50 THEN 'B'
            ELSE                       'C'
        END                                         AS classe_abc
    FROM ranked
    ORDER BY unidades_vendidas DESC
""", titulo="GIRO DE ESTOQUE POR SKU — TOP 15")

# Salva completo, imprime top 15
df_giro_top = df_giro.head(15)


# ─────────────────────────────────────────────
# 3. SAZONALIDADE MENSAL POR SKU (top 10 SKUs)
# ─────────────────────────────────────────────
top_skus = df_giro.head(10)["stock_code"].tolist()
skus_str  = ", ".join(f"'{s}'" for s in top_skus)

df_sazonalidade = query(f"""
    SELECT
        stock_code,
        ano,
        mes,
        SUM(quantidade)      AS unidades,
        ROUND(SUM(valor_total), 2) AS receita
    FROM vendas
    WHERE stock_code IN ({skus_str})
    GROUP BY stock_code, ano, mes
    ORDER BY stock_code, ano, mes
""", titulo="SAZONALIDADE MENSAL — TOP 10 SKUs")


# ─────────────────────────────────────────────
# 4. TAXA DE CANCELAMENTO POR SKU
# ─────────────────────────────────────────────
# Divergência real entre sistema e estoque físico.
# Taxa alta = produto com problema operacional ou de qualidade.

df_cancelamento = query("""
    WITH vendas_sku AS (
        SELECT stock_code, SUM(quantidade) AS qtd_vendida
        FROM vendas
        GROUP BY stock_code
    ),
    cancel_sku AS (
        SELECT stock_code, SUM(ABS(quantidade)) AS qtd_cancelada
        FROM cancelados
        GROUP BY stock_code
    )
    SELECT
        v.stock_code,
        v.qtd_vendida,
        COALESCE(c.qtd_cancelada, 0)              AS qtd_cancelada,
        ROUND(
            COALESCE(c.qtd_cancelada, 0) * 100.0
            / NULLIF(v.qtd_vendida, 0), 2
        )                                          AS taxa_cancelamento_pct
    FROM vendas_sku v
    LEFT JOIN cancel_sku c USING (stock_code)
    WHERE v.qtd_vendida > 100          -- filtra SKUs com volume relevante
    ORDER BY taxa_cancelamento_pct DESC
    LIMIT 20
""", titulo="TOP 20 SKUs — MAIOR TAXA DE CANCELAMENTO (%)")


# ─────────────────────────────────────────────
# 5. RECONCILIAÇÃO: SALDO LÍQUIDO POR SKU
# ─────────────────────────────────────────────
# Saldo = unidades vendidas - unidades canceladas.
# Saldo negativo = mais cancelamentos do que vendas registradas
# → sinal de divergência grave no sistema.

df_reconciliacao = query("""
    WITH movimentacao AS (
        SELECT stock_code, descricao, quantidade, 'VENDA' AS tipo
        FROM vendas
        UNION ALL
        SELECT stock_code, descricao, quantidade, 'CANCELAMENTO' AS tipo
        FROM cancelados
    )
    SELECT
        stock_code,
        MAX(descricao)                      AS descricao,
        SUM(quantidade)                     AS saldo_liquido_unidades,
        SUM(CASE WHEN tipo = 'VENDA'        THEN quantidade ELSE 0 END) AS total_saidas,
        SUM(CASE WHEN tipo = 'CANCELAMENTO' THEN quantidade ELSE 0 END) AS total_cancelado,
        CASE
            WHEN SUM(quantidade) < 0 THEN 'DIVERGÊNCIA CRÍTICA'
            WHEN SUM(quantidade) = 0 THEN 'ZERADO'
            ELSE 'OK'
        END                                 AS status_estoque
    FROM movimentacao
    GROUP BY stock_code
    HAVING SUM(quantidade) < 0             -- só os problemáticos
    ORDER BY saldo_liquido_unidades ASC
    LIMIT 20
""", titulo="SKUs COM DIVERGÊNCIA CRÍTICA (saldo líquido negativo)")


# ─────────────────────────────────────────────
# 6. PADRÃO TEMPORAL — DIA E HORA DE PICO
# ─────────────────────────────────────────────
# Útil para planejar auditorias: quais períodos têm maior movimentação
# e portanto maior risco de erro operacional.

df_pico = query("""
    SELECT
        dia_semana,
        hora,
        COUNT(DISTINCT invoice_no)    AS num_notas,
        SUM(quantidade)               AS unidades_movimentadas,
        ROUND(SUM(valor_total), 2)    AS receita
    FROM vendas
    GROUP BY dia_semana, hora
    ORDER BY unidades_movimentadas DESC
    LIMIT 15
""", titulo="PICOS DE MOVIMENTAÇÃO — DIA DA SEMANA × HORA")


# ─────────────────────────────────────────────
# 7. CONCENTRAÇÃO ABC — RESUMO EXECUTIVO
# ─────────────────────────────────────────────
df_abc = query("""
    WITH saidas AS (
        SELECT
            stock_code,
            SUM(quantidade)  AS unidades,
            SUM(valor_total) AS receita,
            PERCENT_RANK() OVER (ORDER BY SUM(quantidade) DESC) AS pct_rank
        FROM vendas
        GROUP BY stock_code
    ),
    classified AS (
        SELECT *,
            CASE
                WHEN pct_rank <= 0.20 THEN 'A'
                WHEN pct_rank <= 0.50 THEN 'B'
                ELSE                       'C'
            END AS classe
        FROM saidas
    )
    SELECT
        classe,
        COUNT(*)                              AS num_skus,
        SUM(unidades)                         AS total_unidades,
        ROUND(SUM(receita), 2)                AS total_receita,
        ROUND(SUM(receita) * 100.0
              / SUM(SUM(receita)) OVER (), 1) AS pct_receita
    FROM classified
    GROUP BY classe
    ORDER BY classe
""", titulo="CURVA ABC — CONCENTRAÇÃO DE RECEITA")


# ─────────────────────────────────────────────
# 8. EXPORT
# ─────────────────────────────────────────────
resultados = {
    "giro_sku":        df_giro,
    "sazonalidade":    df_sazonalidade,
    "cancelamentos":   df_cancelamento,
    "reconciliacao":   df_reconciliacao,
    "picos":           df_pico,
    "curva_abc":       df_abc,
}

OUTPUT = "analise_estoque.parquet"
# Salva o principal (giro completo) em parquet para a próxima etapa
df_giro.to_parquet(OUTPUT, index=False)

# Salva todas as tabelas em Excel (uma aba cada)
EXCEL_OUTPUT = "analise_estoque_tabelas.xlsx"
with pd.ExcelWriter(EXCEL_OUTPUT, engine="openpyxl") as writer:
    for aba, df in resultados.items():
        df.to_excel(writer, sheet_name=aba[:31], index=False)

print(f"\nExportado:")
print(f"  {OUTPUT}           ← base para Etapa 3 (anomalias)")
print(f"  {EXCEL_OUTPUT}  ← tabelas prontas para o Excel final")
print("\nEtapa 2 concluída. Próximo: 03_deteccao_anomalias.py")

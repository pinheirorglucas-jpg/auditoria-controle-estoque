"""
Projeto: Auditoria e Controle de Estoque
Etapa 1: Ingestão e Limpeza de Dados
Dataset: Online Retail II (UCI Machine Learning Repository)
Fonte: https://archive.ics.uci.edu/dataset/502/online+retail+ii
Licença: CC BY 4.0
"""

import pandas as pd
import numpy as np
import os

# ─────────────────────────────────────────────
# 1. DOWNLOAD DO DATASET
# ─────────────────────────────────────────────
# O dataset está disponível no UCI via ucimlrepo ou direto no Kaggle.
# Para instalar: pip install ucimlrepo
#
# Alternativamente, baixe o arquivo .xlsx manualmente em:
# https://archive.ics.uci.edu/dataset/502/online+retail+ii
# e ajuste o caminho em RAW_PATH abaixo.

try:
    from ucimlrepo import fetch_ucirepo
    print("Baixando dataset do UCI...")
    online_retail_ii = fetch_ucirepo(id=502)
    df_raw = pd.concat(
        [online_retail_ii.data.features, online_retail_ii.data.targets],
        axis=1
    )
    print(f"Dataset carregado via ucimlrepo: {df_raw.shape[0]:,} linhas")

except Exception as e:
    print(f"ucimlrepo falhou ({e}). Tentando carregar arquivo local...")
    RAW_PATH = "online_retail_II.xlsx"  # ajuste se necessário
    if not os.path.exists(RAW_PATH):
        raise FileNotFoundError(
            "Arquivo não encontrado. Baixe em: "
            "https://archive.ics.uci.edu/dataset/502/online+retail+ii"
        )
    df_raw = pd.read_excel(RAW_PATH, sheet_name=None)
    df_raw = pd.concat(df_raw.values(), ignore_index=True)
    print(f"Dataset carregado via arquivo local: {df_raw.shape[0]:,} linhas")


# ─────────────────────────────────────────────
# 2. INSPEÇÃO INICIAL
# ─────────────────────────────────────────────
print("\n" + "="*50)
print("INSPEÇÃO INICIAL")
print("="*50)
print(f"Shape: {df_raw.shape}")
print(f"\nColunas: {list(df_raw.columns)}")
print(f"\nTipos:\n{df_raw.dtypes}")
print(f"\nNulos por coluna:\n{df_raw.isnull().sum()}")
print(f"\nAmostra:\n{df_raw.head(3)}")


# ─────────────────────────────────────────────
# 3. PADRONIZAÇÃO DE COLUNAS
# ─────────────────────────────────────────────
# O UCI às vezes retorna nomes ligeiramente diferentes do .xlsx original.
# Mapeamos para um padrão único aqui.

COLUMN_MAP = {
    # possíveis variações → nome padronizado
    "Invoice":      "invoice_no",
    "InvoiceNo":    "invoice_no",
    "StockCode":    "stock_code",
    "Description":  "descricao",
    "Quantity":     "quantidade",
    "InvoiceDate":  "data_nota",
    "Price":        "preco_unit",
    "UnitPrice":    "preco_unit",
    "Customer ID":  "customer_id",
    "CustomerID":   "customer_id",
    "Country":      "pais",
}

df = df_raw.rename(columns=COLUMN_MAP)

# Garante que todas as colunas esperadas existem
COLS_ESPERADAS = [
    "invoice_no", "stock_code", "descricao",
    "quantidade", "data_nota", "preco_unit",
    "customer_id", "pais"
]
faltando = [c for c in COLS_ESPERADAS if c not in df.columns]
if faltando:
    raise ValueError(f"Colunas não encontradas após mapeamento: {faltando}")

df = df[COLS_ESPERADAS].copy()
print(f"\nColunas padronizadas: {list(df.columns)}")


# ─────────────────────────────────────────────
# 4. TIPAGEM
# ─────────────────────────────────────────────
df["data_nota"]    = pd.to_datetime(df["data_nota"], errors="coerce")
df["quantidade"]   = pd.to_numeric(df["quantidade"], errors="coerce")
df["preco_unit"]   = pd.to_numeric(df["preco_unit"], errors="coerce")
df["invoice_no"]   = df["invoice_no"].astype(str).str.strip()
df["stock_code"]   = df["stock_code"].astype(str).str.strip().str.upper()
df["descricao"]    = df["descricao"].astype(str).str.strip().str.title()
df["pais"]         = df["pais"].astype(str).str.strip()
df["customer_id"]  = pd.to_numeric(df["customer_id"], errors="coerce")


# ─────────────────────────────────────────────
# 5. IDENTIFICAÇÃO DE CANCELAMENTOS
# ─────────────────────────────────────────────
# Notas fiscais canceladas começam com "C" — são divergências reais a auditar.
df["cancelado"] = df["invoice_no"].str.startswith("C")

n_cancelamentos = df["cancelado"].sum()
print(f"\nNotas canceladas: {n_cancelamentos:,} "
      f"({n_cancelamentos / len(df) * 100:.1f}%)")


# ─────────────────────────────────────────────
# 6. REMOÇÃO DE REGISTROS INVÁLIDOS
# ─────────────────────────────────────────────
print("\n" + "="*50)
print("LIMPEZA")
print("="*50)

n_inicial = len(df)
log_limpeza = {}

# 6a. Datas inválidas (NaT após coerção)
mask_data_invalida = df["data_nota"].isna()
log_limpeza["data_nota nula"] = mask_data_invalida.sum()
df = df[~mask_data_invalida]

# 6b. Preço negativo ou nulo (exceto cancelamentos que já têm quantidade negativa)
#     Um preço zero ou negativo em nota normal é suspeito.
mask_preco_invalido = (df["preco_unit"] <= 0) & (~df["cancelado"])
log_limpeza["preco_unit <= 0 (não cancelado)"] = mask_preco_invalido.sum()
df = df[~mask_preco_invalido]

# 6c. Quantidade zero (não gera movimentação de estoque)
mask_qtd_zero = df["quantidade"] == 0
log_limpeza["quantidade == 0"] = mask_qtd_zero.sum()
df = df[~mask_qtd_zero]

# 6d. stock_code com padrão claramente não-produto
#     (ajustes internos, postagens manuais etc.)
CODIGOS_SISTEMA = {"POST", "D", "C2", "M", "BANK CHARGES", "PADS", "DOT"}
mask_codigo_sistema = df["stock_code"].isin(CODIGOS_SISTEMA)
log_limpeza["stock_code de sistema"] = mask_codigo_sistema.sum()
df = df[~mask_codigo_sistema]

# 6e. Descrição vazia ou "nan"
mask_desc_vazia = df["descricao"].isin(["", "Nan", "nan", "None"])
log_limpeza["descricao vazia"] = mask_desc_vazia.sum()
df = df[~mask_desc_vazia]

n_final = len(df)
print(f"Linhas removidas por motivo:")
for motivo, qtd in log_limpeza.items():
    print(f"  {motivo:<40} {qtd:>7,}")
print(f"\nTotal removido: {n_inicial - n_final:,} linhas "
      f"({(n_inicial - n_final) / n_inicial * 100:.1f}%)")
print(f"Linhas restantes: {n_final:,}")


# ─────────────────────────────────────────────
# 7. FEATURES DERIVADAS
# ─────────────────────────────────────────────
df["valor_total"]    = df["quantidade"] * df["preco_unit"]
df["ano"]            = df["data_nota"].dt.year
df["mes"]            = df["data_nota"].dt.month
df["dia_semana"]     = df["data_nota"].dt.day_name()
df["hora"]           = df["data_nota"].dt.hour

# Separar bases: vendas normais vs cancelamentos
df_vendas      = df[~df["cancelado"]].copy()
df_cancelados  = df[ df["cancelado"]].copy()

print(f"\nVendas normais:   {len(df_vendas):,} linhas")
print(f"Cancelamentos:    {len(df_cancelados):,} linhas")


# ─────────────────────────────────────────────
# 8. RESUMO DE QUALIDADE FINAL
# ─────────────────────────────────────────────
print("\n" + "="*50)
print("RESUMO FINAL DA BASE LIMPA")
print("="*50)
print(f"Período: {df['data_nota'].min().date()} → {df['data_nota'].max().date()}")
print(f"SKUs únicos:      {df['stock_code'].nunique():,}")
print(f"Clientes únicos:  {df['customer_id'].nunique():,}")
print(f"Países:           {df['pais'].nunique()}")
print(f"Customer_id nulo: {df['customer_id'].isna().sum():,} "
      f"({df['customer_id'].isna().mean()*100:.1f}%) "
      f"← mantidos (transações sem cadastro são válidas para estoque)")
print(f"\nValor total movimentado: £{df_vendas['valor_total'].sum():,.2f}")
print(f"Ticket médio por nota:   £{df_vendas.groupby('invoice_no')['valor_total'].sum().mean():,.2f}")


# ─────────────────────────────────────────────
# 9. EXPORT
# ─────────────────────────────────────────────
OUTPUT_VENDAS     = "dados_limpos_vendas.parquet"
OUTPUT_CANCELADOS = "dados_limpos_cancelamentos.parquet"

df_vendas.to_parquet(OUTPUT_VENDAS, index=False)
df_cancelados.to_parquet(OUTPUT_CANCELADOS, index=False)

print(f"\nArquivos exportados:")
print(f"  {OUTPUT_VENDAS}")
print(f"  {OUTPUT_CANCELADOS}")
print("\nEtapa 1 concluída. Próximo: 02_analise_estoque_sql.py")

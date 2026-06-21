
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(page_title="Auditoria de Estoque", layout="wide")

# ── Carregamento ──────────────────────────────────────
@st.cache_data
def carregar():
    vendas     = pd.read_parquet("dados_limpos_vendas.parquet")
    cancelados = pd.read_parquet("dados_limpos_cancelamentos.parquet")
    return vendas, cancelados

df_vendas, df_cancelados = carregar()

# ── Sidebar ───────────────────────────────────────────
st.sidebar.title("Filtros")
anos = sorted(df_vendas["ano"].unique())
ano_sel = st.sidebar.multiselect("Ano", anos, default=anos)
paises = sorted(df_vendas["pais"].unique())
pais_sel = st.sidebar.multiselect("País", paises, default=["United Kingdom"])

df = df_vendas[df_vendas["ano"].isin(ano_sel) & df_vendas["pais"].isin(pais_sel)]

# ── KPIs ──────────────────────────────────────────────
st.title("Dashboard de Auditoria e Controle de Estoque")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Receita Total", f"£{df['valor_total'].sum():,.0f}")
k2.metric("SKUs Únicos",   f"{df['stock_code'].nunique():,}")
k3.metric("Notas Fiscais", f"{df['invoice_no'].nunique():,}")
k4.metric("Países",        f"{df['pais'].nunique()}")

st.divider()

# ── Curva ABC ─────────────────────────────────────────
st.subheader("Curva ABC — Concentração de Receita")
abc = df.groupby("stock_code").agg(
    receita=("valor_total","sum"),
    unidades=("quantidade","sum")
).reset_index()
abc = abc.sort_values("receita", ascending=False)
abc["pct_rank"] = np.arange(len(abc)) / len(abc)
abc["classe"] = abc["pct_rank"].apply(
    lambda x: "A" if x<=0.20 else ("B" if x<=0.50 else "C")
)
resumo_abc = abc.groupby("classe").agg(
    skus=("stock_code","count"),
    receita=("receita","sum")
).reset_index()
resumo_abc["pct_receita"] = resumo_abc["receita"] / resumo_abc["receita"].sum() * 100

fig_abc = px.bar(resumo_abc, x="classe", y="pct_receita",
    color="classe", text_auto=".1f",
    labels={"pct_receita":"% da Receita","classe":"Classe"},
    color_discrete_map={"A":"#2ecc71","B":"#f39c12","C":"#e74c3c"})
st.plotly_chart(fig_abc, use_container_width=True)

st.divider()

# ── Sazonalidade ──────────────────────────────────────
st.subheader("Sazonalidade Mensal de Vendas")
saz = df.groupby(["ano","mes"])["valor_total"].sum().reset_index()
saz["periodo"] = saz["ano"].astype(str) + "-" + saz["mes"].astype(str).str.zfill(2)
fig_saz = px.line(saz, x="periodo", y="valor_total",
    labels={"periodo":"Período","valor_total":"Receita (£)"},
    markers=True)
st.plotly_chart(fig_saz, use_container_width=True)

st.divider()

# ── Taxa de Cancelamento ──────────────────────────────
st.subheader("Top 20 SKUs — Taxa de Cancelamento (%)")
v = df.groupby("stock_code")["quantidade"].sum().reset_index(name="vendido")
c = df_cancelados.groupby("stock_code")["quantidade"].apply(
    lambda x: x.abs().sum()
).reset_index(name="cancelado")
canc = v.merge(c, on="stock_code", how="left").fillna(0)
canc = canc[canc["vendido"]>100]
canc["taxa"] = canc["cancelado"] / canc["vendido"] * 100
canc = canc.sort_values("taxa", ascending=False).head(20)
canc = canc.merge(
    df[["stock_code","descricao"]].drop_duplicates(),
    on="stock_code", how="left"
)
fig_canc = px.bar(canc, x="taxa", y="descricao", orientation="h",
    labels={"taxa":"Taxa (%)","descricao":"Produto"},
    color="taxa", color_continuous_scale="Reds")
fig_canc.update_layout(yaxis={"categoryorder":"total ascending"})
st.plotly_chart(fig_canc, use_container_width=True)

st.divider()

# ── Anomalias ─────────────────────────────────────────
st.subheader("Anomalias Detectadas por Z-score")
serie = df.groupby(["stock_code","ano","mes"])["quantidade"].sum().reset_index()
serie["media"]  = serie.groupby("stock_code")["quantidade"].transform("mean")
serie["desvio"] = serie.groupby("stock_code")["quantidade"].transform("std")
serie["zscore"] = (serie["quantidade"] - serie["media"]) / serie["desvio"].replace(0, np.nan)
anom = serie[serie["zscore"].abs() > 3].copy()
anom = anom.merge(df[["stock_code","descricao"]].drop_duplicates(), on="stock_code", how="left")
anom = anom.sort_values("zscore", key=abs, ascending=False)

st.metric("Total de Anomalias", len(anom))
fig_anom = px.scatter(anom, x="mes", y="zscore",
    color="ano", hover_data=["descricao","quantidade"],
    labels={"zscore":"Z-score","mes":"Mês"},
    title="Distribuição das Anomalias")
fig_anom.add_hline(y=3,  line_dash="dash", line_color="red")
fig_anom.add_hline(y=-3, line_dash="dash", line_color="red")
st.plotly_chart(fig_anom, use_container_width=True)
st.dataframe(anom[["stock_code","descricao","ano","mes","quantidade","zscore"]].reset_index(drop=True))

st.divider()

# ── Divergências Críticas ─────────────────────────────
st.subheader("SKUs com Divergência Crítica")
mov = pd.concat([df[["stock_code","descricao","quantidade"]],
                 df_cancelados[["stock_code","descricao","quantidade"]]])
saldo = mov.groupby(["stock_code","descricao"])["quantidade"].sum().reset_index(name="saldo")
criticos = saldo[saldo["saldo"]<0].sort_values("saldo")
st.metric("SKUs com Saldo Negativo", len(criticos))
st.dataframe(criticos.reset_index(drop=True))

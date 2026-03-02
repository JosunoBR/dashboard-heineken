import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da página
st.set_page_config(page_title="Dashboard Operação Heineken", layout="wide")

# Estilização customizada para um visual mais moderno
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    /* Força a cor do texto das métricas para garantir visibilidade sobre o fundo branco */
    [data-testid="stMetricValue"] > div { color: #1f2937 !important; }
    [data-testid="stMetricLabel"] > div { color: #4b5563 !important; }
    </style>
    """, unsafe_allow_html=True)

# URL de exportação direta para CSV (mais estável que a API de edição)
# O gid=316476550 identifica a aba "HEINEKEN"
SHEET_ID = "1f3DubkiqNVYsOd_arblxpYAEVwv4qRIhsI9cdMR99EU"
GID = "316476550"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

@st.cache_data
def load_data():
    try:
        # Pula as linhas anteriores para ler a partir da linha 1157 (mantendo o cabeçalho da linha 1)
        # range(1, 1156) pula as linhas de índice 1 a 1155 (que correspondem às linhas 2 a 1156 no Excel)
        return pd.read_csv(CSV_URL, skiprows=range(1, 1156))
    except Exception as e:
        st.error(f"Erro ao carregar a planilha: {e}")
        return None

df = load_data()

if df is not None:
    st.title("📊 Auditoria de Pendências - Heineken")
    
    col_title, col_refresh = st.columns([4, 1])
    with col_title:
        st.subheader("Monitoramento de Preenchimento (Últimas 3 Colunas)")
    with col_refresh:
        if st.button("🔄 Atualizar Dados"):
            st.cache_data.clear()
            st.rerun()

    # --- LÓGICA DE ANÁLISE DAS 3 ÚLTIMAS COLUNAS ---
    colunas_totais = df.columns.tolist()
    ultimas_3_cols = colunas_totais[-3:]
    
    # Criamos uma função auxiliar para verificar se o conteúdo é um "OK" válido
    def verificar_ok(valor):
        return str(valor).strip().lower() == "ok"

    # Verificamos cada uma das 3 colunas
    check_cols = df[ultimas_3_cols].applymap(verificar_ok)
    
    # Uma linha é pendente se pelo menos uma das colunas NÃO tiver "ok"
    mask_pendente = ~check_cols.all(axis=1)
    df_pendencias = df[mask_pendente].copy()

    # Adicionamos uma coluna informativa para mostrar o que falta preencher
    def listar_faltantes(row):
        faltam = [col for col in ultimas_3_cols if not verificar_ok(row[col])]
        return ", ".join(faltam)

    if not df_pendencias.empty:
        df_pendencias["⚠️ Colunas Faltantes"] = df_pendencias.apply(listar_faltantes, axis=1)

    # --- INDICADORES (METRICS) ---
    st.markdown("### 📈 Resumo de Qualidade")
    m1, m2, m3 = st.columns(3)
    
    total_viagens = len(df)
    total_pendentes = len(df_pendencias)
    taxa_preenchimento = ((total_viagens - total_pendentes) / total_viagens * 100) if total_viagens > 0 else 0

    m1.metric("Total de Viagens", total_viagens)
    m2.metric("Viagens com Alguma Pendência", total_pendentes, delta_color="inverse")
    m3.metric("Taxa de Integridade", f"{taxa_preenchimento:.1f}%")

    st.markdown("#### 🔍 Pendências Específicas por Assunto")
    c1, c2, c3 = st.columns(3)
    cols_metrics = [c1, c2, c3]
    dt_col_name = df.columns[0]  # Assume que a coluna A (DT) é a primeira
    
    # Cálculo e exibição de pendências independentes
    for i, col in enumerate(ultimas_3_cols):
        qtd_pendente_col = (~check_cols[col]).sum()
        with cols_metrics[i]:
            st.metric(label=f"Pendentes: {col}", value=qtd_pendente_col)
            # Botão para ativar a visualização da lista de DTs
            if st.button(f"📋 Ver DTs: {col}", key=f"btn_{col}"):
                st.session_state.selected_dt_col = col

    # Se um assunto foi selecionado, exibe a lista de DTs logo abaixo
    if "selected_dt_col" in st.session_state:
        col_alvo = st.session_state.selected_dt_col
        st.info(f"### 📄 DTs Pendentes - {col_alvo}")
        # Filtra as DTs onde a coluna específica não tem "ok"
        lista_dts = df.loc[~df[col_alvo].apply(verificar_ok), [dt_col_name]]
        st.dataframe(lista_dts, use_container_width=True, hide_index=True)
        if st.button("✖️ Fechar Lista"):
            del st.session_state.selected_dt_col
            st.rerun()

    st.divider()

    # --- VISUALIZAÇÃO DE DADOS ---
    tab1, tab2 = st.tabs(["⚠️ Lista de Pendências", "📊 Análise por Campo"])

    with tab1:
        if not df_pendencias.empty:
            st.markdown(f"#### Detalhamento de Pendências")
            
            # Filtro para isolar pendências de um assunto específico
            filtro_assunto = st.selectbox("Filtrar lista por coluna específica:", ["Mostrar Todas"] + ultimas_3_cols)
            
            df_exibir = df_pendencias.copy()
            if filtro_assunto != "Mostrar Todas":
                df_exibir = df_exibir[~df_exibir[filtro_assunto].apply(verificar_ok)]

            # Reordenar para mostrar a coluna de aviso primeiro
            cols_view = ["⚠️ Colunas Faltantes"] + [c for c in df_exibir.columns if c != "⚠️ Colunas Faltantes"]
            st.dataframe(df_exibir[cols_view], use_container_width=True)
            
            # Botão para exportar apenas o que falta preencher
            csv = df_exibir.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Baixar Lista de Pendências (CSV)", csv, "pendencias_operacao.csv", "text/csv")
        else:
            st.success("✅ Excelente! Todas as colunas monitoradas estão 100% preenchidas.")

    with tab2:
        # Contagem de vazios por coluna específica
        stats_vazios = []
        for col in ultimas_3_cols:
            # Conta quantos não têm "ok"
            pendentes_col = (~df[col].apply(verificar_ok)).sum()
            stats_vazios.append({"Coluna": col, "Qtd. Pendentes": pendentes_col})
        
        df_stats = pd.DataFrame(stats_vazios)
        
        fig_bar = px.bar(df_stats, x="Coluna", y="Qtd. Pendentes", 
                         text="Qtd. Pendentes", title="Pendências de 'ok' por Coluna",
                         color="Coluna", color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig_bar, use_container_width=True)

        st.info(f"**Nota:** As colunas analisadas são as 3 últimas encontradas na aba HEINEKEN: {', '.join(ultimas_3_cols)}")

else:
    st.info("Aguardando conexão com a planilha Google Sheets.")

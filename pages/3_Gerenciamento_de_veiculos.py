import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Gerenciamento de Veículos", layout="wide")

st.title("🚚 Gerenciamento de Veículos")

# URL de exportação direta
SHEET_ID = "1f3DubkiqNVYsOd_arblxpYAEVwv4qRIhsI9cdMR99EU"
GID = "316476550"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

@st.cache_data(ttl=60)
def load_data():
    try:
        # Pula as linhas anteriores para ler a partir da linha 1157 (mantendo o cabeçalho da linha 1)
        return pd.read_csv(CSV_URL, skiprows=range(1, 1156))
    except Exception as e:
        st.error(f"Erro ao carregar a planilha: {e}")
        return None

df_raw = load_data()

if df_raw is not None:
    col_refresh, _ = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 Atualizar Dados"):
            st.cache_data.clear()
            st.rerun()

    # C=2, M=12, U=20, V=21, X=23, Y=24, Z=25
    if len(df_raw.columns) > 25:
        col_data_c = df_raw.columns[2]
        col_placa = df_raw.columns[12]
        col_chegada_coleta = df_raw.columns[20]
        col_saida_coleta = df_raw.columns[21]
        col_agenda_descarga = df_raw.columns[23]
        col_chegada_cliente = df_raw.columns[24]
        col_saida_descarga = df_raw.columns[25]

        colunas_necessarias = [
            col_data_c, col_placa, col_chegada_coleta, col_saida_coleta, 
            col_agenda_descarga, col_chegada_cliente, col_saida_descarga
        ]
        
        df = df_raw[colunas_necessarias].copy()
        
        # 1. Limpeza de placas vazias
        df = df[df[col_placa].notna() & (df[col_placa].astype(str).str.strip() != "")]
        
        def parse_dates(series):
            return pd.to_datetime(series, errors='coerce', dayfirst=True)

        # Tratar colunas de tempo
        for col in [col_chegada_coleta, col_saida_coleta, col_chegada_cliente, col_saida_descarga]:
            df[f"{col}_dt"] = parse_dates(df[col])

        # Achar a data do evento mais recente da linha
        df['Ultimo_Evento_Dt'] = df[[
            f"{col_chegada_coleta}_dt", f"{col_saida_coleta}_dt", 
            f"{col_chegada_cliente}_dt", f"{col_saida_descarga}_dt"
        ]].max(axis=1)

        # 2. Filtro dos últimos 20 dias
        hoje = pd.Timestamp.now()
        limite_20_dias = hoje - pd.DateOffset(days=20)

        # Tratar a coluna base C (DATA) para usar como referência de linhas sem horários
        df[f"{col_data_c}_dt"] = parse_dates(df[col_data_c])
        df['Referencia_Filtro'] = df['Ultimo_Evento_Dt'].fillna(df[f"{col_data_c}_dt"])
        
        mask_tempo = df['Referencia_Filtro'] >= limite_20_dias
        
        df_filtrado = df[mask_tempo].copy()

        # 3. Desduplicação (manter a viagem mais atual)
        df_filtrado = df_filtrado.sort_values(by='Ultimo_Evento_Dt', ascending=False)
        df_frota = df_filtrado.drop_duplicates(subset=[col_placa], keep='first').copy()

        # 4. Lógica de Status
        def definir_status(row):
            if pd.notna(row[f"{col_saida_descarga}_dt"]):
                return "Vazio"
            elif pd.notna(row[f"{col_chegada_cliente}_dt"]):
                return "Aguardando descarga/Descarregando"
            elif pd.notna(row[f"{col_saida_coleta}_dt"]):
                return "Em viagem"
            elif pd.notna(row[f"{col_chegada_coleta}_dt"]):
                return "Em carregamento"
            else:
                return "Coleta programada"

        if not df_frota.empty:
            df_frota['Status Atual'] = df_frota.apply(definir_status, axis=1)

            st.markdown("### 📊 Visão Geral da Frota em Operação")
            
            status_counts = df_frota['Status Atual'].value_counts()
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("📦 Programada", status_counts.get("Coleta programada", 0))
            with col2:
                st.metric("🏗️ Em carreg. ", status_counts.get("Em carregamento", 0))
            with col3:
                st.metric("🚚 Em viagem", status_counts.get("Em viagem", 0))
            with col4:
                st.metric("⏳ Aguardando", status_counts.get("Aguardando descarga/Descarregando", 0))
            with col5:
                st.metric("✅ Vazio", status_counts.get("Vazio", 0))
                
            st.divider()
            
            st.markdown("### 📋  Lista de Veículos")
            
            # 5. Interface Visual
            status_filter = st.selectbox("Filtrar por Status", ["Todos"] + df_frota['Status Atual'].unique().tolist())
            
            df_view = df_frota.copy()
            if status_filter != "Todos":
                df_view = df_view[df_view['Status Atual'] == status_filter]
                
            cols_to_drop = [c for c in df_view.columns if c.endswith("_dt") or c in ["Ultimo_Evento_Dt", "Referencia_Filtro"]]
            df_view = df_view.drop(columns=cols_to_drop)
            
            cols = [col_placa, 'Status Atual'] + [c for c in df_view.columns if c not in [col_placa, 'Status Atual']]
            df_view = df_view[cols]
            
            st.dataframe(df_view, width='stretch', hide_index=True)
            
            csv = df_view.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Exportar Lista (CSV)",
                data=csv,
                file_name=f"gerenciamento_frota_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhum veículo encontrado no período analisado.")
    else:
        st.error("A planilha não possui as colunas necessárias detectadas (esperado pelo menos até a coluna Z).")
else:
    st.info("Aguardando carregamento dos dados...")

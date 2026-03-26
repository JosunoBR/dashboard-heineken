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
            parsed = pd.to_datetime(series, errors='coerce', dayfirst=True)
            # Proteção contra erros de digitação (ex: digitar 2028 ou mês 06 no lugar de 02)
            # Vai tratar como vazio (NaT) datas além de hoje, forçando usar a etapa anterior válida
            limite_futuro = pd.Timestamp.now() + pd.DateOffset(days=1)
            return parsed.where(parsed <= limite_futuro, pd.NaT)

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

        # 3. Desduplicação (baseada na ordem da planilha)
        # Mudar para manter a última ocorrência física (keep='last') da placa, 
        # garantindo imunidade total contra datas digitadas incorretamente.
        df_frota = df_filtrado.drop_duplicates(subset=[col_placa], keep='last').copy()

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
            
            # 5. Interface Visual (Cards Customizados em SVG)
            col_view_filtro, col_view_csv = st.columns([3, 1])
            with col_view_filtro:
                status_filter = st.selectbox("📌 Filtrar por Status", ["Todos"] + df_frota['Status Atual'].unique().tolist())
            
            df_view = df_frota.copy()
            if status_filter != "Todos":
                df_view = df_view[df_view['Status Atual'] == status_filter]
                
            with col_view_csv:
                st.write("") # alinhamento
                st.write("")
                csv_export = df_view.drop(columns=[c for c in df_view.columns if c.endswith('_dt') or c in ['Ultimo_Evento_Dt', 'Referencia_Filtro']]).to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exportar (CSV)",
                    data=csv_export,
                    file_name=f"gerenciamento_frota_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
                
            # Mapeamento do Visual
            cores_status = {
                "Coleta programada": "#9e9e9e",
                "Em carregamento": "#2196f3",
                "Em viagem": "#ff9800",
                "Aguardando descarga/Descarregando": "#9c27b0",
                "Vazio": "#4caf50"
            }
            bg_luz = {
                "Coleta programada": "#f5f5f5",
                "Em carregamento": "#e3f2fd",
                "Em viagem": "#fff3e0",
                "Aguardando descarga/Descarregando": "#f3e5f5",
                "Vazio": "#e8f5e9"
            }

            html_cards = "<div style='display:flex; flex-direction:column; gap:10px; margin-top:20px;'>"
            for _, row in df_view.iterrows():
                placa = row[col_placa]
                status = row['Status Atual']
                cor = cores_status.get(status, "#000000")
                bg = bg_luz.get(status, "#ffffff")
                
                # Tratar valores vazios para n dar erro no HTML
                dt_ch_coleta = str(row[col_chegada_coleta]) if pd.notna(row[col_chegada_coleta]) else "---"
                dt_sai_coleta = str(row[col_saida_coleta]) if pd.notna(row[col_saida_coleta]) else "---"
                dt_ch_cliente = str(row[col_chegada_cliente]) if pd.notna(row[col_chegada_cliente]) else "---"
                dt_sai_descarga = str(row[col_saida_descarga]) if pd.notna(row[col_saida_descarga]) else "---"
                
                # Evitar erro se o Ultimo Evento for nulo devido ao preenchimento de proteção
                data_event = row['Ultimo_Evento_Dt'] if 'Ultimo_Evento_Dt' in row and pd.notna(row['Ultimo_Evento_Dt']) else row['Referencia_Filtro']
                txt_ref = data_event.strftime("%d/%m/%Y") if pd.notna(data_event) else "?"

                html_cards += f"""
<div style="background-color: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.06); display: flex; align-items: center; border-left: 6px solid {cor}; font-family: sans-serif; margin-bottom: 10px;">
    <div style="margin-right: 25px;">
        <svg width="65" height="40" viewBox="0 0 64 40" xmlns="http://www.w3.org/2000/svg">
            <path d="M 46 15 L 53 15 L 59 23 L 59 34 L 46 34 Z" fill="#444" />
            <path d="M 48 17 L 52 17 L 56 22 L 48 22 Z" fill="#fff" />
            <circle cx="16" cy="34" r="5" fill="#222"/>
            <circle cx="51" cy="34" r="5" fill="#222"/>
            <circle cx="34" cy="34" r="5" fill="#222"/>
            <rect x="2" y="5" width="42" height="29" rx="2" fill="{cor}" />
            <text x="23" y="24" fill="#ffffff" font-size="11" font-weight="bold" text-anchor="middle">FROTA</text>
        </svg>
    </div>
    <div style="flex-grow: 1;">
        <h3 style="margin: 0; padding: 0; color: #333; font-size: 18px;">{placa}</h3>
        <div style="display: flex; gap: 20px; margin-top: 5px; color: #666; font-size: 13px;">
            <span><b>Coleta:</b> {dt_ch_coleta}</span>
            <span><b>Viagem:</b> {dt_sai_coleta}</span>
            <span><b>Descarga:</b> {dt_ch_cliente}</span>
            <span><b>Fim:</b> {dt_sai_descarga}</span>
        </div>
    </div>
    <div style="text-align: right; min-width: 150px;">
        <div style="background-color: {bg}; color: {cor}; padding: 6px 12px; border-radius: 12px; font-weight: bold; font-size: 12px; display: inline-block;">
            {status}
        </div>
        <div style="margin-top: 6px; font-size: 11px; color: #999;">Últ. Ref: {txt_ref}</div>
    </div>
</div>
"""
                
            html_cards += "</div>"
            
            if not df_view.empty:
                st.markdown(html_cards, unsafe_allow_html=True)
            else:
                st.info("Nenhum veículo corresponde a este filtro.")
        else:
            st.info("Nenhum veículo encontrado no período analisado.")
    else:
        st.error("A planilha não possui as colunas necessárias detectadas (esperado pelo menos até a coluna Z).")
else:
    st.info("Aguardando carregamento dos dados...")

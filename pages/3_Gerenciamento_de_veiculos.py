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

    # A=0, C=2, J=9, K=10, M=12, U=20, V=21, X=23, Y=24, Z=25
    if len(df_raw.columns) > 25:
        col_dt_a = df_raw.columns[0]
        col_data_c = df_raw.columns[2]
        col_origem_j = df_raw.columns[9]
        col_destino_k = df_raw.columns[10]
        col_placa = df_raw.columns[12]
        col_chegada_coleta = df_raw.columns[20]
        col_saida_coleta = df_raw.columns[21]
        col_agenda_descarga = df_raw.columns[23]
        col_chegada_cliente = df_raw.columns[24]
        col_saida_descarga = df_raw.columns[25]

        colunas_necessarias = [
            col_dt_a, col_data_c, col_origem_j, col_destino_k, col_placa, 
            col_chegada_coleta, col_saida_coleta, col_agenda_descarga, 
            col_chegada_cliente, col_saida_descarga
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
        for col in [col_chegada_coleta, col_saida_coleta, col_agenda_descarga, col_chegada_cliente, col_saida_descarga]:
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
            
            # Mapeamento Global de Estilo
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
            
            labels_curtas = {
                "Coleta programada": "PROGRAMADA",
                "Em carregamento": "CARREGANDO",
                "Em viagem": "EM VIAGEM",
                "Aguardando descarga/Descarregando": "AGUARDANDO",
                "Vazio": "VAZIO"
            }

            import urllib.parse
            
            # Recuperar filtro da URL
            status_url_param = st.query_params.get("status", "Todos")
            
            metrics_html = '<div style="display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap;">'
            
            for status in ["Coleta programada", "Em carregamento", "Em viagem", "Aguardando descarga/Descarregando", "Vazio"]:
                qtd = status_counts.get(status, 0)
                cor = cores_status[status]
                bg = bg_luz[status]
                label = labels_curtas[status]
                
                # Lógica de toggle: se já estiver selecionado, clicar novamente limpa o filtro
                if status_url_param == status:
                    href_status = "Todos"
                else:
                    href_status = urllib.parse.quote(status)
                    
                opacity = "1" if status_url_param == "Todos" or status_url_param == status else "0.4"
                
                metrics_html += f"""
<a href="?status={href_status}" target="_self" style="text-decoration: none; color: inherit; flex: 1; min-width: 120px; opacity: {opacity}; transition: transform 0.2s; display: block;" onmouseover="this.style.transform='scale(1.03)';" onmouseout="this.style.transform='scale(1)';">
<div style="background-color: white; padding: 15px 10px; border-radius: 10px; border-bottom: 5px solid {cor}; height: 100%; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); font-family: sans-serif;">
    <svg width="75" height="45" viewBox="0 0 64 40" xmlns="http://www.w3.org/2000/svg">
        <path d="M 46 15 L 53 15 L 59 23 L 59 34 L 46 34 Z" fill="#444" />
        <path d="M 48 17 L 52 17 L 56 22 L 48 22 Z" fill="#fff" />
        <circle cx="16" cy="34" r="5" fill="#222"/>
        <circle cx="51" cy="34" r="5" fill="#222"/>
        <circle cx="34" cy="34" r="5" fill="#222"/>
        <rect x="2" y="5" width="42" height="29" rx="2" fill="{cor}" />
        <text x="23" y="25" fill="#ffffff" font-size="15" font-weight="bold" text-anchor="middle">{qtd}</text>
    </svg>
    <div style="font-size: 12px; font-weight: bold; color: {cor}; text-transform: uppercase; margin-top: 8px;">
        {label}
    </div>
</div>
</a>
"""
            metrics_html += "</div>"
            metrics_html = "\n".join([line.strip() for line in metrics_html.split('\n')])
            st.markdown(metrics_html, unsafe_allow_html=True)
                
            st.divider()
            
            st.markdown("### 📋  Lista de Veículos")
            
            # 5. Interface Visual (Com Barra de Pesquisa)
            col_search, _, col_view_csv = st.columns([2, 5, 1])
            with col_search:
                search_placa = st.text_input("🔍 Buscar por Placa:", placeholder="Digite a placa...")
            
            status_filter = st.query_params.get("status", "Todos")
            
            df_view = df_frota.copy()
            if search_placa:
                df_view = df_view[df_view[col_placa].astype(str).str.contains(search_placa.strip(), case=False, na=False)]
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
                
            html_cards = "<div style='display:flex; flex-direction:column; gap:10px; margin-top:10px;'>"
            for _, row in df_view.iterrows():
                placa = row[col_placa]
                status = row['Status Atual']
                cor = cores_status.get(status, "#000000")
                bg = bg_luz.get(status, "#ffffff")
                
                # Resgatar DT limpando possível zero decimal
                dt_number = row[col_dt_a]
                try:
                    dt_txt = str(int(float(dt_number)))
                except:
                    dt_txt = str(dt_number).strip() if pd.notna(dt_number) else "Sem DT"
                
                # Resgatar Rota Origem x Destino
                origem_rot = str(row[col_origem_j]).strip().upper() if pd.notna(row[col_origem_j]) else "?"
                destino_rot = str(row[col_destino_k]).strip().upper() if pd.notna(row[col_destino_k]) else "?"
                rota_txt = f"{origem_rot} x {destino_rot}"
                
                # Tratar valores vazios para n dar erro no HTML
                dt_ch_coleta = str(row[col_chegada_coleta]) if pd.notna(row[col_chegada_coleta]) else "---"
                dt_sai_coleta = str(row[col_saida_coleta]) if pd.notna(row[col_saida_coleta]) else "---"
                dt_ch_cliente = str(row[col_chegada_cliente]) if pd.notna(row[col_chegada_cliente]) else "---"
                dt_sai_descarga = str(row[col_saida_descarga]) if pd.notna(row[col_saida_descarga]) else "---"
                agend_txt = str(row[col_agenda_descarga]) if pd.notna(row[col_agenda_descarga]) else "Sem agenda"
                
                # Evitar erro se o Ultimo Evento for nulo devido ao preenchimento de proteção
                data_event = row['Ultimo_Evento_Dt'] if 'Ultimo_Evento_Dt' in row and pd.notna(row['Ultimo_Evento_Dt']) else row['Referencia_Filtro']
                txt_ref = data_event.strftime("%d/%m/%Y") if pd.notna(data_event) else "?"

                # --- LÓGICA DE ALERTA (SLA) ---
                alertas = []
                dt_ch_client_dt = row[f"{col_chegada_cliente}_dt"]
                dt_agendamento_dt = row[f"{col_agenda_descarga}_dt"]
                hoje_agora = pd.Timestamp.now()
                
                # SLA 1: > 2h Aguardando Descarga = Excesso
                if status == "Aguardando descarga/Descarregando" and pd.notna(dt_ch_client_dt):
                    horas_espera = (hoje_agora - dt_ch_client_dt).total_seconds() / 3600
                    if horas_espera > 2:
                        alertas.append("<span style='background-color:#ffebee; color:#f44336; border: 1px solid #f44336; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;'>⚠️ EXCESSO: >2h NA DESCARGA</span>")
                
                # SLA 2: Atraso de Agenda
                if pd.notna(dt_agendamento_dt):
                    if pd.notna(dt_ch_client_dt):
                        # Chegou após a agenda
                        if (dt_ch_client_dt - dt_agendamento_dt).total_seconds() > 0:
                            alertas.append("<span style='background-color:#fff3e0; color:#ff9800; border: 1px solid #ff9800; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;'>⏳ CHEGOU ATRASADO</span>")
                    elif status != "Vazio" and status != "Aguardando descarga/Descarregando":
                        # Não chegou e a hora atual já passou da agenda
                        if (hoje_agora - dt_agendamento_dt).total_seconds() > 0:
                            alertas.append("<span style='background-color:#fff3e0; color:#ff9800; border: 1px solid #ff9800; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;'>⏰ ATRASADO P/ AGENDA</span>")
                            
                alertas_html = " &nbsp; ".join(alertas) if alertas else ""

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
        <h3 style="margin: 0; padding: 0; color: #333; font-size: 18px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            {placa} <span style="color: #999; font-weight: normal; font-size: 15px;">- DT {dt_txt} - {rota_txt}</span> {alertas_html}
        </h3>
        <div style="display: flex; gap: 15px; margin-top: 5px; color: #666; font-size: 12px;">
            <span><b>Coleta:</b> {dt_ch_coleta}</span>
            <span><b>Viagem:</b> {dt_sai_coleta}</span>
            <span><b>Agenda:</b> {agend_txt}</span>
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
                html_cards = "\n".join([line.strip() for line in html_cards.split('\n')])
                st.markdown(html_cards, unsafe_allow_html=True)
            else:
                st.info("Nenhum veículo corresponde a este filtro.")
        else:
            st.info("Nenhum veículo encontrado no período analisado.")
    else:
        st.error("A planilha não possui as colunas necessárias detectadas (esperado pelo menos até a coluna Z).")
else:
    st.info("Aguardando carregamento dos dados...")

import pandas as pd
import sys

SHEET_ID = "1f3DubkiqNVYsOd_arblxpYAEVwv4qRIhsI9cdMR99EU"
GID = "316476550"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

df_raw = pd.read_csv(CSV_URL, skiprows=range(1, 1156))

col_data_c = df_raw.columns[2]
col_placa = df_raw.columns[12]
col_chegada_coleta = df_raw.columns[20]
col_saida_coleta = df_raw.columns[21]
col_agenda_descarga = df_raw.columns[23]
col_chegada_cliente = df_raw.columns[24]
col_saida_descarga = df_raw.columns[25]

colunas = [col_data_c, col_placa, col_chegada_coleta, col_saida_coleta, col_agenda_descarga, col_chegada_cliente, col_saida_descarga]
df = df_raw[colunas].copy()
df['linha_original'] = df.index + 1157

df = df[df[col_placa].notna() & (df[col_placa].astype(str).str.strip() != "")]

def parse_dates(series):
    return pd.to_datetime(series, errors='coerce', dayfirst=True)

for col in [col_chegada_coleta, col_saida_coleta, col_chegada_cliente, col_saida_descarga]:
    df[f"{col}_dt"] = parse_dates(df[col])

df['Ultimo_Evento_Dt'] = df[[
    f"{col_chegada_coleta}_dt", f"{col_saida_coleta}_dt", 
    f"{col_chegada_cliente}_dt", f"{col_saida_descarga}_dt"
]].max(axis=1)

hoje = pd.Timestamp('2026-03-26')  # Mocado pra consistencia
limite_2_meses = hoje - pd.DateOffset(months=2)

df[f"{col_data_c}_dt"] = parse_dates(df[col_data_c])
df['Referencia_Filtro'] = df['Ultimo_Evento_Dt'].fillna(df[f"{col_data_c}_dt"])
df_filtrado = df[df['Referencia_Filtro'] >= limite_2_meses].copy()

# Apenas para ver o EWJ0E55 antes da desduplicação
print("Antes da desduplicação:")
print(df_filtrado[df_filtrado[col_placa].astype(str).str.contains("EWJ0E55")][['linha_original', 'Ultimo_Evento_Dt', 'Referencia_Filtro']].to_string())

df_filtrado = df_filtrado.sort_values(by='Ultimo_Evento_Dt', ascending=False)
df_frota = df_filtrado.drop_duplicates(subset=[col_placa], keep='first').copy()

ewj = df_frota[df_frota[col_placa].astype(str).str.contains("EWJ0E55")]

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

ewj['Status'] = ewj.apply(definir_status, axis=1)
print("\nDepois da desduplicação:")
print(ewj[['linha_original', 'Ultimo_Evento_Dt', 'Status']].to_string())

import pandas as pd
import sys

# URL de exportação direta
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

df = df_raw[[col_data_c, col_placa, col_chegada_coleta, col_saida_coleta, col_chegada_cliente, col_saida_descarga]].copy()
df = df[df[col_placa].astype(str).str.contains("EWJ9I55", case=False, na=False)]
df['linha_original'] = df.index + 1156 + 1 # offset de linhas puladas (header + 1155 curtas)

def parse_dates(series):
    return pd.to_datetime(series, errors='coerce', dayfirst=True)

for col in [col_chegada_coleta, col_saida_coleta, col_chegada_cliente, col_saida_descarga, col_data_c]:
    df[f"{col}_dt"] = parse_dates(df[col])

df['Ultimo_Evento_Dt'] = df[[
    f"{col_chegada_coleta}_dt", f"{col_saida_coleta}_dt", 
    f"{col_chegada_cliente}_dt", f"{col_saida_descarga}_dt"
]].max(axis=1)

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
print(df)

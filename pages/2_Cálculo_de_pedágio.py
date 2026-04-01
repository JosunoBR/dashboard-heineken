import streamlit as st
import PyPDF2
from io import BytesIO
import re
import pandas as pd
import hashlib
import unicodedata
from datetime import datetime

st.set_page_config(page_title="Cálculo de Pedágio", layout="wide")

st.title("Calculadora de Pedágio")

st.write("Faça o upload do arquivo PDF do pedágio para análise.")

# --- Inicialização do Histórico ---
if 'toll_history' not in st.session_state:
    st.session_state.toll_history = []

if 'processed_pdf_hashes' not in st.session_state:
    st.session_state.processed_pdf_hashes = set()

if st.session_state.toll_history and "Valor Numérico" not in st.session_state.toll_history[0]:
    st.session_state.toll_history = []
    st.session_state.processed_pdf_hashes = set()

# --- Funções de Extração de Dados ---

@st.cache_data
def extract_text_from_pdf(file_bytes):
    """Extrai todo o texto de um arquivo PDF em memória."""
    try:
        bytes_io = BytesIO(file_bytes)
        reader = PyPDF2.PdfReader(bytes_io)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        st.error(f"Erro ao ler o PDF: {e}")
        return None

def normalize_pdf_text(text):
    """Compacta o texto extraído para facilitar a leitura por regex."""
    text = text.replace("\u00a0", " ").replace("\ufb01", "fi")
    text = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def strip_accents(text):
    """Remove acentos para tornar os padrões mais estáveis."""
    return "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )

def normalize_currency(value):
    """Padroniza o valor monetário no formato 'R$ 00,00' ou '-R$ 00,00'."""
    value = value.replace("\u00a0", " ").strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^\s*[-\u2013\u2014]\s*R\$\s*", "-R$ ", value)
    value = re.sub(r"^\s*R\$\s*", "R$ ", value)
    return value.strip()

def currency_to_float(value):
    """Converte 'R$ 00,00' ou '-R$ 00,00' para float."""
    normalized_value = normalize_currency(value)
    is_negative = normalized_value.startswith("-")
    numeric_text = normalized_value.replace("-R$ ", "").replace("R$ ", "").replace(".", "").replace(",", ".")

    try:
        amount = float(numeric_text)
    except ValueError:
        return 0.0

    return -amount if is_negative else amount

def format_currency(value):
    """Formata float no padrão monetário brasileiro preservando o sinal."""
    prefix = "-R$" if value < 0 else "R$"
    formatted_amount = f"{abs(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{prefix} {formatted_amount}"

def apply_transaction_sign(transaction_type, amount):
    """Aplica a regra de sinal conforme o tipo da transação."""
    if "estorno" in transaction_type.lower():
        return abs(amount)
    return -abs(amount)

def parse_filter_datetime(datetime_text, end_of_minute=False):
    """Converte o texto digitado no filtro para datetime com precisão de minuto."""
    if not datetime_text:
        return None

    try:
        parsed_datetime = datetime.strptime(datetime_text.strip(), "%d/%m/%Y %H:%M")
        if end_of_minute:
            parsed_datetime = parsed_datetime.replace(second=59)
        return parsed_datetime
    except ValueError:
        return None

def extract_toll_info(text):
    """
    Extrai a placa do veículo e uma lista de transações (data e valor).
    Cada registro de pedágio contém duas datas/horas: a da movimentação e a da
    transação. O sistema deve usar a segunda data/hora e o primeiro valor da linha.
    Retorna a placa e uma lista de dicionários de transação.
    """
    placa = "Não encontrada"
    extracted_data = []

    if not text:
        return placa, extracted_data

    normalized_text = normalize_pdf_text(text)
    searchable_text = strip_accents(normalized_text)

    # 1. Extrair a Placa do Veículo
    placa_regex = r"[A-Z]{3}-?\d{4}|[A-Z]{3}\d[A-Z]\d{2}"
    placa_match = re.search(placa_regex, searchable_text)
    if placa_match:
        placa = placa_match.group(0)

    # 2. Extrair as transações usando o tipo da linha para definir o sinal
    transacoes_regex = re.compile(
        r"(?:\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2})\s*"
        r"(Estorno\s+)?Pedagio\s*"
        r"(\d{2}/\d{2}/\d{4})\s*"
        r"(\d{2}:\d{2}:\d{2})"
        r".*?"
        r"(R\$\s*[\d\.]+,\d{2})",
        flags=re.IGNORECASE
    )

    for match in transacoes_regex.finditer(searchable_text):
        transaction_type = "Estorno Pedágio" if match.group(1) else "Pedágio"
        data = f"{match.group(2)} {match.group(3)}"
        raw_amount = currency_to_float(match.group(4))
        signed_amount = apply_transaction_sign(transaction_type, raw_amount)
        extracted_data.append({
            "Data da Transação": data,
            "Valor da Transação": format_currency(signed_amount),
            "Valor Numérico": signed_amount,
            "Tipo de Transação": transaction_type
        })
            
    return placa, extracted_data


# --- Lógica da Página ---

filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    start_date_text = st.text_input(
        "Data e hora inicial",
        placeholder="DD/MM/AAAA HH:MM",
        key="toll_filter_start"
    )

with filter_col2:
    end_date_text = st.text_input(
        "Data e hora final",
        placeholder="DD/MM/AAAA HH:MM",
        key="toll_filter_end"
    )

uploaded_file = st.file_uploader("Escolha um arquivo PDF", type="pdf", key="pdf_uploader")

if uploaded_file is not None:
    uploaded_file_bytes = uploaded_file.getvalue()
    pdf_text = extract_text_from_pdf(uploaded_file_bytes)
    file_hash = hashlib.sha1(uploaded_file_bytes).hexdigest()
    
    if pdf_text:
        st.success("Arquivo PDF carregado e texto extraído com sucesso!")

        placa, extracted_transactions = extract_toll_info(pdf_text)
        
        # Adiciona as novas transações ao histórico apenas uma vez por arquivo
        if extracted_transactions and file_hash not in st.session_state.processed_pdf_hashes:
            for trans in extracted_transactions:
                st.session_state.toll_history.append(trans)
            st.session_state.processed_pdf_hashes.add(file_hash)
        
        st.subheader(f"Placa do Veículo: {placa}")
        if extracted_transactions:
            st.caption(f"{len(extracted_transactions)} transação(ões) encontrada(s) no arquivo.")
        
        if not extracted_transactions:
            st.warning("Nenhuma transação encontrada no formato esperado da linha do relatório.")

    else:
        st.error("Não foi possível extrair texto do arquivo PDF.")

# --- Exibição do Histórico ---
st.divider()
st.subheader("Lista de Transações")

if st.session_state.toll_history:
    # Garante que as colunas Placa não existam, limpando o histórico se necessário
    if any("Placa" in col for col in st.session_state.toll_history[0]):
        # Limpa o histórico se o formato for antigo
        st.session_state.toll_history = [
            {k: v for k, v in item.items() if k != "Placa"}
            for item in st.session_state.toll_history
        ]

    df_history = pd.DataFrame(st.session_state.toll_history)
    if "Valor Numérico" not in df_history.columns:
        df_history["Valor Numérico"] = df_history["Valor da Transação"].apply(currency_to_float)

    df_history["Data da Transação Dt"] = pd.to_datetime(
        df_history["Data da Transação"],
        format="%d/%m/%Y %H:%M:%S",
        errors="coerce"
    )

    start_datetime = parse_filter_datetime(start_date_text)
    end_datetime = parse_filter_datetime(end_date_text, end_of_minute=True)
    invalid_start = bool(start_date_text.strip()) and start_datetime is None
    invalid_end = bool(end_date_text.strip()) and end_datetime is None

    if invalid_start or invalid_end:
        st.warning("Informe os filtros no formato DD/MM/AAAA HH:MM.")
    elif start_datetime and end_datetime and start_datetime > end_datetime:
        st.warning("A data e hora inicial deve ser menor ou igual à data e hora final.")
    else:
        if start_datetime:
            df_history = df_history[df_history["Data da Transação Dt"] >= start_datetime]
        if end_datetime:
            df_history = df_history[df_history["Data da Transação Dt"] <= end_datetime]

    df_display = df_history.drop(columns=["Data da Transação Dt", "Valor Numérico", "Tipo de Transação"], errors="ignore")
    st.dataframe(df_display, width='stretch')

    # --- Cálculo do Valor Total ---
    total_soma = df_history["Valor Numérico"].sum()
    total_formatado = format_currency(total_soma)
    st.markdown(f"### 💰 Valor Total: **{total_formatado}**")

    # Botão para limpar o histórico
    if st.button("🗑️ Limpar Histórico"):
        st.session_state.toll_history = []
        st.session_state.processed_pdf_hashes = set()
        st.rerun()
else:
    st.info("Nenhuma transação foi processada ainda.")

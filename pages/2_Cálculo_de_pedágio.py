import streamlit as st
import PyPDF2
from io import BytesIO
import re
import pandas as pd
import hashlib
import unicodedata

st.set_page_config(page_title="Cálculo de Pedágio", layout="wide")

st.title("Calculadora de Pedágio")

st.write("Faça o upload do arquivo PDF do pedágio para análise.")

# --- Inicialização do Histórico ---
if 'toll_history' not in st.session_state:
    st.session_state.toll_history = []

if 'processed_pdf_hashes' not in st.session_state:
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
    """Padroniza o valor monetário no formato 'R$ 00,00'."""
    value = value.replace("\u00a0", " ").strip()
    value = re.sub(r"\s+", " ", value)
    value = value.replace("-R$", "R$").replace("- R$", "R$")
    return value.strip()

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

    # 2. Extrair as transações usando a data/hora após "Pedagio"
    transacoes_regex = re.compile(
        r"(?:\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2})\s*"
        r"Pedagio\s*"
        r"(\d{2}/\d{2}/\d{4})\s*"
        r"(\d{2}:\d{2}:\d{2})"
        r".*?"
        r"(R\$\s*[\d\.]+,\d{2})",
        flags=re.IGNORECASE
    )

    for match in transacoes_regex.finditer(searchable_text):
        data = f"{match.group(1)} {match.group(2)}"
        valor = normalize_currency(match.group(3))
        extracted_data.append({
            "Data da Transação": data,
            "Valor da Transação": valor
        })
            
    return placa, extracted_data


# --- Lógica da Página ---

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
    st.dataframe(df_history, width='stretch')

    # --- Cálculo do Valor Total ---
    total_soma = 0.0
    for valor_str in df_history["Valor da Transação"]:
        # Limpa a string "R$ 72,96" para converter em float 72.96
        num_str = valor_str.replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            total_soma += float(num_str)
        except ValueError:
            pass
    
    total_formatado = f"R$ {total_soma:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    st.markdown(f"### 💰 Valor Total: **{total_formatado}**")

    # Botão para limpar o histórico
    if st.button("🗑️ Limpar Histórico"):
        st.session_state.toll_history = []
        st.session_state.processed_pdf_hashes = set()
        st.rerun()
else:
    st.info("Nenhuma transação foi processada ainda.")

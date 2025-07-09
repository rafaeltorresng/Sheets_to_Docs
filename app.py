import streamlit as st
import pandas as pd
from sheets import Google
from googleapiclient.discovery import Resource


# Retorna DataFrame de uma planilha usando cache para evitar chamadas repetidas
@st.cache_data(ttl=300, hash_funcs={Resource: lambda _obj: None})
def _read_sheet_cached(sheets_service: Resource, sheet_id: str):
    return Google.read_sheet_to_df(sheets_service, sheet_id)

# Configuração da página
st.set_page_config(
    page_title="Automação de Briefings Universais",
    page_icon="🤖",
    layout="wide"
)

# Lê dados a partir de uma URL do Google Sheets e exibe mensagens de status
def load_data_from_sheets(sheets_service, sheet_url):
    sheet_id = Google.extract_sheet_id(sheet_url)
    if not sheet_id:
        st.error("❌ URL do Google Sheets inválida.")
        return None
    
    with st.spinner("🔄 Lendo dados do Google Sheets..."):
        try:
            df = _read_sheet_cached(sheets_service, sheet_id)
            if df.empty:
                st.error("❌ A planilha está vazia ou não foi possível ler os dados.")
                return None
            st.success(f"✅ Dados carregados: {len(df)} linhas, {len(df.columns)} colunas")
            return df
        except Exception as e:
            st.error(f"❌ Erro ao ler a planilha: {str(e)}")
            return None

# Lê dados de um arquivo CSV enviado via upload
def load_data_from_csv(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file)
        if df.empty:
            st.error("❌ O arquivo CSV está vazio.")
            return None
        st.success(f"✅ Arquivo carregado: {len(df)} linhas, {len(df.columns)} colunas")
        return df
    except Exception as e:
        st.error(f"❌ Erro ao ler o arquivo CSV: {str(e)}")
        return None

# Mostra pré-visualização do DataFrame em um expander
def display_data_preview(df):
    with st.expander("👀 Visualizar dados carregados", expanded=True):
        st.dataframe(df, use_container_width=True)
        st.info(f"**Estrutura detectada:** {len(df)} linhas × {len(df.columns)} colunas")
        st.info(f"**Coluna identificadora:** '{df.columns[0]}' (será usada como título dos documentos)")

# Permite ao usuário selecionar linhas do DataFrame (todos ou múltiplas específicas)
def get_selected_items(df):
    item_names = df.iloc[:, 0].astype(str).tolist()
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        select_all = st.checkbox("📋 Selecionar todos os itens")
    
    with col2:
        if select_all:
            selected_items = item_names
            st.info(f"✅ Todos os {len(item_names)} itens selecionados")
        else:
            selected_items = st.multiselect(
                "Escolha os itens específicos:",
                options=item_names,
                help="Selecione uma ou mais linhas para gerar os briefings"
            )
    
    return selected_items

# Pergunta ao usuário se deseja documentos individuais ou consolidados
def get_generation_mode():
    return st.radio(
        "Como deseja gerar os documentos?",
        [
            "📄 Um documento para cada item selecionado",
            "📋 Todos os itens em um único documento"
        ],
        help="Escolha entre documentos individuais ou um documento consolidado"
    )

# Gera um Google Doc separado para cada item selecionado
def generate_individual_documents(docs_service, df, selected_items):
    urls = []
    progress_bar = st.progress(0)
    
    for i, item_name in enumerate(selected_items):
        item_data = df[df.iloc[:, 0].astype(str) == item_name].iloc[0]
        doc_url = Google.create_single_document(docs_service, item_data)
        urls.append((item_name, doc_url))
        progress_bar.progress((i + 1) / len(selected_items))
    
    progress_bar.empty()
    st.balloons()
    st.success(f"🎉 {len(urls)} documentos gerados com sucesso!")
    
    st.subheader("📎 Links dos Documentos Gerados:")
    for name, url in urls:
        st.markdown(f"**{name}:** [🔗 Abrir documento]({url})")

# Gera um único Google Doc contendo todos os itens selecionados
def generate_multiple_documents(docs_service, df, selected_items):
    selected_data = []
    for item_name in selected_items:
        item_data = df[df.iloc[:, 0].astype(str) == item_name].iloc[0]
        selected_data.append(item_data)
    
    doc_url = Google.create_multiple_documents(docs_service, selected_data)
    
    st.balloons()
    st.success("🎉 Documento consolidado gerado com sucesso!")
    st.markdown(f"**📋 [🔗 Abrir documento com todos os briefings]({doc_url})**")

# Função principal que compõe a interface Streamlit e orquestra o fluxo
def main():
    st.title("🤖 Automação Universal de Geração de Briefings")
    st.markdown("**✨ Converte QUALQUER planilha em documentos organizados do Google Docs**")
    st.markdown("---")

    credentials = Google.authenticate_google()
    st.success("✅ Autenticado com sucesso no Google!")
    st.markdown("---")
    
    if "sheets_service" not in st.session_state:
        st.session_state["sheets_service"] = Google.get_sheets_service(credentials)
    sheets_service = st.session_state["sheets_service"]

    # Reutiliza docs_service sem armazenar o drive_service (não utilizado)
    if "docs_service" not in st.session_state:
        _, docs_service = Google.get_google_services(credentials)
        st.session_state["docs_service"] = docs_service
    else:
        docs_service = st.session_state["docs_service"]

    st.header("📋 1. Forneça seus Dados")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔗 Google Sheets")
        sheet_url = st.text_input(
            "Cole o link do Google Sheets:",
            placeholder="https://docs.google.com/spreadsheets/d/..."
        )

    with col2:
        st.subheader("📁 Upload CSV")
        uploaded_file = st.file_uploader(
            "Ou faça upload de um arquivo CSV:",
            type="csv",
            help="Arquivo CSV com qualquer estrutura de colunas"
        )

    df_projects = None
    if sheet_url:
        df_projects = load_data_from_sheets(sheets_service, sheet_url)
    elif uploaded_file is not None:
        df_projects = load_data_from_csv(uploaded_file)

    if df_projects is not None and not df_projects.empty:
        st.markdown("---")
        display_data_preview(df_projects)

        st.header("🎯 2. Selecione os Itens para Processar")
        selected_items = get_selected_items(df_projects)

        st.subheader("📄 Modo de Geração")
        generation_mode = get_generation_mode()

        st.header("🚀 3. Gerar Documentos")
        
        if len(selected_items) > 0:
            st.info(f"**{len(selected_items)} item(s) selecionado(s)** | **Modo:** {generation_mode.split(' ', 1)[1]}")
            
            if st.button("🎯 Gerar Briefings", type="primary", use_container_width=True):
                with st.spinner("🔄 Gerando documentos... Isso pode levar alguns instantes."):
                    try:
                        if "Um documento para cada" in generation_mode:
                            generate_individual_documents(docs_service, df_projects, selected_items)
                        else:
                            generate_multiple_documents(docs_service, df_projects, selected_items)
                    except Exception as e:
                        st.error(f"❌ Erro durante a geração: {str(e)}")
                        st.error("Verifique suas permissões do Google ou tente novamente.")
        else:
            st.warning("⚠️ Selecione pelo menos um item para gerar os briefings.")
    else:
        st.info("👆 Para começar, forneça uma planilha do Google Sheets ou faça upload de um arquivo CSV.")

    st.markdown("---")
    st.markdown("**🤖 Automação Universal de Briefings** | Funciona com qualquer estrutura de dados")

if __name__ == "__main__":
    main()
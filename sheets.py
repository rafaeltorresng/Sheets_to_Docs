import streamlit as st
import pandas as pd
import time
import re
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow

# Classe utilitária com métodos para autenticação, leitura do Sheets e geração de Docs
class Google:
    CLIENT_SECRETS_FILE = "credentials.json"
    SCOPES = [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/spreadsheets.readonly"
    ]

    # Cria o objeto Flow de OAuth2 com escopos e redirect definidos
    @classmethod
    def get_google_auth_flow(cls):
        return Flow.from_client_secrets_file(
            cls.CLIENT_SECRETS_FILE,
            scopes=cls.SCOPES,
            redirect_uri='http://localhost:8501'
        )

    # Realiza o fluxo completo de autenticação no Google e devolve as credenciais
    @classmethod
    def authenticate_google(cls):
        code = st.query_params.get('code')
        if code:
            st.query_params.clear()

        if 'credentials' in st.session_state:
            return st.session_state['credentials']

        if code:
            flow = cls.get_google_auth_flow()
            flow.fetch_token(code=code)
            st.session_state['credentials'] = flow.credentials
            return flow.credentials
        
        flow = cls.get_google_auth_flow()
        auth_url, _ = flow.authorization_url(prompt='consent')
        st.write("### 🔑 Autenticação Necessária")
        st.info("Para gerar os briefings, você precisa autorizar o acesso à sua conta Google.")
        st.link_button("Fazer Login com o Google", auth_url)
        st.stop()

    # Obtém instâncias dos serviços Drive e Docs usando as credenciais fornecidas
    @staticmethod
    def get_google_services(credentials):
        drive_service = build("drive", "v3", credentials=credentials)
        docs_service = build("docs", "v1", credentials=credentials)
        return drive_service, docs_service
    
    # Cria o serviço Google Sheets
    @staticmethod
    def get_sheets_service(credentials):
        return build("sheets", "v4", credentials=credentials)

    # Extrai o ID de uma URL de planilha do Google Sheets
    @staticmethod
    def extract_sheet_id(sheet_url):
        match = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url)
        return match.group(1) if match else None

    # Lê dados de uma aba do Google Sheets para DataFrame usando range dinâmico opcional
    @staticmethod
    def read_sheet_to_df(sheets_service, sheet_id, range_name: str | None = None, sheet_index: int = 0):
        # 1. Determina o intervalo se não foi passado.
        if range_name is None:
            meta = sheets_service.spreadsheets().get(
                spreadsheetId=sheet_id,
                fields="sheets.properties.gridProperties",
            ).execute()

            grid = meta["sheets"][sheet_index]["properties"]["gridProperties"]
            rows = grid.get("rowCount", 1000)
            cols = grid.get("columnCount", 26)

            last_cell = f"{Google._column_to_letter(cols)}{rows}"
            range_name = f"A1:{last_cell}"

        # 2. Busca os valores propriamente ditos.
        sheet = sheets_service.spreadsheets().values()
        result = sheet.get(
            spreadsheetId=sheet_id,
            range=range_name,
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()

        values = result.get("values", [])

        if not values or len(values) < 2:
            return pd.DataFrame()

        return pd.DataFrame(values[1:], columns=values[0])

    # Normaliza valores vazios ou NaN para string padrão
    @staticmethod
    def clean_value(value):
        if pd.isna(value) or value is None or str(value).strip() == '' or str(value).lower() == 'nan':
            return "(não informado)"
        return str(value).strip()

    # Envia lote de operações de edição ao Google Docs com atraso opcional
    @staticmethod
    def _send_batch_requests(docs_service, doc_id, requests_batch, delay=0.8):
        if requests_batch:
            docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests_batch}).execute()
            time.sleep(delay)

    # Constrói lista de requests de texto/estilo para batchUpdate do Docs
    @staticmethod
    def _build_text_requests(content_blocks, start_index=1):
        requests = []
        current_index = start_index
        
        for block in content_blocks:
            text = block['text']
            requests.append({'insertText': {'location': {'index': current_index}, 'text': text}})
            
            if 'style' in block:
                requests.append({'updateParagraphStyle': {
                    'range': {'startIndex': current_index, 'endIndex': current_index + len(text) - 1},
                    'paragraphStyle': {'namedStyleType': block['style']},
                    'fields': 'namedStyleType'
                }})
            
            current_index += len(text)
        
        return requests

    # Cria um documento para um único projeto e retorna a URL
    @staticmethod
    def create_single_document(docs_service, project_data):
        titulo_projeto = Google.clean_value(project_data.iloc[0])
        if titulo_projeto == "(não informado)":
            titulo_projeto = "Documento"
            
        titulo_documento = f"Briefing - {titulo_projeto}"
        doc = docs_service.documents().create(body={"title": titulo_documento}).execute()
        doc_id = doc['documentId']

        content_blocks = [
            {'text': f"{titulo_projeto}\n", 'style': 'TITLE'},
            {'text': f"Gerado em: {pd.to_datetime('today').strftime('%d/%m/%Y')}\n\n"}
        ]

        for nome_coluna, valor in zip(project_data.index[1:], project_data.values[1:]):
            valor_limpo = Google.clean_value(valor)
            content_blocks.extend([
                {'text': f"{nome_coluna}\n", 'style': 'HEADING_2'},
                {'text': f"{valor_limpo}\n\n"}
            ])

        all_requests = Google._build_text_requests(content_blocks)
        
        batch_size = 20
        for i in range(0, len(all_requests), batch_size):
            batch = all_requests[i:i + batch_size]
            Google._send_batch_requests(docs_service, doc_id, batch, 0.8)

        return f"https://docs.google.com/document/d/{doc_id}/edit"

    # Gera um documento consolidado contendo vários projetos selecionados
    @staticmethod
    def create_multiple_documents(docs_service, projetos_data):
        titulo_documento = "Briefings - Vários Projetos"
        doc = docs_service.documents().create(body={"title": titulo_documento}).execute()
        doc_id = doc['documentId']

        content_blocks = [
            {'text': "Briefings Gerados\n", 'style': 'TITLE'},
            {'text': f"Gerado em: {pd.to_datetime('today').strftime('%d/%m/%Y')}\nTotal de projetos: {len(projetos_data)}\n\n"}
        ]

        for i, project_data in enumerate(projetos_data):
            titulo_projeto = Google.clean_value(project_data.iloc[0])
            if titulo_projeto == "(não informado)":
                titulo_projeto = f"Projeto {i+1}"
                
            content_blocks.append({'text': f"{titulo_projeto}\n", 'style': 'HEADING_1'})

            for nome_coluna, valor in zip(project_data.index[1:], project_data.values[1:]):
                valor_limpo = Google.clean_value(valor)
                content_blocks.extend([
                    {'text': f"{nome_coluna}\n", 'style': 'HEADING_2'},
                    {'text': f"{valor_limpo}\n\n"}
                ])

            if i < len(projetos_data) - 1:
                content_blocks.append({'text': "\n" + "="*50 + "\n\n"})

        all_requests = Google._build_text_requests(content_blocks)
        
        batch_size = 15
        for i in range(0, len(all_requests), batch_size):
            batch = all_requests[i:i + batch_size]
            Google._send_batch_requests(docs_service, doc_id, batch, 1.2)

        return f"https://docs.google.com/document/d/{doc_id}/edit"

    # Converte índice numérico (1-based) em letra de coluna (A1 notation)
    @staticmethod
    def _column_to_letter(n: int) -> str:
        letters = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            letters = chr(65 + rem) + letters
        return letters
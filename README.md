# Sheets_to_Docs

Programa que automatiza a criação de documentos de briefing no Google Docs a partir de dados de planilhas do Google Sheets ou ficheiros CSV.

### 🚀 Como Executar Localmente


**1. Clone o Repositório**
```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd <NOME_DA_PASTA_DO_PROJETO>
```

**2. Configure as Credenciais do Google (Passo Crucial)**
   * Siga as instruções do Google para [criar um ID do cliente OAuth 2.0](https://developers.google.com/workspace/guides/create-credentials#oauth-client-id).
   * Durante a configuração, selecione **"Aplicação Web"**.
   * Em **"URIs de redirecionamento autorizados"**, adicione `http://localhost:8501`.
   * Faça o download do ficheiro JSON com as credenciais, renomeie-o para `credentials.json` e coloque-o na raiz do projeto. Este ficheiro está no `.gitignore` e não deve ser partilhado.

**3. Crie um Ambiente Virtual (Recomendado)**
```bash
python -m venv venv
source venv/bin/activate  # No macOS/Linux
# venv\Scripts\activate   # No Windows
```

**4. Instale as Dependências**
```bash
pip install -r requirements.txt
```

**5. Execute a Aplicação**
```bash
streamlit run app.py
```
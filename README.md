# Controle de Ligações – Eleição 2025

Sistema simples para registrar ligações recebidas e gerar relatórios com gráficos, pronto para deploy no Railway a partir do GitHub.

## Recursos
- Formulário com campos: **CRO**, **Nome do Inscrito**, **Dúvida** (com opções fixas).
- Botão **Cadastrar ligação** que grava automaticamente **data e horário**.
- Relatórios com **gráficos** (por tipo de dúvida e por dia).
- **Imprimir/Salvar em PDF** com o botão do navegador (página de relatório é amigável à impressão).
- Banco local (SQLite) para desenvolvimento e **PostgreSQL** no Railway (via `DATABASE_URL`).

## Como rodar localmente
1. Instale o Python 3.11+.
2. Crie e ative um ambiente virtual (opcional):  
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
4. (Opcional) Crie um arquivo `.env` na raiz com a variável `DATABASE_URL`. 
   - Para SQLite local (padrão), você pode **pular** este passo.
   - Exemplos:
     ```env
     # SQLite (dev)
     DATABASE_URL=sqlite:///./data.db
     # PostgreSQL (produção - Railway)
     # DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DBNAME
     ```
5. Rode a aplicação:
   ```bash
   uvicorn app:app --reload --port 8080
   ```
6. Acesse: <http://localhost:8080>

## Como criar o repositório no GitHub
1. No GitHub, clique em **New repository** e crie um repo, por ex.: `ligacoes-2025` (público ou privado).
2. No seu computador:
   ```bash
   git init
   git add .
   git commit -m "Projeto: Controle de Ligações - Eleição 2025"
   git branch -M main
   git remote add origin https://github.com/<SEU_USUARIO>/ligacoes-2025.git
   git push -u origin main
   ```
   > Se der erro de permissão, verifique se você criou o repositório e se está autenticado no Git.

## Deploy no Railway (com GitHub)
1. Crie uma conta no Railway e conecte o Railway ao seu GitHub.
2. Clique em **New Project** → **Deploy from GitHub repo** → escolha `ligacoes-2025`.
3. Após o primeiro deploy, clique no projeto e:
   - Em **Variables**, adicione (se necessário) a variável `DATABASE_URL` apontando para PostgreSQL.
   - **OU** adicione um serviço de banco Postgres do Railway: **Add → Database → PostgreSQL**. Depois copie a **Connection URL** e cole em `DATABASE_URL` do serviço web.
4. A porta é definida pela variável `PORT` fornecida pelo Railway; o app já lê isso automaticamente.
5. Abra a URL pública gerada pelo Railway.

## Dicas de uso
- A página inicial permite cadastrar novas ligações e ver as últimas registradas.
- Em **Relatórios** você vê gráficos e pode imprimir/salvar em PDF (Ctrl+P / Cmd+P e escolha “Salvar como PDF”).

---

### Licença
Uso livre dentro do contexto do CRO/RS.

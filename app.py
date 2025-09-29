import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import secrets
import io
import csv
from typing import List, Dict, Any

from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie, UploadFile, File
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, Column, Integer, String, DateTime, text, func, inspect
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from dotenv import load_dotenv
import pandas as pd
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

# Carrega .env (opcional)
load_dotenv()

# Fuso desejado (Brasil/RS)
TZ = ZoneInfo("America/Sao_Paulo")

# Banco de dados: SQLite local por padrão; PostgreSQL se DATABASE_URL estiver definido
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")

# Normaliza URL do Railway se vier como postgres:// (SQLAlchemy recomenda postgresql+psycopg2://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

# Ajuste para SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

class Ligacao(Base):
    __tablename__ = "ligacoes"
    id = Column(Integer, primary_key=True, index=True)
    cro = Column(String(50), nullable=False)
    nome_inscrito = Column(String(255), nullable=False)
    duvida = Column(String(100), nullable=False)
    observacao = Column(String(1000), nullable=True)
    atendente = Column(String(100), nullable=True)  # Nome do atendente que registrou
    created_at = Column(DateTime, nullable=False, server_default=func.now())

class ProfissionalApto(Base):
    """Modelo para armazenar dados dos profissionais aptos ao voto importados do CSV"""
    __tablename__ = "profissionais_aptos"
    id = Column(Integer, primary_key=True, index=True)
    numero_cro = Column(String(50), nullable=False, index=True)  # INSCRIÇÃO - Índice para busca rápida por CRO
    nome = Column(String(500), nullable=False, index=True)       # NOME_COMPLETO - Índice para busca rápida por nome
    categoria = Column(String(200), nullable=True)              # CATEGORIA
    cpf = Column(String(20), nullable=True)                     # CPF
    email = Column(String(200), nullable=True)                  # EMAIL
    outros_emails = Column(String(500), nullable=True)          # OUTROS_EMAILS
    celular_atualizado = Column(String(50), nullable=True)      # CELULAR_ATUALIZADO
    outros_telefones = Column(String(200), nullable=True)       # OUTROS_TELEFONES
    situacao = Column(String(200), nullable=True)               # Situação do profissional
    outras_informacoes = Column(String(2000), nullable=True)    # Campo para outras colunas não mapeadas do CSV
    imported_at = Column(DateTime, nullable=False, server_default=func.now())  # Data da importação

# Cria tabela se não existir
Base.metadata.create_all(bind=engine)

# MIGRAÇÃO LEVE: adiciona coluna 'observacao' se faltar
insp = inspect(engine)
cols = [c["name"] for c in insp.get_columns("ligacoes")]
if "observacao" not in cols:
    with engine.begin() as conn:
        if DATABASE_URL.startswith("sqlite"):
            conn.execute(text("ALTER TABLE ligacoes ADD COLUMN observacao VARCHAR(1000)"))
        else:
            conn.execute(text("ALTER TABLE ligacoes ADD COLUMN observacao VARCHAR(1000) NULL"))

# MIGRAÇÃO LEVE: adiciona coluna 'atendente' se faltar            
if "atendente" not in cols:
    with engine.begin() as conn:
        if DATABASE_URL.startswith("sqlite"):
            conn.execute(text("ALTER TABLE ligacoes ADD COLUMN atendente VARCHAR(100)"))
        else:
            conn.execute(text("ALTER TABLE ligacoes ADD COLUMN atendente VARCHAR(100) NULL"))

# MIGRAÇÃO LEVE: adiciona novas colunas para ProfissionalApto se faltarem
prof_cols = []
try:
    prof_cols = [c["name"] for c in insp.get_columns("profissionais_aptos")]
except:
    pass  # Tabela ainda não existe

new_columns = {
    "categoria": "VARCHAR(200)",
    "cpf": "VARCHAR(20)", 
    "email": "VARCHAR(200)",
    "outros_emails": "VARCHAR(500)",
    "celular_atualizado": "VARCHAR(50)",
    "outros_telefones": "VARCHAR(200)"
}

for col_name, col_type in new_columns.items():
    if col_name not in prof_cols:
        try:
            with engine.begin() as conn:
                if DATABASE_URL.startswith("sqlite"):
                    conn.execute(text(f"ALTER TABLE profissionais_aptos ADD COLUMN {col_name} {col_type}"))
                else:
                    conn.execute(text(f"ALTER TABLE profissionais_aptos ADD COLUMN {col_name} {col_type} NULL"))
        except Exception as e:
            # Se a tabela não existir ainda, será criada pela Base.metadata.create_all
            pass

DUVIDA_OPCOES = [
    "Dúvida sanada - Profissional apto ao voto",
    "Dúvida sanada - Profissional não apto ao voto",
    "Dúvida encaminhada ao jurídico",
    "Dúvida sanada - Profissional não apto ao voto (débitos)",
    "Dúvida sanada - Profissional não apto ao voto (atualização cadastral)",
    "Dúvida sanada - Profissional não apto ao voto (-60 dias)",
    "Dúvida sanada - Profissional não apto ao voto (militar exclusivo)",
]

# Garante que as pastas existam no runtime
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app = FastAPI(title="ELEIÇÕES CRORS - 2025")

# Static / Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Helpers de fuso horário
UTC = ZoneInfo("UTC")
def to_sp(dt):
    if dt is None:
        return None
    # Se vier sem tzinfo (naive), consideramos que o DB gravou em UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(TZ)

def format_sp(dt):
    dt_sp = to_sp(dt)
    return dt_sp.strftime("%d/%m/%Y %H:%M") if dt_sp else "-"

# Autenticação
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
SESSION_COOKIE_NAME = "session_token"

# Geração automática de usuários e senhas a partir da lista de colaboradores
def generate_users():
    """Gera dicionário de usuários a partir da lista de colaboradores"""
    colaboradores = [
        ("André Nunes Flores", "13/05/1983"),
        ("Alex Barcelos", "07/11/1975"),
        ("Ana Lopes", "01/02/1985"),
        ("Andréia Carla Viezzer", "08/06/1973"),
        ("Andressa Trápaga Paiz", "11/02/1990"),
        ("Bianca Carvalho Aguilar", "19/12/1997"),
        ("Carina Reis Silveira", "02/01/1978"),
        ("Carlos Edvan Carvalho Duarte", "16/04/2001"),
        ("Clarissa da Costa Barcellos", "16/11/1987"),
        ("Cleonice Lourenço Guimarães Muller", "14/09/1961"),
        ("Cristiano Grimaldi Boff", "17/03/1983"),
        ("Daniel José Bahi Aymone", "02/05/1979"),
        ("Diego Maciel", "21/12/1991"),
        ("Edson Almeida", "21/02/1999"),
        ("Giovanna de Castro Bonamigo", "30/08/1994"),
        ("Gustavo Rodrigues Graminho", "14/06/1990"),
        ("Gustavo Santos de Barros", "03/05/2003"),
        ("Igor Ricardo de Souza Sansone", "30/10/1987"),
        ("Jefferson Rocho Barth", "15/10/1985"),
        ("João Francisco Schmidt", "11/07/1964"),
        ("João Paulo Melo de Carvalho", "24/12/1980"),
        ("Jorge Miguel Chaves", "01/02/1958"),
        ("Leandro Oscar Collares da Silva", "12/09/1978"),
        ("Leonardo Carvalho da Rosa", "31/05/1984"),
        ("Leticia Pereira Voltz", "16/02/1973"),
        ("Liliane Correa Bruno", "10/06/1984"),
        ("Luciano Dichel", "26/08/1981"),
        ("Luan Santos", "06/12/2006"),
        ("Luiza Gutheil Bayer", "19/07/1993"),
        ("Matheus Prato da Silva", "09/09/1998"),
        ("Marilda Zanella Busanello", "06/07/1963"),
        ("Rodrigo Fernandes Floriano", "29/07/1978"),
        ("Stephane Antunes", "20/08/1996"),
        ("Tânia Marli Mendes Leite", "19/08/1962"),
        ("Tanise Barbosa Ramaswami", "15/08/1991"),
        ("Tatiana de Carli da Silva", "04/05/1974"),
        ("Tatiana Nuñez Rosa", "13/08/1979"),
        ("Suzana kalil", "29/03/2005"),
        ("Willians da Silva Marks", "22/10/1983"),
    ]
    
    users = {}
    for nome, nascimento in colaboradores:
        # Gerar usuário: primeiro nome + último sobrenome (minúsculo, sem acento, sem espaço)
        partes_nome = nome.split()
        primeiro_nome = partes_nome[0]
        ultimo_sobrenome = partes_nome[-1]
        
        # Remover acentos e converter para minúsculo
        import unicodedata
        def remove_accents(s):
            return ''.join(c for c in unicodedata.normalize('NFD', s) 
                          if unicodedata.category(c) != 'Mn')
        
        usuario = remove_accents(f"{primeiro_nome}{ultimo_sobrenome}").lower()
        
        # Gerar senha: data de nascimento no formato ddmmaaaa
        dia, mes, ano = nascimento.split('/')
        senha = f"{dia}{mes}{ano}"
        
        users[usuario] = senha
    
    return users

# Dicionário de usuários válidos
VALID_USERS = generate_users()

# Mapear username para nome completo
USERNAME_TO_FULLNAME = {}
def generate_username_map():
    """Mapeia username para nome completo"""
    colaboradores = [
        ("André Nunes Flores", "13/05/1983"),
        ("Andréia Carla Viezzer", "08/06/1973"),
        ("Andressa Trápaga Paiz", "11/02/1990"),
        ("Bianca Carvalho Aguilar", "19/12/1997"),
        ("Carina Reis Silveira", "02/01/1978"),
        ("Carlos Edvan Carvalho Duarte", "16/04/2001"),
        ("Clarissa da Costa Barcellos", "16/11/1987"),
        ("Cleonice Lourenço Guimarães Muller", "14/09/1961"),
        ("Cristiano Grimaldi Boff", "17/03/1983"),
        ("Daniel José Bahi Aymone", "02/05/1979"),
        ("Giovanna de Castro Bonamigo", "30/08/1994"),
        ("Gustavo Rodrigues Graminho", "14/06/1990"),
        ("Gustavo Santos de Barros", "03/05/2003"),
        ("Igor Ricardo de Souza Sansone", "30/10/1987"),
        ("Jefferson Rocho Barth", "15/10/1985"),
        ("João Francisco Schmidt", "11/07/1964"),
        ("João Paulo Melo de Carvalho", "24/12/1980"),
        ("Jorge Miguel Chaves", "01/02/1958"),
        ("Leandro Oscar Collares da Silva", "12/09/1978"),
        ("Leonardo Carvalho da Rosa", "31/05/1984"),
        ("Leticia Pereira Voltz Alfaro", "16/02/1973"),
        ("Liliane Correa Bruno", "10/06/1984"),
        ("Luciano Dichel", "26/08/1981"),
        ("Luiza Gutheil Bayer", "19/07/1993"),
        ("Matheus Prato da Silva", "09/09/1998"),
        ("Marilda Zanella Busanello", "06/07/1963"),
        ("Rodrigo Fernandes Floriano", "29/07/1978"),
        ("Tânia Marli Mendes Leite", "19/08/1962"),
        ("Tanise Barbosa Ramaswami", "15/08/1991"),
        ("Tatiana de Carli da Silva", "04/05/1974"),
        ("Tatiana Nuñez Rosa", "13/08/1979"),
        ("Willians da Silva Marks", "22/10/1983"),
    ]
    
    username_map = {}
    for nome, nascimento in colaboradores:
        # Gerar username igual ao da função generate_users
        partes_nome = nome.split()
        primeiro_nome = partes_nome[0]
        ultimo_sobrenome = partes_nome[-1]
        
        import unicodedata
        def remove_accents(s):
            return ''.join(c for c in unicodedata.normalize('NFD', s) 
                          if unicodedata.category(c) != 'Mn')
        
        usuario = remove_accents(f"{primeiro_nome}{ultimo_sobrenome}").lower()
        username_map[usuario] = nome
    
    return username_map

USERNAME_TO_FULLNAME = generate_username_map()

def get_user_full_name(username: str) -> str:
    """Retorna o nome completo do usuário"""
    return USERNAME_TO_FULLNAME.get(username, username)

def can_edit_delete(username: str) -> bool:
    """Verifica se o usuário pode editar/excluir registros"""
    return username == "igorsansone"

def can_access_reports(username: str) -> bool:
    """Verifica se o usuário pode acessar relatórios"""
    return username == "igorsansone"

# Sessions ativas (em memória - em produção usar Redis/Database)
# Estrutura: {token: {'username': 'usuario'}}
active_sessions = {}

def create_session(username: str) -> str:
    """Cria uma nova sessão e retorna o token"""
    token = secrets.token_urlsafe(32)
    active_sessions[token] = {'username': username}
    return token

def is_valid_session(token: str) -> bool:  
    """Verifica se a sessão é válida"""
    return token in active_sessions

def invalidate_session(token: str):
    """Invalida uma sessão"""
    active_sessions.pop(token, None)

def get_current_user(session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    """Dependency para verificar autenticação"""
    if not session_token or not is_valid_session(session_token):
        return None
    return active_sessions[session_token]

def require_auth(session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    """Dependency que requer autenticação"""
    if not session_token or not is_valid_session(session_token):
        return RedirectResponse("/login", status_code=302)

# Rotas de autenticação
@app.get("/login")
def login_form(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Se já estiver logado, redireciona para home
    if session_token and is_valid_session(session_token):
        return RedirectResponse("/", status_code=302)
    
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if username in VALID_USERS and VALID_USERS[username] == password:
        # Criar sessão com o usuário logado
        token = create_session(username)
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            secure=False,  # Para desenvolvimento local
            samesite="lax"
        )
        return response
    else:
        # Credenciais inválidas
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Usuário ou senha incorretos"}
        )

@app.post("/logout")
def logout(session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    if session_token:
        invalidate_session(session_token)
    
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return response

# Página inicial: formulário e lista
@app.get("/")
def home(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        return RedirectResponse("/login", status_code=302)
    
    # Obter usuário atual
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    
    db = SessionLocal()
    try:
        ligacoes = db.query(Ligacao).order_by(Ligacao.id.desc()).limit(50).all()
    finally:
        db.close()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "duvida_opcoes": DUVIDA_OPCOES,
            "ligacoes": ligacoes,
            "format_sp": format_sp,
            "current_user": current_user,
            "current_username": current_username,
            "current_user_fullname": get_user_full_name(current_username),
            "can_edit_delete": can_edit_delete(current_username),
            "can_access_reports": can_access_reports(current_username),
        },
    )

# Cadastrar ligação
@app.post("/cadastrar")
def cadastrar(
    cro: str = Form(...),
    nome_inscrito: str = Form(...),
    duvida: str = Form(...),
    observacao: str = Form(""),
    session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        return RedirectResponse("/login", status_code=302)
    
    # Obter usuário atual
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    attendant_name = get_user_full_name(current_username)
    
    if duvida not in DUVIDA_OPCOES:
        duvida = DUVIDA_OPCOES[0]
    db = SessionLocal()
    try:
        novo = Ligacao(
            cro=cro.strip(),
            nome_inscrito=nome_inscrito.strip(),
            duvida=duvida.strip(),
            observacao=(observacao or "").strip(),
            atendente=attendant_name,
            created_at=datetime.now(timezone.utc),
        )
        db.add(novo)
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/", status_code=303)

# --- EDITAR (GET): formulário preenchido
@app.get("/editar/{ligacao_id}")
def editar_form(request: Request, ligacao_id: int, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação  
    if not session_token or not is_valid_session(session_token):
        return RedirectResponse("/login", status_code=302)
    
    # Verificar permissão para editar
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_edit_delete(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    db = SessionLocal()
    try:
        obj = db.get(Ligacao, ligacao_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
    finally:
        db.close()
    return templates.TemplateResponse(
        "editar.html",
        {
            "request": request,
            "ligacao": obj,
            "duvida_opcoes": DUVIDA_OPCOES,
            "format_sp": format_sp,
            "current_user": current_user,
            "current_username": current_username,
            "current_user_fullname": get_user_full_name(current_username),
            "can_access_reports": can_access_reports(current_username),
        },
    )

# --- EDITAR (POST): salvar alterações
@app.post("/editar/{ligacao_id}")
def editar_submit(
    ligacao_id: int,
    cro: str = Form(...),
    nome_inscrito: str = Form(...),
    duvida: str = Form(...),
    observacao: str = Form(""),
    session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        return RedirectResponse("/login", status_code=302)
    
    # Verificar permissão para editar
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_edit_delete(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    if duvida not in DUVIDA_OPCOES:
        duvida = DUVIDA_OPCOES[0]
    db = SessionLocal()
    try:
        obj = db.get(Ligacao, ligacao_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Registro não encontrado")

        obj.cro = cro.strip()
        obj.nome_inscrito = nome_inscrito.strip()
        obj.duvida = duvida.strip()
        obj.observacao = (observacao or "").strip()

        db.add(obj)
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/", status_code=303)

# EXCLUIR ligação
@app.post("/excluir/{ligacao_id}")
def excluir(ligacao_id: int, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        return RedirectResponse("/login", status_code=302)
    
    # Verificar permissão para excluir
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_edit_delete(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    db = SessionLocal()
    try:
        obj = db.get(Ligacao, ligacao_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        db.delete(obj)
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/", status_code=303)

# ... (restante do seu app.py permanece igual)
# Certifique-se de que DUVIDA_OPCOES, to_sp(), etc. já existem como te enviei antes.

# Relatórios (página com gráficos e botão de impressão)
@app.get("/relatorios")
def relatorios(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        return RedirectResponse("/login", status_code=302)
    
    # Obter usuário atual
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    
    # Verificar permissão para acessar relatórios
    if not can_access_reports(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado - Você não tem permissão para acessar relatórios")
    
    # agora mandamos as opções para montar o filtro no template
    return templates.TemplateResponse("relatorios.html", {
        "request": request,
        "duvida_opcoes": DUVIDA_OPCOES,
        "current_user": current_user,
        "current_username": current_username,
        "current_user_fullname": get_user_full_name(current_username),
        "can_access_reports": can_access_reports(current_username),
    })

def _parse_date(s: str):
    # "YYYY-MM-DD" -> date; se vazio/None, retorna None
    try:
        if not s:
            return None
        y, m, d = map(int, s.split("-"))
        from datetime import date
        return date(y, m, d)
    except Exception:
        return None

def _filter_rows(rows, start_date, end_date, tipos):
    # start_date/end_date são dates no fuso BR (America/Sao_Paulo)
    # tipos é set() de strings; se vazio, não filtra por tipo
    filtered = []
    for row in rows:
        # row pode ser Ligacao ou tupla (Ligacao.created_at, Ligacao.duvida)
        if isinstance(row, tuple):
            dt, duvida = row
        else:
            dt, duvida = row.created_at, row.duvida

        if not dt:
            continue
        dia_br = to_sp(dt).date()  # dia no fuso America/Sao_Paulo

        if start_date and dia_br < start_date:
            continue
        if end_date and dia_br > end_date:
            continue
        if tipos and duvida not in tipos:
            continue
        filtered.append((dia_br, duvida))
    return filtered

# API: estatística por dúvida (com filtros)
@app.get("/api/stats/por_duvida")
def stats_por_duvida(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    # Verificar permissão para acessar relatórios
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_access_reports(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado - Você não tem permissão para acessar relatórios")
    
    # Query params: start=YYYY-MM-DD, end=YYYY-MM-DD, tipos=csv
    start = _parse_date(request.query_params.get("start"))
    end = _parse_date(request.query_params.get("end"))
    tipos_raw = request.query_params.get("tipos", "")
    tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

    db = SessionLocal()
    try:
        # buscamos created_at e duvida para aplicar filtro no fuso BR
        rows = db.query(Ligacao.created_at, Ligacao.duvida).all()
    finally:
        db.close()

    filtered = _filter_rows(rows, start, end, tipos)

    # conta por tipo
    counts_map = {}
    for _, duvida in filtered:
        counts_map[duvida] = counts_map.get(duvida, 0) + 1

    labels = DUVIDA_OPCOES[:]  # ordem fixa
    counts = [int(counts_map.get(lbl, 0)) for lbl in labels]
    total = sum(counts)
    return {"labels": labels, "counts": counts, "total": total}

# API: estatística por dia (com filtros e fuso BR)
@app.get("/api/stats/por_dia")
def stats_por_dia(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    # Verificar permissão para acessar relatórios
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_access_reports(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado - Você não tem permissão para acessar relatórios")
    
    start = _parse_date(request.query_params.get("start"))
    end = _parse_date(request.query_params.get("end"))
    tipos_raw = request.query_params.get("tipos", "")
    tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

    db = SessionLocal()
    try:
        rows = db.query(Ligacao.created_at, Ligacao.duvida).all()
    finally:
        db.close()

    filtered = _filter_rows(rows, start, end, tipos)

    # grupo por dia
    by_day = {}
    for dia, _ in filtered:
        k = dia.isoformat()
        by_day[k] = by_day.get(k, 0) + 1

    labels = sorted(by_day.keys())
    counts = [by_day[d] for d in labels]
    return {"labels": labels, "counts": counts}

# API: comparativo de ligações por período
@app.get("/api/stats/comparativo_periodo")
def stats_comparativo_periodo(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    # Verificar permissão para acessar relatórios
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_access_reports(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado - Você não tem permissão para acessar relatórios")
    
    periodo = request.query_params.get("periodo", "dia")  # dia, semana, mes, ano
    start = _parse_date(request.query_params.get("start"))
    end = _parse_date(request.query_params.get("end"))
    tipos_raw = request.query_params.get("tipos", "")
    tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

    db = SessionLocal()
    try:
        rows = db.query(Ligacao.created_at, Ligacao.duvida).all()
    finally:
        db.close()

    filtered = _filter_rows(rows, start, end, tipos)
    
    # Agrupar por período
    by_period = {}
    for dia, _ in filtered:
        if periodo == "dia":
            key = dia.isoformat()
        elif periodo == "semana":
            # ISO week format: YYYY-Www
            key = f"{dia.year}-W{dia.isocalendar()[1]:02d}"
        elif periodo == "mes":
            key = f"{dia.year}-{dia.month:02d}"
        elif periodo == "ano":
            key = str(dia.year)
        else:
            key = dia.isoformat()
            
        by_period[key] = by_period.get(key, 0) + 1

    labels = sorted(by_period.keys())
    counts = [by_period[p] for p in labels]
    
    return {
        "labels": labels, 
        "counts": counts,
        "periodo": periodo,
        "total": sum(counts)
    }

# API: pico de horários
@app.get("/api/stats/pico_horarios")
def stats_pico_horarios(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    # Verificar permissão para acessar relatórios
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_access_reports(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado - Você não tem permissão para acessar relatórios")
    
    # Garantir que sempre retornamos a estrutura correta mesmo em caso de erro
    all_hours = [f"{h:02d}:00" for h in range(24)]
    default_response = {
        "labels": all_hours,
        "counts": [0] * 24,
        "total": 0
    }
    
    try:
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        tipos_raw = request.query_params.get("tipos", "")
        tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

        # Buscar dados completos (created_at + duvida) e aplicar filtros corretamente
        db = SessionLocal()
        try:
            all_calls = db.query(Ligacao).all()
        finally:
            db.close()
        
        # Agrupar por hora do dia aplicando filtros
        by_hour = {}
        for call in all_calls:
            if not call.created_at:
                continue
                
            # Converter para fuso BR
            dt_br = to_sp(call.created_at)
            if not dt_br:
                continue
                
            # Aplicar filtros de data
            call_date = dt_br.date()
            if start and call_date < start:
                continue
            if end and call_date > end:
                continue
            if tipos and call.duvida not in tipos:
                continue
                
            # Extrair hora e agrupar
            hour_key = f"{dt_br.hour:02d}:00"
            by_hour[hour_key] = by_hour.get(hour_key, 0) + 1
        
        # Gerar counts para todas as horas (0-23) - sempre 24 horas
        counts = [by_hour.get(hour, 0) for hour in all_hours]
        
        # Retornar estrutura sempre correta
        return {
            "labels": all_hours,
            "counts": counts,
            "total": sum(counts)
        }
    
    except Exception as e:
        # Em caso de erro, retornar estrutura padrão com dados zerados
        # Isso garante que o frontend não quebre
        return default_response

# API: relatório por atendente
@app.get("/api/stats/por_atendente")
def stats_por_atendente(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    # Verificar permissão para acessar relatórios
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_access_reports(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado - Você não tem permissão para acessar relatórios")
    
    start = _parse_date(request.query_params.get("start"))
    end = _parse_date(request.query_params.get("end"))
    tipos_raw = request.query_params.get("tipos", "")
    tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

    db = SessionLocal()
    try:
        query = db.query(Ligacao)
        all_calls = query.all()
    finally:
        db.close()

    by_attendant = {}
    for call in all_calls:
        if not call.created_at:
            continue
            
        # Aplicar filtros de data
        call_date = to_sp(call.created_at).date()
        if start and call_date < start:
            continue
        if end and call_date > end:
            continue
        if tipos and call.duvida not in tipos:
            continue
            
        attendant = call.atendente or "Não informado"
        by_attendant[attendant] = by_attendant.get(attendant, 0) + 1
    
    # Ordenar por quantidade (decrescente)
    sorted_attendants = sorted(by_attendant.items(), key=lambda x: x[1], reverse=True)
    
    labels = [item[0] for item in sorted_attendants]
    counts = [item[1] for item in sorted_attendants]
    
    return {
        "labels": labels,
        "counts": counts,
        "total": sum(counts)
    }

# API: exportar dados em CSV
@app.get("/api/export/csv")
def export_csv(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    # Verificar permissão para acessar relatórios
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_access_reports(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado - Você não tem permissão para acessar relatórios")
    
    report_type = request.query_params.get("tipo", "por_duvida")
    start = _parse_date(request.query_params.get("start"))
    end = _parse_date(request.query_params.get("end"))
    tipos_raw = request.query_params.get("tipos", "")
    tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

    db = SessionLocal()
    try:
        all_calls = db.query(Ligacao).all()
    finally:
        db.close()

    # Filtrar dados
    filtered_calls = []
    for call in all_calls:
        if not call.created_at:
            continue
            
        call_date = to_sp(call.created_at).date()
        if start and call_date < start:
            continue
        if end and call_date > end:
            continue
        if tipos and call.duvida not in tipos:
            continue
        filtered_calls.append(call)

    # Criar CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    if report_type == "detalhado":
        # Exportar dados detalhados
        writer.writerow(["ID", "CRO", "Nome Inscrito", "Dúvida", "Observação", "Atendente", "Data/Hora"])
        for call in filtered_calls:
            writer.writerow([
                call.id,
                call.cro,
                call.nome_inscrito,
                call.duvida,
                call.observacao or "",
                call.atendente or "Não informado",
                format_sp(call.created_at)
            ])
    else:
        # Exportar relatório resumido por tipo de dúvida
        by_duvida = {}
        for call in filtered_calls:
            by_duvida[call.duvida] = by_duvida.get(call.duvida, 0) + 1
        
        writer.writerow(["Tipo de Dúvida", "Quantidade"])
        for duvida in DUVIDA_OPCOES:
            count = by_duvida.get(duvida, 0)
            if count > 0:
                writer.writerow([duvida, count])
    
    output.seek(0)
    response = StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=relatorio_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )
    return response

# API: exportar dados em PDF
@app.get("/api/export/pdf")
def export_pdf(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    # Verificar permissão para acessar relatórios
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_access_reports(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado - Você não tem permissão para acessar relatórios")
    
    report_type = request.query_params.get("tipo", "por_duvida")
    start = _parse_date(request.query_params.get("start"))
    end = _parse_date(request.query_params.get("end"))
    tipos_raw = request.query_params.get("tipos", "")
    tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

    db = SessionLocal()
    try:
        all_calls = db.query(Ligacao).all()
    finally:
        db.close()

    # Filtrar dados
    filtered_calls = []
    for call in all_calls:
        if not call.created_at:
            continue
            
        call_date = to_sp(call.created_at).date()
        if start and call_date < start:
            continue
        if end and call_date > end:
            continue
        if tipos and call.duvida not in tipos:
            continue
        filtered_calls.append(call)

    # Criar PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    story.append(Paragraph("ELEIÇÕES CRORS - 2025", title_style))
    story.append(Paragraph(f"Relatório de Ligações - {report_type.replace('_', ' ').title()}", styles['Heading2']))
    
    # Período
    if start or end:
        periodo_text = f"Período: {start.strftime('%d/%m/%Y') if start else 'Início'} até {end.strftime('%d/%m/%Y') if end else 'Fim'}"
        story.append(Paragraph(periodo_text, styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    if report_type == "detalhado":
        # Tabela detalhada
        data = [["ID", "CRO", "Nome", "Dúvida", "Atendente", "Data/Hora"]]
        for call in filtered_calls[:100]:  # Limitar a 100 registros para PDF
            data.append([
                str(call.id),
                call.cro[:15] + "..." if len(call.cro) > 15 else call.cro,
                call.nome_inscrito[:20] + "..." if len(call.nome_inscrito) > 20 else call.nome_inscrito,
                call.duvida[:30] + "..." if len(call.duvida) > 30 else call.duvida,
                (call.atendente or "N/A")[:15] + "..." if call.atendente and len(call.atendente) > 15 else (call.atendente or "N/A"),
                format_sp(call.created_at)[:16]  # Só data e hora, sem segundos
            ])
    else:
        # Relatório resumido
        by_duvida = {}
        for call in filtered_calls:
            by_duvida[call.duvida] = by_duvida.get(call.duvida, 0) + 1
        
        data = [["Tipo de Dúvida", "Quantidade", "Percentual"]]
        total = len(filtered_calls)
        for duvida in DUVIDA_OPCOES:
            count = by_duvida.get(duvida, 0)
            if count > 0:
                pct = f"{(count/total*100):.1f}%" if total > 0 else "0%"
                data.append([
                    duvida[:40] + "..." if len(duvida) > 40 else duvida,
                    str(count),
                    pct
                ])
    
    # Criar tabela
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table)
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Total de registros: {len(filtered_calls)}", styles['Normal']))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    
    response = StreamingResponse(
        io.BytesIO(buffer.getvalue()),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=relatorio_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"}
    )
    return response

# === ROTAS PARA PESQUISA DE PROFISSIONAIS APTOS AO VOTO ===

@app.get("/pesquisa-profissional")
def pesquisa_profissional(request: Request, session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    """Página de pesquisa de profissionais aptos ao voto"""
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        return RedirectResponse("/login", status_code=302)
    
    # Obter usuário atual
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    
    return templates.TemplateResponse("pesquisa_profissional.html", {
        "request": request,
        "current_user": current_user,
        "current_username": current_username,
        "current_user_fullname": get_user_full_name(current_username),
        "can_access_reports": can_access_reports(current_username),
        "can_edit_delete": can_edit_delete(current_username),
    })

@app.post("/upload-csv-profissionais")
async def upload_csv_profissionais(
    request: Request,
    csv_file: UploadFile = File(...), 
    session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)
):
    """Upload e processamento do arquivo CSV com profissionais aptos ao voto"""
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        return RedirectResponse("/login", status_code=302)
    
    # Verificar permissão (apenas administrador pode fazer upload)
    current_user = active_sessions[session_token]
    current_username = current_user['username']
    if not can_access_reports(current_username):
        raise HTTPException(status_code=403, detail="Acesso negado - Apenas administradores podem importar CSV")
    
    # Validar tipo de arquivo
    allowed_extensions = ['.csv', '.xls', '.xlsx']
    file_extension = None
    if csv_file.filename:
        file_extension = csv_file.filename.lower().split('.')[-1]
        if f'.{file_extension}' not in allowed_extensions:
            return templates.TemplateResponse("pesquisa_profissional.html", {
                "request": request,
                "current_user": current_user,
                "current_username": current_username,
                "current_user_fullname": get_user_full_name(current_username),
                "can_access_reports": can_access_reports(current_username),
                "can_edit_delete": can_edit_delete(current_username),
                "error_message": "Por favor, envie um arquivo válido (.csv, .xls, .xlsx)",
            })
    
    try:
        # Ler conteúdo do arquivo
        content = await csv_file.read()
        
        # Processar dados conforme o tipo de arquivo
        import pandas as pd
        from io import StringIO, BytesIO
        
        # Determinar como ler o arquivo baseado na extensão
        if file_extension == 'csv':
            # Para CSV, decodificar como texto
            csv_string = content.decode('utf-8')
            df = pd.read_csv(StringIO(csv_string))
        elif file_extension in ['xls', 'xlsx']:
            # Para Excel, ler direto dos bytes
            df = pd.read_excel(BytesIO(content), engine='openpyxl' if file_extension == 'xlsx' else 'xlrd')
        else:
            raise ValueError("Formato de arquivo não suportado")
        
        # Validar se o DataFrame não está vazio
        if df.empty:
            raise ValueError("O arquivo está vazio")
        
        # Mapear colunas possíveis (ignorando case e espaços)
        available_cols = [col.lower().strip() for col in df.columns]
        
        # Mapear colunas possíveis
        name_cols = ['nome', 'nome_profissional', 'profissional', 'nome_inscrito', 'nome_completo']
        cro_cols = ['numero_cro', 'cro', 'inscricao', 'numero_inscricao', 'registro']
        situacao_cols = ['situacao', 'status', 'condicao']
        categoria_cols = ['categoria', 'tipo', 'classificacao']
        cpf_cols = ['cpf', 'documento']
        email_cols = ['email', 'email_principal']
        outros_emails_cols = ['outros_emails', 'email_secundario', 'emails_alternativos']
        celular_cols = ['celular_atualizado', 'celular', 'telefone_celular', 'telefone_principal']
        outros_telefones_cols = ['outros_telefones', 'telefones_alternativos', 'telefone_secundario']
        
        # Variáveis para armazenar as colunas encontradas
        name_col = None
        cro_col = None
        situacao_col = None
        categoria_col = None
        cpf_col = None
        email_col = None
        outros_emails_col = None
        celular_col = None
        outros_telefones_col = None
        
        # Função auxiliar para encontrar coluna
        def find_column(possible_names, available_columns, df_columns):
            for col_name in possible_names:
                if col_name in available_columns:
                    return df_columns[available_columns.index(col_name)]
            return None
        
        # Função auxiliar para processar numero_cro e remover decimais desnecessários
        def process_numero_cro(value):
            """Processa o campo numero_cro para garantir que floats como 9659.0 sejam convertidos para '9659'"""
            if pd.notna(value):
                # Convert to string first
                str_value = str(value).strip()
                # If it's a float-like string ending in .0, remove the decimal part
                if str_value.endswith('.0'):
                    return str_value[:-2]
                else:
                    # Try to convert to float and back to int to handle actual floats
                    try:
                        float_val = float(str_value)
                        if float_val.is_integer():
                            return str(int(float_val))
                        else:
                            return str_value  # Keep as is if not integer
                    except ValueError:
                        return str_value  # Keep as is if not numeric
            else:
                return ""
        
        # Encontrar colunas usando a função auxiliar
        name_col = find_column(name_cols, available_cols, df.columns)
        cro_col = find_column(cro_cols, available_cols, df.columns)
        situacao_col = find_column(situacao_cols, available_cols, df.columns)
        categoria_col = find_column(categoria_cols, available_cols, df.columns)
        cpf_col = find_column(cpf_cols, available_cols, df.columns)
        email_col = find_column(email_cols, available_cols, df.columns)
        outros_emails_col = find_column(outros_emails_cols, available_cols, df.columns)
        celular_col = find_column(celular_cols, available_cols, df.columns)
        outros_telefones_col = find_column(outros_telefones_cols, available_cols, df.columns)
        
        if not name_col or not cro_col:
            available_cols_str = ", ".join(df.columns.tolist())
            raise ValueError(f"CSV deve conter colunas para 'nome' e 'numero_cro'. Colunas encontradas: {available_cols_str}")
        
        # Limpar tabela existente antes de importar novos dados
        db = SessionLocal()
        try:
            db.query(ProfissionalApto).delete()
            db.commit()
            
            # Processar cada linha do CSV
            success_count = 0
            for _, row in df.iterrows():
                # Extrair dados das colunas identificadas
                nome = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
                numero_cro = process_numero_cro(row[cro_col])
                situacao = str(row[situacao_col]).strip() if situacao_col and pd.notna(row[situacao_col]) else ""
                categoria = str(row[categoria_col]).strip() if categoria_col and pd.notna(row[categoria_col]) else ""
                cpf = str(row[cpf_col]).strip() if cpf_col and pd.notna(row[cpf_col]) else ""
                email = str(row[email_col]).strip() if email_col and pd.notna(row[email_col]) else ""
                outros_emails = str(row[outros_emails_col]).strip() if outros_emails_col and pd.notna(row[outros_emails_col]) else ""
                celular_atualizado = str(row[celular_col]).strip() if celular_col and pd.notna(row[celular_col]) else ""
                outros_telefones = str(row[outros_telefones_col]).strip() if outros_telefones_col and pd.notna(row[outros_telefones_col]) else ""
                
                # Colunas mapeadas para não incluir em outras_informacoes
                mapped_cols = [name_col, cro_col, situacao_col, categoria_col, cpf_col, 
                              email_col, outros_emails_col, celular_col, outros_telefones_col]
                mapped_cols = [col for col in mapped_cols if col is not None]
                
                # Construir outras informações (colunas não mapeadas)
                outras_info = {}
                for col in df.columns:
                    if col not in mapped_cols:
                        value = row[col]
                        if pd.notna(value):
                            outras_info[col] = str(value).strip()
                
                outras_informacoes = str(outras_info) if outras_info else ""
                
                # Validar dados obrigatórios
                if nome and numero_cro:
                    profissional = ProfissionalApto(
                        nome=nome,
                        numero_cro=numero_cro,
                        categoria=categoria,
                        cpf=cpf,
                        email=email,
                        outros_emails=outros_emails,
                        celular_atualizado=celular_atualizado,
                        outros_telefones=outros_telefones,
                        situacao=situacao,
                        outras_informacoes=outras_informacoes,
                        imported_at=datetime.now(timezone.utc)
                    )
                    db.add(profissional)
                    success_count += 1
            
            db.commit()
            
            return templates.TemplateResponse("pesquisa_profissional.html", {
                "request": request,
                "current_user": current_user,
                "current_username": current_username,
                "current_user_fullname": get_user_full_name(current_username),
                "can_access_reports": can_access_reports(current_username),
                "can_edit_delete": can_edit_delete(current_username),
                "success_message": f"Planilha importada com sucesso! {success_count} profissionais cadastrados.",
            })
            
        finally:
            db.close()
            
    except Exception as e:
        return templates.TemplateResponse("pesquisa_profissional.html", {
            "request": request,
            "current_user": current_user,
            "current_username": current_username,
            "current_user_fullname": get_user_full_name(current_username),
            "can_access_reports": can_access_reports(current_username),
            "can_edit_delete": can_edit_delete(current_username),
            "error_message": f"Erro ao processar planilha: {str(e)}",
        })

@app.get("/api/pesquisar-profissional")
def pesquisar_profissional(
    request: Request,
    q: str = "",  # Query de pesquisa
    session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)
):
    """API para pesquisar profissionais por nome ou CRO"""
    # Verificar autenticação
    if not session_token or not is_valid_session(session_token):
        raise HTTPException(status_code=401, detail="Não autorizado")
    
    if not q or len(q.strip()) < 2:
        return {"results": [], "message": "Digite pelo menos 2 caracteres para pesquisar"}
    
    query = q.strip()
    
    db = SessionLocal()
    try:
        # Pesquisar por nome (LIKE), número CRO (exato) ou qualquer campo adicional
        results = db.query(ProfissionalApto).filter(
            (ProfissionalApto.nome.ilike(f"%{query}%")) |
            (ProfissionalApto.numero_cro == query) |
            (ProfissionalApto.categoria.ilike(f"%{query}%")) |
            (ProfissionalApto.cpf.ilike(f"%{query}%")) |
            (ProfissionalApto.email.ilike(f"%{query}%")) |
            (ProfissionalApto.outros_emails.ilike(f"%{query}%")) |
            (ProfissionalApto.celular_atualizado.ilike(f"%{query}%")) |
            (ProfissionalApto.outros_telefones.ilike(f"%{query}%")) |
            (ProfissionalApto.situacao.ilike(f"%{query}%")) |
            (ProfissionalApto.outras_informacoes.ilike(f"%{query}%"))
        ).limit(50).all()  # Limitar a 50 resultados
        
        # Converter para dicionário para JSON
        profissionais = []
        for p in results:
            outras_info = {}
            try:
                if p.outras_informacoes:
                    import ast
                    outras_info = ast.literal_eval(p.outras_informacoes)
            except:
                outras_info = {}
            
            profissionais.append({
                "id": p.id,
                "nome": p.nome,  # NOME_COMPLETO
                "numero_cro": p.numero_cro,  # INSCRIÇÃO
                "categoria": p.categoria or "",  # CATEGORIA
                "cpf": p.cpf or "",  # CPF
                "email": p.email or "",  # EMAIL
                "outros_emails": p.outros_emails or "",  # OUTROS_EMAILS
                "celular_atualizado": p.celular_atualizado or "",  # CELULAR_ATUALIZADO
                "outros_telefones": p.outros_telefones or "",  # OUTROS_TELEFONES
                "situacao": p.situacao or "",
                "outras_informacoes": outras_info,
                "data_importacao": format_sp(p.imported_at)
            })
        
        return {
            "results": profissionais,
            "total": len(profissionais),
            "query": query
        }
        
    finally:
        db.close()

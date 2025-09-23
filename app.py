import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import secrets

from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, Column, Integer, String, DateTime, text, func, inspect
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from dotenv import load_dotenv

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
    created_at = Column(DateTime, nullable=False, server_default=func.now())

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
    
    if duvida not in DUVIDA_OPCOES:
        duvida = DUVIDA_OPCOES[0]
    db = SessionLocal()
    try:
        novo = Ligacao(
            cro=cro.strip(),
            nome_inscrito=nome_inscrito.strip(),
            duvida=duvida.strip(),
            observacao=(observacao or "").strip(),
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
    
    # agora mandamos as opções para montar o filtro no template
    return templates.TemplateResponse("relatorios.html", {
        "request": request,
        "duvida_opcoes": DUVIDA_OPCOES,
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

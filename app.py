import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome_completo = Column(String(255), nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    password = Column(String(20), nullable=False)  # dd/mm/yyyy format
    data_nascimento = Column(String(10), nullable=False)  # dd/mm/yyyy format

class Ligacao(Base):
    __tablename__ = "ligacoes"
    id = Column(Integer, primary_key=True, index=True)
    cro = Column(String(50), nullable=False)
    nome_inscrito = Column(String(255), nullable=False)
    duvida = Column(String(100), nullable=False)
    observacao = Column(String(1000), nullable=True)
    attendant_username = Column(String(100), nullable=True)  # New field
    created_at = Column(DateTime, nullable=False, server_default=func.now())

# Cria tabela se não existir
Base.metadata.create_all(bind=engine)

# MIGRAÇÃO LEVE: adiciona colunas que faltam
insp = inspect(engine)
cols = [c["name"] for c in insp.get_columns("ligacoes")]
if "observacao" not in cols:
    with engine.begin() as conn:
        if DATABASE_URL.startswith("sqlite"):
            conn.execute(text("ALTER TABLE ligacoes ADD COLUMN observacao VARCHAR(1000)"))
        else:
            conn.execute(text("ALTER TABLE ligacoes ADD COLUMN observacao VARCHAR(1000) NULL"))

if "attendant_username" not in cols:
    with engine.begin() as conn:
        if DATABASE_URL.startswith("sqlite"):
            conn.execute(text("ALTER TABLE ligacoes ADD COLUMN attendant_username VARCHAR(100)"))
        else:
            conn.execute(text("ALTER TABLE ligacoes ADD COLUMN attendant_username VARCHAR(100) NULL"))

DUVIDA_OPCOES = [
    "Dúvida sanada - Profissional apto ao voto",
    "Dúvida sanada - Profissional não apto ao voto",
    "Dúvida encaminhada ao jurídico",
    "Dúvida sanada - Profissional não apto ao voto (débitos)",
    "Dúvida sanada - Profissional não apto ao voto (atualização cadastral)",
    "Dúvida sanada - Profissional não apto ao voto (-60 dias)",
    "Dúvida sanada - Profissional não apto ao voto (militar exclusivo)",
]

# Predefined users - expandir conforme a imagem mencionada
USUARIOS_PREDEFINIDOS = [
    {
        "nome_completo": "Igor Ricardo de Souza Sansone",
        "data_nascimento": "15/03/1985"  # Exemplo - ajustar conforme dados reais
    },
    {
        "nome_completo": "Maria Silva Santos",
        "data_nascimento": "10/07/1990"  # Usuário de teste não-master
    },
    # Adicionar outros usuários conforme a imagem
]

def generate_username(nome_completo):
    """Gera username: primeiro nome + último sobrenome (lowercase, sem espaços)"""
    partes = nome_completo.strip().split()
    if len(partes) < 2:
        return partes[0].lower().replace(" ", "")
    primeiro_nome = partes[0]
    ultimo_sobrenome = partes[-1]
    return f"{primeiro_nome}{ultimo_sobrenome}".lower().replace(" ", "")

def create_predefined_users():
    """Cria usuários predefinidos se não existirem"""
    db = SessionLocal()
    try:
        for user_data in USUARIOS_PREDEFINIDOS:
            username = generate_username(user_data["nome_completo"])
            existing = db.query(Usuario).filter(Usuario.username == username).first()
            if not existing:
                novo_usuario = Usuario(
                    nome_completo=user_data["nome_completo"],
                    username=username,
                    password=user_data["data_nascimento"],
                    data_nascimento=user_data["data_nascimento"]
                )
                db.add(novo_usuario)
        db.commit()
    finally:
        db.close()

# Criar usuários predefinidos
create_predefined_users()

MASTER_USER = "igorsansone"  # Master user com privilégios especiais

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

# Authentication helpers
def get_current_user(session_token: str = Cookie(None)):
    """Recupera o usuário atual da sessão"""
    if not session_token:
        return None
    
    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(Usuario.username == session_token).first()
        return usuario
    finally:
        db.close()

def authenticate_user(username: str, password: str):
    """Autentica usuário com username/password"""
    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(
            Usuario.username == username,
            Usuario.password == password
        ).first()
        return usuario
    finally:
        db.close()

def require_authentication(current_user = Depends(get_current_user)):
    """Dependência para exigir autenticação"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Usuário não autenticado")
    return current_user

def require_master_user(current_user = Depends(require_authentication)):
    """Dependência para exigir usuário master"""
    if current_user.username != MASTER_USER:
        raise HTTPException(status_code=403, detail="Acesso restrito ao usuário master")
    return current_user

# Página inicial: formulário e lista
@app.get("/")
def home(request: Request, current_user = Depends(get_current_user)):
    # Redirecionar para login se não autenticado
    if not current_user:
        return RedirectResponse("/login", status_code=303)
        
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
            "is_master": current_user.username == MASTER_USER,
        },
    )

# Login page
@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Login submission
@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html", 
            {
                "request": request, 
                "error": "Usuário ou senha inválidos"
            }
        )
    
    # Set session cookie and redirect
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(key="session_token", value=user.username, httponly=True)
    return response

# Logout
@app.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(key="session_token")
    return response

# Cadastrar ligação
@app.post("/cadastrar")
def cadastrar(
    cro: str = Form(...),
    nome_inscrito: str = Form(...),
    duvida: str = Form(...),
    observacao: str = Form(""),
    current_user = Depends(require_authentication),
):
    if duvida not in DUVIDA_OPCOES:
        duvida = DUVIDA_OPCOES[0]
    db = SessionLocal()
    try:
        novo = Ligacao(
            cro=cro.strip(),
            nome_inscrito=nome_inscrito.strip(),
            duvida=duvida.strip(),
            observacao=(observacao or "").strip(),
            attendant_username=current_user.username,
            created_at=datetime.now(timezone.utc),
        )
        db.add(novo)
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/", status_code=303)

# --- EDITAR (GET): formulário preenchido
@app.get("/editar/{ligacao_id}")
def editar_form(request: Request, ligacao_id: int, current_user = Depends(require_master_user)):
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
    current_user = Depends(require_master_user),
):
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
def excluir(ligacao_id: int, current_user = Depends(require_master_user)):
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
def relatorios(request: Request, current_user = Depends(require_authentication)):
    # agora mandamos as opções para montar o filtro no template
    return templates.TemplateResponse("relatorios.html", {
        "request": request,
        "duvida_opcoes": DUVIDA_OPCOES,
        "current_user": current_user,
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
def stats_por_duvida(request: Request):
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
def stats_por_dia(request: Request):
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

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Form, HTTPException
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
    # Usamos server_default para DB e também podemos setar valor em Python (UTC) no insert
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

app = FastAPI(title="Controle de Ligações - Eleição 2025")

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

# Página inicial: formulário e lista
@app.get("/")
def home(request: Request):
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
            "format_sp": format_sp,  # função para usar no template
        },
    )

# Cadastrar ligação
@app.post("/cadastrar")
def cadastrar(
    cro: str = Form(...),
    nome_inscrito: str = Form(...),
    duvida: str = Form(...),
    observacao: str = Form(""),
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
            # Garantimos UTC no Python; o server_default também cobre se não setarmos
            created_at=datetime.now(timezone.utc),
        )
        db.add(novo)
        db.commit()
    finally:
        db.close()
    return RedirectResponse("/", status_code=303)

# EXCLUIR ligação
@app.post("/excluir/{ligacao_id}")
def excluir(ligacao_id: int):
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

# Relatórios (página com gráficos e botão de impressão)
@app.get("/relatorios")
def relatorios(request: Request):
    return templates.TemplateResponse("relatorios.html", {"request": request})

# API: estatística por dúvida
@app.get("/api/stats/por_duvida")
def stats_por_duvida():
    db = SessionLocal()
    try:
        rows = db.query(Ligacao.duvida, func.count(Ligacao.id)).group_by(Ligacao.duvida).all()
        data = {duvida: count for duvida, count in rows}
        labels = DUVIDA_OPCOES
        counts = [int(data.get(lbl, 0)) for lbl in labels]
        return {"labels": labels, "counts": counts}
    finally:
        db.close()

# API: estatística por dia (convertendo para America/Sao_Paulo)
@app.get("/api/stats/por_dia")
def stats_por_dia():
    db = SessionLocal()
    try:
        # Buscamos todos os timestamps e agrupamos em Python pelo dia no fuso de SP/RS.
        rows = db.query(Ligacao.created_at).all()
        counts_by_day = {}
        for (dt,) in rows:
            if not dt:
                continue
            d_sp = to_sp(dt).date().isoformat()  # YYYY-MM-DD no fuso BR
            counts_by_day[d_sp] = counts_by_day.get(d_sp, 0) + 1

        labels = sorted(counts_by_day.keys())
        counts = [counts_by_day[d] for d in labels]
        return {"labels": labels, "counts": counts}
    finally:
        db.close()

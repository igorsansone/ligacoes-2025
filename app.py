import os
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, Column, Integer, String, DateTime, text, func
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from dotenv import load_dotenv

# Carrega .env (opcional)
load_dotenv()

# Banco de dados: SQLite local por padrão; PostgreSQL se DATABASE_URL estiver definido
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")
# Ajuste para SQLite com check_same_thread se necessário
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
    created_at = Column(DateTime, nullable=False, server_default=func.now())

Base.metadata.create_all(bind=engine)

DUVIDA_OPCOES = [
    "Dúvida sanada - Profissional apto ao voto",
    "Dúvida sanada - Profissional não apto ao voto",
    "Dúvida encaminhada ao jurídico",
    "Dúvida sanada - Profissional não apto ao voto (débitos)",
    "Dúvida sanada - Profissional não apto ao voto (atualização cadastral)",
    "Dúvida sanada - Profissional não apto ao voto (-60 dias)",
    "Dúvida sanada - Profissional não apto ao voto (militar exclusivo)",
]

app = FastAPI(title="Controle de Ligações - Eleição 2025")

# Static / Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Página inicial: formulário e lista
@app.get("/")
def home(request: Request):
    db = SessionLocal()
    try:
        ligacoes = db.query(Ligacao).order_by(Ligacao.id.desc()).limit(50).all()
    finally:
        db.close()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "duvida_opcoes": DUVIDA_OPCOES,
        "ligacoes": ligacoes,
    })

# Cadastrar ligação
@app.post("/cadastrar")
def cadastrar(
    cro: str = Form(...),
    nome_inscrito: str = Form(...),
    duvida: str = Form(...),
):
    if duvida not in DUVIDA_OPCOES:
        # Sanitiza para evitar valores inesperados
        duvida = DUVIDA_OPCOES[0]
    db = SessionLocal()
    try:
        # Cria registro com timestamp (UTC) para consistência
        novo = Ligacao(
            cro=cro.strip(),
            nome_inscrito=nome_inscrito.strip(),
            duvida=duvida.strip(),
        )
        db.add(novo)
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
        # Garante que todas as opções apareçam no gráfico (mesmo com zero)
        labels = DUVIDA_OPCOES
        counts = [int(data.get(lbl, 0)) for lbl in labels]
        return {"labels": labels, "counts": counts}
    finally:
        db.close()

# API: estatística por dia (data do created_at)
@app.get("/api/stats/por_dia")
def stats_por_dia():
    db = SessionLocal()
    try:
        # Função de data por banco (SQLite vs Postgres)
        if DATABASE_URL.startswith("sqlite"):
            rows = db.execute(text("SELECT strftime('%Y-%m-%d', created_at) as dia, COUNT(*) FROM ligacoes GROUP BY dia ORDER BY dia")).all()
        else:
            rows = db.execute(text("SELECT to_char(created_at::date, 'YYYY-MM-DD') as dia, COUNT(*) FROM ligacoes GROUP BY dia ORDER BY dia")).all()
        labels = [r[0] for r in rows]
        counts = [int(r[1]) for r in rows]
        return {"labels": labels, "counts": counts}
    finally:
        db.close()

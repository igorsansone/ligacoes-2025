"""
Sistema de Gerenciamento de Processos Jurídicos
Versão 2.0 - Transformado a partir do sistema de ligações CRO/RS

Este arquivo mantém compatibilidade com o sistema anterior enquanto adiciona
todas as funcionalidades de gerenciamento de processos jurídicos.
"""

import os
from datetime import datetime, timezone, date, timedelta
from zoneinfo import ZoneInfo
import secrets
import io
import csv
import json
from typing import List, Dict, Any, Optional
import hashlib

from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie, UploadFile, File, Query
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, text, inspect, and_, or_, desc, asc
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv
import pandas as pd
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

# Importar novos modelos
from models import (
    Base, Usuario, Processo, Anexo, Tarefa, Prazo, Compromisso, 
    ChatCanal, ChatMensagem, Notificacao, HistoricoAlteracoes, Permissao,
    Ligacao, ProfissionalApto,  # Modelos antigos para compatibilidade
    TipoProcesso, StatusProcesso, PrioridadeProcesso, TipoUsuario, 
    StatusTarefa, TipoNotificacao
)

# Carrega .env (opcional)
load_dotenv()

# Fuso desejado (Brasil/RS)
TZ = ZoneInfo("America/Sao_Paulo")

# Banco de dados: SQLite local por padrão; PostgreSQL se DATABASE_URL estiver definido
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./processo_management.db")

# Normaliza URL do Railway se vier como postgres:// (SQLAlchemy recomenda postgresql+psycopg2://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

# Ajuste para SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Cria todas as tabelas
Base.metadata.create_all(bind=engine)

# === MIGRAÇÃO E COMPATIBILIDADE ===

def migrate_old_system():
    """Migra dados do sistema antigo se necessário"""
    db = SessionLocal()
    try:
        # Verificar se já temos usuários no novo sistema
        usuarios_count = db.query(Usuario).count()
        if usuarios_count == 0:
            # Migrar usuários antigos
            print("Migrando usuários do sistema antigo...")
            
            # Buscar colaboradores da lista original
            colaboradores = [
                ("André Nunes Flores", "13/05/1983", "andreflores"),
                ("Andréia Carla Viezzer", "08/06/1973", "andreiaviezzer"),
                ("Andressa Trápaga Paiz", "11/02/1990", "andressapaiz"),
                ("Bianca Carvalho Aguilar", "19/12/1997", "biancaaguilar"),
                ("Carina Reis Silveira", "02/01/1978", "carinasilveira"),
                ("Carlos Edvan Carvalho Duarte", "16/04/2001", "carlosduarte"),
                ("Clarissa da Costa Barcellos", "16/11/1987", "clarissabarcellos"),
                ("Cleonice Lourenço Guimarães Muller", "14/09/1961", "cleonicemuller"),
                ("Cristiano Grimaldi Boff", "17/03/1983", "cristianoboff"),
                ("Daniel José Bahi Aymone", "02/05/1979", "danielaymone"),
                ("Giovanna de Castro Bonamigo", "30/08/1994", "giovannabonamigo"),
                ("Gustavo Rodrigues Graminho", "14/06/1990", "gustavograminho"),
                ("Gustavo Santos de Barros", "03/05/2003", "gustavobarros"),
                ("Igor Ricardo de Souza Sansone", "30/10/1987", "igorsansone"),
                ("Jefferson Rocho Barth", "15/10/1985", "jeffersonbarth"),
                ("João Francisco Schmidt", "11/07/1964", "joaoschmidt"),
                ("João Paulo Melo de Carvalho", "24/12/1980", "joaocarvalho"),
                ("Jorge Miguel Chaves", "01/02/1958", "jorgechaves"),
                ("Leandro Oscar Collares da Silva", "12/09/1978", "leandrosilva"),
                ("Leonardo Carvalho da Rosa", "31/05/1984", "leonardorosa"),
                ("Leticia Pereira Voltz Alfaro", "16/02/1973", "leticiaalfaro"),
                ("Liliane Correa Bruno", "10/06/1984", "lilianebruno"),
                ("Luciano Dichel", "26/08/1981", "lucianodichel"),
                ("Luiza Gutheil Bayer", "19/07/1993", "luizabayer"),
                ("Matheus Prato da Silva", "09/09/1998", "matheussilva"),
                ("Marilda Zanella Busanello", "06/07/1963", "marildabusanello"),
                ("Rodrigo Fernandes Floriano", "29/07/1978", "rodrigofloriano"),
                ("Tânia Marli Mendes Leite", "19/08/1962", "tanialeite"),
                ("Tanise Barbosa Ramaswami", "15/08/1991", "taniseramaswami"),
                ("Tatiana de Carli da Silva", "04/05/1974", "tatianasilva"),
                ("Tatiana Nuñez Rosa", "13/08/1979", "tatianaRosa"),
                ("Willians da Silva Marks", "22/10/1983", "wiliansmarks"),
            ]
            
            for nome, nascimento, username in colaboradores:
                # Gerar email baseado no username
                email = f"{username}@crors.gov.br"
                
                # Gerar hash da senha (data de nascimento)
                dia, mes, ano = nascimento.split('/')
                senha = f"{dia}{mes}{ano}"
                senha_hash = hashlib.sha256(senha.encode()).hexdigest()
                
                # Determinar tipo de usuário
                tipo = TipoUsuario.ADMIN if username == "igorsansone" else TipoUsuario.ASSISTENTE
                
                usuario = Usuario(
                    username=username,
                    nome_completo=nome,
                    email=email,
                    senha_hash=senha_hash,
                    tipo_usuario=tipo,
                    ativo=True,
                    setor="CRO/RS",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(usuario)
            
            db.commit()
            print(f"Migrados {len(colaboradores)} usuários.")
            
        # Criar canal de chat geral se não existir
        canal_geral = db.query(ChatCanal).filter(ChatCanal.processo_id.is_(None)).first()
        if not canal_geral:
            canal_geral = ChatCanal(
                nome="Geral",
                descricao="Canal geral para discussões da equipe",
                ativo=True,
                created_at=datetime.now(timezone.utc)
            )
            db.add(canal_geral)
            db.commit()
            print("Canal de chat geral criado.")
            
    except Exception as e:
        print(f"Erro na migração: {e}")
        db.rollback()
    finally:
        db.close()

# Executar migração na inicialização
migrate_old_system()

# === CONSTANTES E CONFIGURAÇÕES ===

# Manter opções antigas para compatibilidade
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
os.makedirs("uploads", exist_ok=True)  # Para anexos de processos

app = FastAPI(title="Sistema de Gerenciamento de Processos Jurídicos - CRO/RS")

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

# === AUTENTICAÇÃO E SESSÃO ===

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
SESSION_COOKIE_NAME = "session_token"

# Sessions ativas (em memória - em produção usar Redis/Database)
# Estrutura: {token: {'user_id': int, 'username': str, 'tipo_usuario': str}}
active_sessions = {}

def create_session(user: Usuario) -> str:
    """Cria uma nova sessão e retorna o token"""
    token = secrets.token_urlsafe(32)
    active_sessions[token] = {
        'user_id': user.id,
        'username': user.username,
        'tipo_usuario': user.tipo_usuario.value,
        'nome_completo': user.nome_completo
    }
    
    # Atualizar último login
    db = SessionLocal()
    try:
        user.ultimo_login = datetime.now(timezone.utc)
        db.add(user)
        db.commit()
    except:
        pass
    finally:
        db.close()
    
    return token

def is_valid_session(token: str) -> bool:
    """Verifica se a sessão é válida"""
    return token in active_sessions

def invalidate_session(token: str):
    """Invalida uma sessão"""
    active_sessions.pop(token, None)

def get_current_user_session(session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    """Dependency para obter usuário atual da sessão"""
    if not session_token or not is_valid_session(session_token):
        return None
    return active_sessions[session_token]

def require_auth(session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    """Dependency que requer autenticação"""
    if not session_token or not is_valid_session(session_token):
        raise HTTPException(status_code=401, detail="Não autorizado")
    return active_sessions[session_token]

def get_current_user_db(session_data: dict = Depends(require_auth)) -> Usuario:
    """Dependency para obter usuário atual do banco"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == session_data['user_id']).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        return user
    finally:
        db.close()

# === FUNÇÕES DE PERMISSÃO ===

def has_permission(user: Usuario, recurso: str, acao: str) -> bool:
    """Verifica se o usuário tem permissão para realizar uma ação"""
    # Administradores têm acesso total
    if user.tipo_usuario == TipoUsuario.ADMIN:
        return True
    
    # Verificar permissões específicas no banco
    db = SessionLocal()
    try:
        permissao = db.query(Permissao).filter(
            and_(
                Permissao.usuario_id == user.id,
                Permissao.recurso == recurso,
                Permissao.acao == acao
            )
        ).first()
        
        if permissao:
            return permissao.permitido
        
        # Permissões padrão por tipo de usuário
        default_permissions = {
            TipoUsuario.ADVOGADO: {
                'processos': ['create', 'read', 'update'],
                'tarefas': ['create', 'read', 'update'],
                'compromissos': ['create', 'read', 'update', 'delete'],
                'chat': ['read', 'create'],
                'relatorios': ['read', 'export']
            },
            TipoUsuario.ASSISTENTE: {
                'processos': ['read', 'update'],
                'tarefas': ['read', 'update'],
                'compromissos': ['read', 'create'],
                'chat': ['read', 'create']
            },
            TipoUsuario.SECRETARIO: {
                'processos': ['create', 'read', 'update'],
                'tarefas': ['create', 'read', 'update'],
                'compromissos': ['create', 'read', 'update', 'delete'],
                'chat': ['read', 'create'],
                'relatorios': ['read']
            },
            TipoUsuario.ESTAGIARIO: {
                'processos': ['read'],
                'tarefas': ['read'],
                'compromissos': ['read'],
                'chat': ['read']
            }
        }
        
        user_permissions = default_permissions.get(user.tipo_usuario, {})
        return acao in user_permissions.get(recurso, [])
        
    finally:
        db.close()

def can_edit_delete(user: Usuario) -> bool:
    """Função de compatibilidade - verifica se pode editar/deletar"""
    return user.tipo_usuario in [TipoUsuario.ADMIN, TipoUsuario.ADVOGADO, TipoUsuario.SECRETARIO]

def can_access_reports(user: Usuario) -> bool:
    """Função de compatibilidade - verifica se pode acessar relatórios"""
    return has_permission(user, 'relatorios', 'read')

# === FUNÇÕES AUXILIARES ===

def log_alteracao(db, user_id: int, tabela: str, registro_id: int, acao: str, 
                 dados_anteriores: dict = None, dados_novos: dict = None, 
                 descricao: str = None, processo_id: int = None):
    """Registra alteração no histórico"""
    try:
        historico = HistoricoAlteracoes(
            processo_id=processo_id,
            usuario_id=user_id,
            tabela=tabela,
            registro_id=registro_id,
            acao=acao,
            dados_anteriores=json.dumps(dados_anteriores) if dados_anteriores else None,
            dados_novos=json.dumps(dados_novos) if dados_novos else None,
            descricao=descricao,
            created_at=datetime.now(timezone.utc)
        )
        db.add(historico)
    except Exception as e:
        print(f"Erro ao registrar histórico: {e}")

def criar_notificacao(db, usuario_id: int, titulo: str, conteudo: str, 
                     tipo: TipoNotificacao, link_interno: str = None,
                     processo_id: int = None, tarefa_id: int = None, prazo_id: int = None):
    """Cria uma notificação para o usuário"""
    try:
        notificacao = Notificacao(
            usuario_id=usuario_id,
            titulo=titulo,
            conteudo=conteudo,
            tipo=tipo,
            link_interno=link_interno,
            processo_id=processo_id,
            tarefa_id=tarefa_id,
            prazo_id=prazo_id,
            created_at=datetime.now(timezone.utc)
        )
        db.add(notificacao)
    except Exception as e:
        print(f"Erro ao criar notificação: {e}")

# === ROTAS DE AUTENTICAÇÃO ===

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
    db = SessionLocal()
    try:
        # Buscar usuário no banco
        user = db.query(Usuario).filter(Usuario.username == username).first()
        
        if user and user.ativo:
            # Verificar senha (hash)
            senha_hash = hashlib.sha256(password.encode()).hexdigest()
            if user.senha_hash == senha_hash:
                # Criar sessão
                token = create_session(user)
                response = RedirectResponse("/", status_code=302)
                response.set_cookie(
                    key=SESSION_COOKIE_NAME,
                    value=token,
                    httponly=True,
                    secure=False,  # Para desenvolvimento local
                    samesite="lax"
                )
                return response
        
        # Credenciais inválidas
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Usuário ou senha incorretos"}
        )
    finally:
        db.close()

@app.post("/logout")
def logout(session_token: str = Cookie(None, alias=SESSION_COOKIE_NAME)):
    if session_token:
        invalidate_session(session_token)
    
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return response

# === ROTAS PRINCIPAIS ===

@app.get("/")
def dashboard(request: Request, current_session: dict = Depends(require_auth)):
    """Dashboard principal do sistema"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        # Estatísticas do dashboard
        total_processos = db.query(Processo).count()
        processos_ativos = db.query(Processo).filter(Processo.status == StatusProcesso.ATIVO).count()
        
        # Tarefas pendentes do usuário
        tarefas_pendentes = db.query(Tarefa).filter(
            and_(
                Tarefa.atribuido_para_id == user.id,
                Tarefa.status.in_([StatusTarefa.PENDENTE, StatusTarefa.EM_ANDAMENTO])
            )
        ).limit(5).all()
        
        # Próximos prazos (próximos 7 dias)
        proximos_prazos = db.query(Prazo).filter(
            and_(
                Prazo.data_limite >= datetime.now(timezone.utc),
                Prazo.data_limite <= datetime.now(timezone.utc) + timedelta(days=7),
                Prazo.cumprido == False
            )
        ).order_by(Prazo.data_limite).limit(5).all()
        
        # Próximos compromissos
        proximos_compromissos = db.query(Compromisso).filter(
            and_(
                Compromisso.usuario_id == user.id,
                Compromisso.data_inicio >= datetime.now(timezone.utc)
            )
        ).order_by(Compromisso.data_inicio).limit(5).all()
        
        # Notificações não lidas
        notificacoes = db.query(Notificacao).filter(
            and_(
                Notificacao.usuario_id == user.id,
                Notificacao.lida == False
            )
        ).order_by(desc(Notificacao.created_at)).limit(10).all()
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": user,
            "current_session": current_session,
            "total_processos": total_processos,
            "processos_ativos": processos_ativos,
            "tarefas_pendentes": tarefas_pendentes,
            "proximos_prazos": proximos_prazos,
            "proximos_compromissos": proximos_compromissos,
            "notificacoes": notificacoes,
            "format_sp": format_sp,
            "can_edit_delete": can_edit_delete(user),
            "can_access_reports": can_access_reports(user)
        })
    finally:
        db.close()

# === IMPORTAR ROTAS DOS MÓDULOS ===
# Aqui vamos importar as rotas específicas de cada módulo

# Para agora, vamos manter as rotas antigas para compatibilidade
from app_old_routes import *

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
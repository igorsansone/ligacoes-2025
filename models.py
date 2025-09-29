"""
Modelos de banco de dados para o Sistema de Gerenciamento de Processos Jurídicos
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Float, Enum
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func
from datetime import datetime, timezone
import enum

class Base(DeclarativeBase):
    pass

# Enums para tipos específicos
class TipoProcesso(enum.Enum):
    CIVIL = "civil"
    CRIMINAL = "criminal"
    TRABALHISTA = "trabalhista"
    ADMINISTRATIVO = "administrativo"
    TRIBUTARIO = "tributario"
    EMPRESARIAL = "empresarial"
    FAMILIA = "familia"
    CONSUMIDOR = "consumidor"
    AMBIENTAL = "ambiental"
    PREVIDENCIARIO = "previdenciario"
    OUTROS = "outros"

class StatusProcesso(enum.Enum):
    ATIVO = "ativo"
    ARQUIVADO = "arquivado"
    SUSPENSO = "suspenso"
    ENCERRADO = "encerrado"
    AGUARDANDO = "aguardando"
    EM_RECURSO = "em_recurso"

class PrioridadeProcesso(enum.Enum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    URGENTE = "urgente"

class TipoUsuario(enum.Enum):
    ADMIN = "admin"
    ADVOGADO = "advogado"
    ASSISTENTE = "assistente"
    ESTAGIARIO = "estagiario"
    SECRETARIO = "secretario"
    CLIENTE = "cliente"

class StatusTarefa(enum.Enum):
    PENDENTE = "pendente"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDA = "concluida"
    CANCELADA = "cancelada"
    ATRASADA = "atrasada"

class TipoNotificacao(enum.Enum):
    PRAZO = "prazo"
    COMPROMISSO = "compromisso"
    TAREFA = "tarefa"
    PROCESSO = "processo"
    CHAT = "chat"
    SISTEMA = "sistema"

# === MODELOS PRINCIPAIS ===

class Usuario(Base):
    """Modelo aprimorado para usuários do sistema"""
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    nome_completo = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)  # Para futuras melhorias de segurança
    tipo_usuario = Column(Enum(TipoUsuario), nullable=False, default=TipoUsuario.ASSISTENTE)
    ativo = Column(Boolean, default=True, nullable=False)
    telefone = Column(String(50), nullable=True)
    setor = Column(String(100), nullable=True)
    observacoes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    ultimo_login = Column(DateTime, nullable=True)
    
    # Relacionamentos
    processos_responsavel = relationship("Processo", foreign_keys="Processo.responsavel_id", back_populates="responsavel")
    processos_advogado = relationship("Processo", foreign_keys="Processo.advogado_id", back_populates="advogado")
    tarefas_atribuidas = relationship("Tarefa", foreign_keys="Tarefa.atribuido_para_id", back_populates="atribuido_para")
    compromissos = relationship("Compromisso", back_populates="usuario")
    mensagens_enviadas = relationship("ChatMensagem", foreign_keys="ChatMensagem.remetente_id", back_populates="remetente")
    historico_alteracoes = relationship("HistoricoAlteracoes", back_populates="usuario")

class Processo(Base):
    """Modelo principal para processos jurídicos"""
    __tablename__ = "processos"
    
    id = Column(Integer, primary_key=True, index=True)
    numero_processo = Column(String(100), unique=True, nullable=False, index=True)
    titulo = Column(String(500), nullable=False)
    descricao = Column(Text, nullable=True)
    
    # Classificação
    tipo_processo = Column(Enum(TipoProcesso), nullable=False)
    area = Column(String(100), nullable=False)  # Área específica dentro do tipo
    status = Column(Enum(StatusProcesso), nullable=False, default=StatusProcesso.ATIVO)
    prioridade = Column(Enum(PrioridadeProcesso), nullable=False, default=PrioridadeProcesso.MEDIA)
    
    # Partes do processo
    autor = Column(String(255), nullable=False)
    reu = Column(String(255), nullable=False)
    terceiros = Column(Text, nullable=True)  # JSON ou texto com outros envolvidos
    
    # Valores
    valor_causa = Column(Float, nullable=True)
    valor_condenacao = Column(Float, nullable=True)
    honorarios = Column(Float, nullable=True)
    
    # Responsáveis
    responsavel_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    advogado_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    
    # Instâncias e localização
    comarca = Column(String(100), nullable=True)
    vara = Column(String(100), nullable=True)
    instancia = Column(String(50), nullable=True)  # 1ª, 2ª, STF, STJ, etc.
    
    # Datas importantes
    data_abertura = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    data_encerramento = Column(DateTime, nullable=True)
    ultima_movimentacao = Column(DateTime, nullable=True)
    
    # Observações e notas
    observacoes = Column(Text, nullable=True)
    estrategia = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    responsavel = relationship("Usuario", foreign_keys=[responsavel_id], back_populates="processos_responsavel")
    advogado = relationship("Usuario", foreign_keys=[advogado_id], back_populates="processos_advogado")
    anexos = relationship("Anexo", back_populates="processo", cascade="all, delete-orphan")
    tarefas = relationship("Tarefa", back_populates="processo", cascade="all, delete-orphan")
    prazos = relationship("Prazo", back_populates="processo", cascade="all, delete-orphan")
    historico = relationship("HistoricoAlteracoes", back_populates="processo", cascade="all, delete-orphan")
    chat_canais = relationship("ChatCanal", back_populates="processo", cascade="all, delete-orphan")

class Anexo(Base):
    """Modelo para anexos/documentos dos processos"""
    __tablename__ = "anexos"
    
    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=False)
    
    # Informações do arquivo
    nome_arquivo = Column(String(255), nullable=False)
    nome_original = Column(String(255), nullable=False)
    tipo_documento = Column(String(100), nullable=True)  # Petição, Sentença, Contrato, etc.
    tamanho_arquivo = Column(Integer, nullable=False)  # em bytes
    tipo_mime = Column(String(100), nullable=False)
    caminho_arquivo = Column(String(500), nullable=False)
    
    # Metadados
    descricao = Column(Text, nullable=True)
    publico = Column(Boolean, default=False, nullable=False)  # Se pode ser visto por clientes
    
    # Controle de acesso
    uploaded_by_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Relacionamentos
    processo = relationship("Processo", back_populates="anexos")
    uploaded_by = relationship("Usuario")

class Tarefa(Base):
    """Modelo para tarefas/demandas atribuídas"""
    __tablename__ = "tarefas"
    
    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=True)  # Opcional - tarefa pode não ser de um processo específico
    
    # Conteúdo da tarefa
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    status = Column(Enum(StatusTarefa), nullable=False, default=StatusTarefa.PENDENTE)
    prioridade = Column(Enum(PrioridadeProcesso), nullable=False, default=PrioridadeProcesso.MEDIA)
    
    # Atribuição
    atribuido_para_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    atribuido_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    
    # Prazos
    data_limite = Column(DateTime, nullable=True)
    data_conclusao = Column(DateTime, nullable=True)
    
    # Progresso
    progresso = Column(Integer, default=0, nullable=False)  # 0-100%
    observacoes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    processo = relationship("Processo", back_populates="tarefas")
    atribuido_para = relationship("Usuario", foreign_keys=[atribuido_para_id], back_populates="tarefas_atribuidas")
    atribuido_por = relationship("Usuario", foreign_keys=[atribuido_por_id])

class Prazo(Base):
    """Modelo para prazos vinculados aos processos"""
    __tablename__ = "prazos"
    
    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=False)
    
    # Dados do prazo
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    data_limite = Column(DateTime, nullable=False)
    
    # Controle
    cumprido = Column(Boolean, default=False, nullable=False)
    data_cumprimento = Column(DateTime, nullable=True)
    
    # Notificações
    notificar_antecedencia = Column(Integer, default=2, nullable=False)  # dias de antecedência
    notificado = Column(Boolean, default=False, nullable=False)
    
    # Responsável
    responsavel_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    processo = relationship("Processo", back_populates="prazos")
    responsavel = relationship("Usuario")

class Compromisso(Base):
    """Modelo para compromissos/agenda"""
    __tablename__ = "compromissos"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=True)  # Opcional
    
    # Dados do compromisso
    titulo = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    local = Column(String(255), nullable=True)
    
    # Data e hora
    data_inicio = Column(DateTime, nullable=False)
    data_fim = Column(DateTime, nullable=True)
    dia_inteiro = Column(Boolean, default=False, nullable=False)
    
    # Notificações
    lembrete_antes = Column(Integer, default=30, nullable=False)  # minutos antes
    notificado = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    usuario = relationship("Usuario", back_populates="compromissos")
    processo = relationship("Processo")

class ChatCanal(Base):
    """Modelo para canais de chat por processo ou geral"""
    __tablename__ = "chat_canais"
    
    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=True)  # None = canal geral
    
    # Dados do canal
    nome = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Relacionamentos
    processo = relationship("Processo", back_populates="chat_canais")
    mensagens = relationship("ChatMensagem", back_populates="canal", cascade="all, delete-orphan")

class ChatMensagem(Base):
    """Modelo para mensagens do chat interno"""
    __tablename__ = "chat_mensagens"
    
    id = Column(Integer, primary_key=True, index=True)
    canal_id = Column(Integer, ForeignKey("chat_canais.id"), nullable=False)
    remetente_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    
    # Conteúdo
    conteudo = Column(Text, nullable=False)
    tipo_mensagem = Column(String(50), default="texto", nullable=False)  # texto, arquivo, sistema
    
    # Controle
    editada = Column(Boolean, default=False, nullable=False)
    lida = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relacionamentos
    canal = relationship("ChatCanal", back_populates="mensagens")
    remetente = relationship("Usuario", foreign_keys=[remetente_id], back_populates="mensagens_enviadas")

class Notificacao(Base):
    """Modelo para notificações do sistema"""
    __tablename__ = "notificacoes"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    
    # Conteúdo
    titulo = Column(String(255), nullable=False)
    conteudo = Column(Text, nullable=False)
    tipo = Column(Enum(TipoNotificacao), nullable=False)
    
    # Links e referências
    link_interno = Column(String(255), nullable=True)  # URL interna do sistema
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=True)
    tarefa_id = Column(Integer, ForeignKey("tarefas.id"), nullable=True)
    prazo_id = Column(Integer, ForeignKey("prazos.id"), nullable=True)
    
    # Controle
    lida = Column(Boolean, default=False, nullable=False)
    data_leitura = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Relacionamentos
    usuario = relationship("Usuario")
    processo = relationship("Processo")
    tarefa = relationship("Tarefa")
    prazo = relationship("Prazo")

class HistoricoAlteracoes(Base):
    """Modelo para auditoria e histórico de alterações"""
    __tablename__ = "historico_alteracoes"
    
    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    
    # Dados da alteração
    tabela = Column(String(100), nullable=False)  # Nome da tabela alterada
    registro_id = Column(Integer, nullable=False)  # ID do registro alterado
    acao = Column(String(50), nullable=False)  # CREATE, UPDATE, DELETE
    
    # Conteúdo
    dados_anteriores = Column(Text, nullable=True)  # JSON dos dados antes da alteração
    dados_novos = Column(Text, nullable=True)  # JSON dos dados após a alteração
    descricao = Column(String(500), nullable=True)  # Descrição da alteração
    
    # Metadados
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Relacionamentos
    processo = relationship("Processo", back_populates="historico")
    usuario = relationship("Usuario", back_populates="historico_alteracoes")

class Permissao(Base):
    """Modelo para controle granular de permissões"""
    __tablename__ = "permissoes"
    
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    
    # Permissões específicas
    recurso = Column(String(100), nullable=False)  # processos, usuarios, relatorios, etc.
    acao = Column(String(50), nullable=False)  # create, read, update, delete, export, etc.
    permitido = Column(Boolean, default=True, nullable=False)
    
    # Restrições
    condicoes = Column(Text, nullable=True)  # JSON com condições específicas
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Relacionamentos
    usuario = relationship("Usuario")

# === COMPATIBILIDADE COM SISTEMA EXISTENTE ===

class Ligacao(Base):
    """Manter modelo existente para compatibilidade durante migração"""
    __tablename__ = "ligacoes"
    id = Column(Integer, primary_key=True, index=True)
    cro = Column(String(50), nullable=False)
    nome_inscrito = Column(String(255), nullable=False)
    duvida = Column(String(100), nullable=False)
    observacao = Column(String(1000), nullable=True)
    atendente = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

class ProfissionalApto(Base):
    """Manter modelo existente para compatibilidade durante migração"""
    __tablename__ = "profissionais_aptos"
    id = Column(Integer, primary_key=True, index=True)
    numero_cro = Column(String(50), nullable=False, index=True)
    nome = Column(String(500), nullable=False, index=True)
    categoria = Column(String(200), nullable=True)
    cpf = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)
    outros_emails = Column(String(500), nullable=True)
    celular_atualizado = Column(String(50), nullable=True)
    outros_telefones = Column(String(200), nullable=True)
    situacao = Column(String(200), nullable=True)
    outras_informacoes = Column(String(2000), nullable=True)
    imported_at = Column(DateTime, nullable=False, server_default=func.now())
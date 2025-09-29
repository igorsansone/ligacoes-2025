"""
Rotas básicas para gerenciamento de processos
Demonstração do novo sistema de gerenciamento de processos jurídicos
"""

# === ROTAS DE PROCESSOS ===

@app.get("/processos")
def listar_processos(
    request: Request,
    current_session: dict = Depends(require_auth),
    page: int = Query(1, ge=1),
    search: str = Query("", description="Busca por número ou título do processo")
):
    """Listar processos com paginação e busca"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        # Query base
        query = db.query(Processo)
        
        # Aplicar filtros de busca
        if search:
            query = query.filter(
                or_(
                    Processo.numero_processo.ilike(f"%{search}%"),
                    Processo.titulo.ilike(f"%{search}%"),
                    Processo.autor.ilike(f"%{search}%"),
                    Processo.reu.ilike(f"%{search}%")
                )
            )
        
        # Se não for admin, mostrar apenas processos que o usuário tem acesso
        if user.tipo_usuario != TipoUsuario.ADMIN:
            query = query.filter(
                or_(
                    Processo.responsavel_id == user.id,
                    Processo.advogado_id == user.id
                )
            )
        
        # Paginação
        per_page = 20
        offset = (page - 1) * per_page
        processos = query.order_by(desc(Processo.created_at)).offset(offset).limit(per_page).all()
        total = query.count()
        
        # Informações de paginação
        has_prev = page > 1
        has_next = (page * per_page) < total
        
        return templates.TemplateResponse("processos/listar.html", {
            "request": request,
            "user": user,
            "current_session": current_session,
            "processos": processos,
            "search": search,
            "page": page,
            "has_prev": has_prev,
            "has_next": has_next,
            "total": total,
            "format_sp": format_sp,
            "can_edit_delete": can_edit_delete(user),
            "can_access_reports": can_access_reports(user)
        })
    finally:
        db.close()

@app.get("/processos/novo")
def novo_processo_form(request: Request, current_session: dict = Depends(require_auth)):
    """Formulário para novo processo"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not has_permission(user, 'processos', 'create'):
            raise HTTPException(status_code=403, detail="Sem permissão para criar processos")
        
        # Buscar advogados para o dropdown
        advogados = db.query(Usuario).filter(
            Usuario.tipo_usuario.in_([TipoUsuario.ADVOGADO, TipoUsuario.ADMIN])
        ).all()
        
        return templates.TemplateResponse("processos/novo.html", {
            "request": request,
            "user": user,
            "current_session": current_session,
            "advogados": advogados,
            "tipos_processo": TipoProcesso,
            "prioridades": PrioridadeProcesso,
            "can_edit_delete": can_edit_delete(user),
            "can_access_reports": can_access_reports(user)
        })
    finally:
        db.close()

@app.post("/processos/novo")
def criar_processo(
    request: Request,
    numero_processo: str = Form(...),
    titulo: str = Form(...),
    tipo_processo: str = Form(...),
    area: str = Form(...),
    autor: str = Form(...),
    reu: str = Form(...),
    advogado_id: Optional[int] = Form(None),
    prioridade: str = Form("media"),
    descricao: str = Form(""),
    observacoes: str = Form(""),
    valor_causa: Optional[float] = Form(None),
    comarca: str = Form(""),
    vara: str = Form(""),
    instancia: str = Form(""),
    current_session: dict = Depends(require_auth)
):
    """Criar novo processo"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not has_permission(user, 'processos', 'create'):
            raise HTTPException(status_code=403, detail="Sem permissão para criar processos")
        
        # Verificar se número do processo já existe
        existing = db.query(Processo).filter(Processo.numero_processo == numero_processo.strip()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Número do processo já existe")
        
        # Criar novo processo
        processo = Processo(
            numero_processo=numero_processo.strip(),
            titulo=titulo.strip(),
            tipo_processo=TipoProcesso(tipo_processo),
            area=area.strip(),
            autor=autor.strip(),
            reu=reu.strip(),
            responsavel_id=user.id,
            advogado_id=advogado_id,
            prioridade=PrioridadeProcesso(prioridade),
            descricao=descricao.strip() if descricao else None,
            observacoes=observacoes.strip() if observacoes else None,
            valor_causa=valor_causa,
            comarca=comarca.strip() if comarca else None,
            vara=vara.strip() if vara else None,
            instancia=instancia.strip() if instancia else None,
            data_abertura=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(processo)
        db.flush()  # Para obter o ID
        
        # Registrar no histórico
        log_alteracao(
            db, user.id, 'processos', processo.id, 'CREATE',
            dados_novos={
                'numero_processo': numero_processo,
                'titulo': titulo,
                'tipo_processo': tipo_processo,
                'autor': autor,
                'reu': reu
            },
            descricao="Processo criado",
            processo_id=processo.id
        )
        
        # Criar notificação para o advogado responsável (se diferente do criador)
        if advogado_id and advogado_id != user.id:
            criar_notificacao(
                db, advogado_id, 
                "Novo processo atribuído",
                f"O processo {numero_processo} foi atribuído a você.",
                TipoNotificacao.PROCESSO,
                f"/processos/{processo.id}",
                processo_id=processo.id
            )
        
        db.commit()
        
        return RedirectResponse(f"/processos/{processo.id}", status_code=303)
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao criar processo: {str(e)}")
    finally:
        db.close()

@app.get("/processos/{processo_id}")
def visualizar_processo(
    request: Request,
    processo_id: int,
    current_session: dict = Depends(require_auth)
):
    """Visualizar detalhes do processo"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        # Buscar processo
        processo = db.query(Processo).filter(Processo.id == processo_id).first()
        if not processo:
            raise HTTPException(status_code=404, detail="Processo não encontrado")
        
        # Verificar permissão de acesso
        if (user.tipo_usuario != TipoUsuario.ADMIN and 
            processo.responsavel_id != user.id and 
            processo.advogado_id != user.id):
            raise HTTPException(status_code=403, detail="Sem permissão para acessar este processo")
        
        # Buscar dados relacionados
        tarefas = db.query(Tarefa).filter(Tarefa.processo_id == processo_id).order_by(desc(Tarefa.created_at)).all()
        prazos = db.query(Prazo).filter(Prazo.processo_id == processo_id).order_by(Prazo.data_limite).all()
        anexos = db.query(Anexo).filter(Anexo.processo_id == processo_id).order_by(desc(Anexo.created_at)).all()
        historico = db.query(HistoricoAlteracoes).filter(HistoricoAlteracoes.processo_id == processo_id).order_by(desc(HistoricoAlteracoes.created_at)).limit(20).all()
        
        return templates.TemplateResponse("processos/visualizar.html", {
            "request": request,
            "user": user,
            "current_session": current_session,
            "processo": processo,
            "tarefas": tarefas,
            "prazos": prazos,
            "anexos": anexos,
            "historico": historico,
            "format_sp": format_sp,
            "can_edit_delete": can_edit_delete(user),
            "can_access_reports": can_access_reports(user)
        })
    finally:
        db.close()

# === ROTAS DE TAREFAS ===

@app.get("/tarefas")
def listar_tarefas(
    request: Request,
    current_session: dict = Depends(require_auth),
    status_filter: Optional[str] = Query(None)
):
    """Listar tarefas do usuário"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        # Query base - tarefas atribuídas ao usuário
        query = db.query(Tarefa).filter(Tarefa.atribuido_para_id == user.id)
        
        # Aplicar filtro de status se fornecido
        if status_filter:
            try:
                status_enum = StatusTarefa(status_filter)
                query = query.filter(Tarefa.status == status_enum)
            except ValueError:
                pass  # Ignorar filtro inválido
        
        tarefas = query.order_by(
            desc(Tarefa.prioridade == PrioridadeProcesso.URGENTE),
            desc(Tarefa.prioridade == PrioridadeProcesso.ALTA),
            asc(Tarefa.data_limite),
            desc(Tarefa.created_at)
        ).all()
        
        return templates.TemplateResponse("tarefas/listar.html", {
            "request": request,
            "user": user,
            "current_session": current_session,
            "tarefas": tarefas,
            "status_filter": status_filter,
            "status_opcoes": StatusTarefa,
            "format_sp": format_sp,
            "can_edit_delete": can_edit_delete(user),
            "can_access_reports": can_access_reports(user)
        })
    finally:
        db.close()

@app.get("/tarefas/nova")
def nova_tarefa_form(request: Request, current_session: dict = Depends(require_auth)):
    """Formulário para nova tarefa"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        # Buscar processos para o dropdown
        processos = db.query(Processo).filter(
            Processo.status == StatusProcesso.ATIVO
        ).order_by(Processo.numero_processo).all()
        
        # Buscar usuários para atribuição
        usuarios = db.query(Usuario).filter(Usuario.ativo == True).order_by(Usuario.nome_completo).all()
        
        return templates.TemplateResponse("tarefas/nova.html", {
            "request": request,
            "user": user,
            "current_session": current_session,
            "processos": processos,
            "usuarios": usuarios,
            "prioridades": PrioridadeProcesso,
            "can_edit_delete": can_edit_delete(user),
            "can_access_reports": can_access_reports(user)
        })
    finally:
        db.close()

# === ROTA PARA DEMONSTRAÇÃO ===

@app.get("/demo/criar-dados")
def criar_dados_demonstracao(current_session: dict = Depends(require_auth)):
    """Criar dados de demonstração para o sistema"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if user.tipo_usuario != TipoUsuario.ADMIN:
            raise HTTPException(status_code=403, detail="Apenas administradores podem criar dados de demonstração")
        
        # Verificar se já existem processos
        if db.query(Processo).count() > 0:
            return {"message": "Dados de demonstração já existem"}
        
        # Criar alguns processos de exemplo
        processos_exemplo = [
            {
                "numero_processo": "0001234-56.2024.8.21.0001",
                "titulo": "Ação de Cobrança - Débitos em Aberto",
                "tipo_processo": TipoProcesso.CIVIL,
                "area": "Cobrança",
                "autor": "CRO/RS",
                "reu": "João Silva Santos",
                "descricao": "Cobrança de anuidades em atraso referentes aos anos de 2022 e 2023",
                "valor_causa": 5500.00,
                "comarca": "Porto Alegre",
                "vara": "2ª Vara Cível",
                "prioridade": PrioridadeProcesso.MEDIA
            },
            {
                "numero_processo": "0002345-67.2024.8.21.0002",
                "titulo": "Processo Administrativo - Apuração de Denúncia",
                "tipo_processo": TipoProcesso.ADMINISTRATIVO,
                "area": "Fiscalização",
                "autor": "CRO/RS",
                "reu": "Dra. Maria Fernanda Oliveira",
                "descricao": "Apuração de denúncia sobre exercício irregular da profissão",
                "comarca": "Caxias do Sul",
                "prioridade": PrioridadeProcesso.ALTA
            },
            {
                "numero_processo": "0003456-78.2024.8.21.0003",
                "titulo": "Recurso - Questionamento de Multa",
                "tipo_processo": TipoProcesso.ADMINISTRATIVO,
                "area": "Recursos",
                "autor": "Dr. Carlos Eduardo Pereira",
                "reu": "CRO/RS",
                "descricao": "Recurso contra aplicação de multa por descumprimento de normas",
                "valor_causa": 2000.00,
                "comarca": "Santa Maria",
                "vara": "Vara da Fazenda Pública",
                "prioridade": PrioridadeProcesso.BAIXA
            }
        ]
        
        processos_criados = []
        for proc_data in processos_exemplo:
            processo = Processo(
                numero_processo=proc_data["numero_processo"],
                titulo=proc_data["titulo"],
                tipo_processo=proc_data["tipo_processo"],
                area=proc_data["area"],
                autor=proc_data["autor"],
                reu=proc_data["reu"],
                responsavel_id=user.id,
                advogado_id=user.id,
                prioridade=proc_data["prioridade"],
                descricao=proc_data["descricao"],
                valor_causa=proc_data.get("valor_causa"),
                comarca=proc_data.get("comarca"),
                vara=proc_data.get("vara"),
                data_abertura=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc)
            )
            db.add(processo)
            db.flush()
            processos_criados.append(processo)
        
        # Criar algumas tarefas
        for i, processo in enumerate(processos_criados):
            tarefa = Tarefa(
                processo_id=processo.id,
                titulo=f"Análise inicial - {processo.titulo[:30]}...",
                descricao="Revisar documentação inicial e definir estratégia",
                atribuido_para_id=user.id,
                atribuido_por_id=user.id,
                prioridade=processo.prioridade,
                data_limite=datetime.now(timezone.utc) + timedelta(days=7),
                created_at=datetime.now(timezone.utc)
            )
            db.add(tarefa)
        
        # Criar alguns prazos
        for processo in processos_criados:
            prazo = Prazo(
                processo_id=processo.id,
                titulo="Prazo para contestação",
                descricao="Prazo legal para apresentar contestação",
                data_limite=datetime.now(timezone.utc) + timedelta(days=15),
                responsavel_id=user.id,
                notificar_antecedencia=3,
                created_at=datetime.now(timezone.utc)
            )
            db.add(prazo)
        
        # Criar algumas notificações
        criar_notificacao(
            db, user.id,
            "Bem-vindo ao Sistema de Processos!",
            "O sistema foi configurado com dados de demonstração. Explore as funcionalidades disponíveis.",
            TipoNotificacao.SISTEMA,
            "/processos"
        )
        
        db.commit()
        
        return {
            "message": "Dados de demonstração criados com sucesso!",
            "processos_criados": len(processos_criados),
            "tarefas_criadas": len(processos_criados),
            "prazos_criados": len(processos_criados)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao criar dados: {str(e)}")
    finally:
        db.close()
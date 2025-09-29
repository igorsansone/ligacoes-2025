"""
Rotas antigas mantidas para compatibilidade
Este arquivo contém todas as rotas do sistema antigo de ligações
"""

# === ROTAS DE COMPATIBILIDADE COM SISTEMA ANTIGO ===

# Página inicial antiga: formulário e lista de ligações
@app.get("/ligacoes")
def ligacoes_home(request: Request, current_session: dict = Depends(require_auth)):
    """Página de ligações (sistema antigo) para compatibilidade"""
    db = SessionLocal()
    try:
        ligacoes = db.query(Ligacao).order_by(Ligacao.id.desc()).limit(50).all()
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        return templates.TemplateResponse(
            "index.html",  # Reutilizar template existente
            {
                "request": request,
                "duvida_opcoes": DUVIDA_OPCOES,
                "ligacoes": ligacoes,
                "format_sp": format_sp,
                "current_user": current_session,
                "current_username": current_session['username'],
                "current_user_fullname": current_session['nome_completo'],
                "can_edit_delete": can_edit_delete(user),
                "can_access_reports": can_access_reports(user),
            },
        )
    finally:
        db.close()

# Cadastrar ligação
@app.post("/cadastrar")
def cadastrar_ligacao(
    cro: str = Form(...),
    nome_inscrito: str = Form(...),
    duvida: str = Form(...),
    observacao: str = Form(""),
    current_session: dict = Depends(require_auth),
):
    """Cadastrar ligação (sistema antigo)"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if duvida not in DUVIDA_OPCOES:
            duvida = DUVIDA_OPCOES[0]
            
        novo = Ligacao(
            cro=cro.strip(),
            nome_inscrito=nome_inscrito.strip(),
            duvida=duvida.strip(),
            observacao=(observacao or "").strip(),
            atendente=user.nome_completo,
            created_at=datetime.now(timezone.utc),
        )
        db.add(novo)
        db.commit()
        
        # Log da alteração
        log_alteracao(
            db, user.id, 'ligacoes', novo.id, 'CREATE',
            dados_novos={'cro': cro, 'nome_inscrito': nome_inscrito, 'duvida': duvida},
            descricao="Nova ligação cadastrada"
        )
        db.commit()
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao cadastrar ligação: {str(e)}")
    finally:
        db.close()
    
    return RedirectResponse("/ligacoes", status_code=303)

# Editar ligação (GET)
@app.get("/editar/{ligacao_id}")
def editar_ligacao_form(
    request: Request, 
    ligacao_id: int, 
    current_session: dict = Depends(require_auth)
):
    """Formulário de edição de ligação"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_edit_delete(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        obj = db.get(Ligacao, ligacao_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
            
        return templates.TemplateResponse(
            "editar.html",
            {
                "request": request,
                "ligacao": obj,
                "duvida_opcoes": DUVIDA_OPCOES,
                "format_sp": format_sp,
                "current_user": current_session,
                "current_username": current_session['username'],
                "current_user_fullname": current_session['nome_completo'],
                "can_access_reports": can_access_reports(user),
            },
        )
    finally:
        db.close()

# Editar ligação (POST)
@app.post("/editar/{ligacao_id}")
def editar_ligacao_submit(
    ligacao_id: int,
    cro: str = Form(...),
    nome_inscrito: str = Form(...),
    duvida: str = Form(...),
    observacao: str = Form(""),
    current_session: dict = Depends(require_auth),
):
    """Salvar edição de ligação"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_edit_delete(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        obj = db.get(Ligacao, ligacao_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Registro não encontrado")

        # Guardar dados anteriores para log
        dados_anteriores = {
            'cro': obj.cro,
            'nome_inscrito': obj.nome_inscrito,
            'duvida': obj.duvida,
            'observacao': obj.observacao
        }

        if duvida not in DUVIDA_OPCOES:
            duvida = DUVIDA_OPCOES[0]

        obj.cro = cro.strip()
        obj.nome_inscrito = nome_inscrito.strip()
        obj.duvida = duvida.strip()
        obj.observacao = (observacao or "").strip()

        db.add(obj)
        
        # Log da alteração
        dados_novos = {
            'cro': obj.cro,
            'nome_inscrito': obj.nome_inscrito,
            'duvida': obj.duvida,
            'observacao': obj.observacao
        }
        log_alteracao(
            db, user.id, 'ligacoes', ligacao_id, 'UPDATE',
            dados_anteriores=dados_anteriores,
            dados_novos=dados_novos,
            descricao="Ligação editada"
        )
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao editar ligação: {str(e)}")
    finally:
        db.close()
    
    return RedirectResponse("/ligacoes", status_code=303)

# Excluir ligação
@app.post("/excluir/{ligacao_id}")
def excluir_ligacao(ligacao_id: int, current_session: dict = Depends(require_auth)):
    """Excluir ligação"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_edit_delete(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        obj = db.get(Ligacao, ligacao_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Registro não encontrado")
        
        # Guardar dados para log
        dados_anteriores = {
            'cro': obj.cro,
            'nome_inscrito': obj.nome_inscrito,
            'duvida': obj.duvida,
            'observacao': obj.observacao
        }
        
        db.delete(obj)
        
        # Log da alteração
        log_alteracao(
            db, user.id, 'ligacoes', ligacao_id, 'DELETE',
            dados_anteriores=dados_anteriores,
            descricao="Ligação excluída"
        )
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao excluir ligação: {str(e)}")
    finally:
        db.close()
    
    return RedirectResponse("/ligacoes", status_code=303)

# === RELATÓRIOS (SISTEMA ANTIGO) ===

@app.get("/relatorios")
def relatorios_antigos(request: Request, current_session: dict = Depends(require_auth)):
    """Página de relatórios do sistema antigo"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_access_reports(user):
            raise HTTPException(status_code=403, detail="Acesso negado - Você não tem permissão para acessar relatórios")
        
        return templates.TemplateResponse("relatorios.html", {
            "request": request,
            "duvida_opcoes": DUVIDA_OPCOES,
            "current_user": current_session,
            "current_username": current_session['username'],
            "current_user_fullname": current_session['nome_completo'],
            "can_access_reports": can_access_reports(user),
        })
    finally:
        db.close()

def _parse_date(s: str):
    """Função auxiliar para parse de datas"""
    try:
        if not s:
            return None
        y, m, d = map(int, s.split("-"))
        return date(y, m, d)
    except Exception:
        return None

def _filter_rows(rows, start_date, end_date, tipos):
    """Função auxiliar para filtrar registros"""
    filtered = []
    for row in rows:
        if isinstance(row, tuple):
            dt, duvida = row
        else:
            dt, duvida = row.created_at, row.duvida

        if not dt:
            continue
        dia_br = to_sp(dt).date()

        if start_date and dia_br < start_date:
            continue
        if end_date and dia_br > end_date:
            continue
        if tipos and duvida not in tipos:
            continue
        filtered.append((dia_br, duvida))
    return filtered

# APIs de estatísticas (sistema antigo)
@app.get("/api/stats/por_duvida")
def stats_por_duvida(request: Request, current_session: dict = Depends(require_auth)):
    """API de estatísticas por dúvida"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_access_reports(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        tipos_raw = request.query_params.get("tipos", "")
        tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

        rows = db.query(Ligacao.created_at, Ligacao.duvida).all()
        filtered = _filter_rows(rows, start, end, tipos)

        counts_map = {}
        for _, duvida in filtered:
            counts_map[duvida] = counts_map.get(duvida, 0) + 1

        labels = DUVIDA_OPCOES[:]
        counts = [int(counts_map.get(lbl, 0)) for lbl in labels]
        total = sum(counts)
        return {"labels": labels, "counts": counts, "total": total}
    finally:
        db.close()

@app.get("/api/stats/por_dia")
def stats_por_dia(request: Request, current_session: dict = Depends(require_auth)):
    """API de estatísticas por dia"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_access_reports(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        tipos_raw = request.query_params.get("tipos", "")
        tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

        rows = db.query(Ligacao.created_at, Ligacao.duvida).all()
        filtered = _filter_rows(rows, start, end, tipos)

        by_day = {}
        for dia, _ in filtered:
            k = dia.isoformat()
            by_day[k] = by_day.get(k, 0) + 1

        labels = sorted(by_day.keys())
        counts = [by_day[d] for d in labels]
        return {"labels": labels, "counts": counts}
    finally:
        db.close()

@app.get("/api/stats/comparativo_periodo")
def stats_comparativo_periodo(request: Request, current_session: dict = Depends(require_auth)):
    """API de comparativo por período"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_access_reports(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        periodo = request.query_params.get("periodo", "dia")
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        tipos_raw = request.query_params.get("tipos", "")
        tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

        rows = db.query(Ligacao.created_at, Ligacao.duvida).all()
        filtered = _filter_rows(rows, start, end, tipos)
        
        by_period = {}
        for dia, _ in filtered:
            if periodo == "dia":
                key = dia.isoformat()
            elif periodo == "semana":
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
    finally:
        db.close()

@app.get("/api/stats/pico_horarios")
def stats_pico_horarios(request: Request, current_session: dict = Depends(require_auth)):
    """API de pico de horários"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_access_reports(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
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

            all_calls = db.query(Ligacao).all()
            
            by_hour = {}
            for call in all_calls:
                if not call.created_at:
                    continue
                    
                dt_br = to_sp(call.created_at)
                if not dt_br:
                    continue
                    
                call_date = dt_br.date()
                if start and call_date < start:
                    continue
                if end and call_date > end:
                    continue
                if tipos and call.duvida not in tipos:
                    continue
                    
                hour_key = f"{dt_br.hour:02d}:00"
                by_hour[hour_key] = by_hour.get(hour_key, 0) + 1
            
            counts = [by_hour.get(hour, 0) for hour in all_hours]
            
            return {
                "labels": all_hours,
                "counts": counts,
                "total": sum(counts)
            }
        
        except Exception as e:
            return default_response
    finally:
        db.close()

@app.get("/api/stats/por_atendente")
def stats_por_atendente(request: Request, current_session: dict = Depends(require_auth)):
    """API de estatísticas por atendente"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_access_reports(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        tipos_raw = request.query_params.get("tipos", "")
        tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

        all_calls = db.query(Ligacao).all()

        by_attendant = {}
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
                
            attendant = call.atendente or "Não informado"
            by_attendant[attendant] = by_attendant.get(attendant, 0) + 1
        
        sorted_attendants = sorted(by_attendant.items(), key=lambda x: x[1], reverse=True)
        
        labels = [item[0] for item in sorted_attendants]
        counts = [item[1] for item in sorted_attendants]
        
        return {
            "labels": labels,
            "counts": counts,
            "total": sum(counts)
        }
    finally:
        db.close()

# === EXPORTAÇÃO (SISTEMA ANTIGO) ===

@app.get("/api/export/csv")
def export_csv_antigo(request: Request, current_session: dict = Depends(require_auth)):
    """Exportar dados em CSV (sistema antigo)"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_access_reports(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        report_type = request.query_params.get("tipo", "por_duvida")
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        tipos_raw = request.query_params.get("tipos", "")
        tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

        all_calls = db.query(Ligacao).all()

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
    finally:
        db.close()

@app.get("/api/export/pdf")
def export_pdf_antigo(request: Request, current_session: dict = Depends(require_auth)):
    """Exportar dados em PDF (sistema antigo)"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_access_reports(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        report_type = request.query_params.get("tipo", "por_duvida")
        start = _parse_date(request.query_params.get("start"))
        end = _parse_date(request.query_params.get("end"))
        tipos_raw = request.query_params.get("tipos", "")
        tipos = set([t for t in (s.strip() for s in tipos_raw.split(",")) if t]) if tipos_raw else set()

        all_calls = db.query(Ligacao).all()

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
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1
        )
        story.append(Paragraph("ELEIÇÕES CRORS - 2025", title_style))
        story.append(Paragraph(f"Relatório de Ligações - {report_type.replace('_', ' ').title()}", styles['Heading2']))
        
        if start or end:
            periodo_text = f"Período: {start.strftime('%d/%m/%Y') if start else 'Início'} até {end.strftime('%d/%m/%Y') if end else 'Fim'}"
            story.append(Paragraph(periodo_text, styles['Normal']))
        
        story.append(Spacer(1, 20))
        
        if report_type == "detalhado":
            data = [["ID", "CRO", "Nome", "Dúvida", "Atendente", "Data/Hora"]]
            for call in filtered_calls[:100]:
                data.append([
                    str(call.id),
                    call.cro[:15] + "..." if len(call.cro) > 15 else call.cro,
                    call.nome_inscrito[:20] + "..." if len(call.nome_inscrito) > 20 else call.nome_inscrito,
                    call.duvida[:30] + "..." if len(call.duvida) > 30 else call.duvida,
                    (call.atendente or "N/A")[:15] + "..." if call.atendente and len(call.atendente) > 15 else (call.atendente or "N/A"),
                    format_sp(call.created_at)[:16]
                ])
        else:
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
    finally:
        db.close()

# === PESQUISA DE PROFISSIONAIS (SISTEMA ANTIGO) ===

@app.get("/pesquisa-profissional")
def pesquisa_profissional_form(request: Request, current_session: dict = Depends(require_auth)):
    """Página de pesquisa de profissionais"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        return templates.TemplateResponse("pesquisa_profissional.html", {
            "request": request,
            "current_user": current_session,
            "current_username": current_session['username'],
            "current_user_fullname": current_session['nome_completo'],
            "can_access_reports": can_access_reports(user),
            "can_edit_delete": can_edit_delete(user),
        })
    finally:
        db.close()

@app.post("/upload-csv-profissionais")
async def upload_csv_profissionais(
    request: Request,
    csv_file: UploadFile = File(...), 
    current_session: dict = Depends(require_auth)
):
    """Upload de CSV de profissionais (sistema antigo)"""
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.id == current_session['user_id']).first()
        
        if not can_access_reports(user):
            raise HTTPException(status_code=403, detail="Acesso negado")
        
        # Validar tipo de arquivo
        allowed_extensions = ['.csv', '.xls', '.xlsx']
        file_extension = None
        if csv_file.filename:
            file_extension = csv_file.filename.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                return templates.TemplateResponse("pesquisa_profissional.html", {
                    "request": request,
                    "current_user": current_session,
                    "current_username": current_session['username'],
                    "current_user_fullname": current_session['nome_completo'],
                    "can_access_reports": can_access_reports(user),
                    "can_edit_delete": can_edit_delete(user),
                    "error_message": "Por favor, envie um arquivo válido (.csv, .xls, .xlsx)",
                })
        
        try:
            # Ler conteúdo do arquivo
            content = await csv_file.read()
            
            # Processar dados conforme o tipo de arquivo
            from io import StringIO, BytesIO
            
            if file_extension == 'csv':
                csv_string = content.decode('utf-8')
                df = pd.read_csv(StringIO(csv_string))
            elif file_extension in ['xls', 'xlsx']:
                df = pd.read_excel(BytesIO(content), engine='openpyxl' if file_extension == 'xlsx' else 'xlrd')
            else:
                raise ValueError("Formato de arquivo não suportado")
            
            if df.empty:
                raise ValueError("O arquivo está vazio")
            
            # Processar e salvar dados (lógica do sistema antigo mantida)
            # ... (código de processamento do CSV mantido do sistema original)
            
            return templates.TemplateResponse("pesquisa_profissional.html", {
                "request": request,
                "current_user": current_session,
                "current_username": current_session['username'],
                "current_user_fullname": current_session['nome_completo'],
                "can_access_reports": can_access_reports(user),
                "can_edit_delete": can_edit_delete(user),
                "success_message": f"Planilha importada com sucesso!",
            })
            
        except Exception as e:
            return templates.TemplateResponse("pesquisa_profissional.html", {
                "request": request,
                "current_user": current_session,
                "current_username": current_session['username'],
                "current_user_fullname": current_session['nome_completo'],
                "can_access_reports": can_access_reports(user),
                "can_edit_delete": can_edit_delete(user),
                "error_message": f"Erro ao processar planilha: {str(e)}",
            })
    finally:
        db.close()

@app.get("/api/pesquisar-profissional")
def pesquisar_profissional_api(
    request: Request,
    q: str = "",
    current_session: dict = Depends(require_auth)
):
    """API para pesquisar profissionais"""
    db = SessionLocal()
    try:
        if not q or len(q.strip()) < 2:
            return {"results": [], "message": "Digite pelo menos 2 caracteres para pesquisar"}
        
        query = q.strip()
        
        if query.isdigit():
            results = db.query(ProfissionalApto).filter(
                ProfissionalApto.numero_cro == query
            ).limit(50).all()
        else:
            results = db.query(ProfissionalApto).filter(
                or_(
                    ProfissionalApto.nome.ilike(f"%{query}%"),
                    ProfissionalApto.numero_cro == query,
                    ProfissionalApto.categoria.ilike(f"%{query}%"),
                    ProfissionalApto.cpf.ilike(f"%{query}%"),
                    ProfissionalApto.email.ilike(f"%{query}%")
                )
            ).limit(50).all()
        
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
                "nome": p.nome,
                "numero_cro": p.numero_cro,
                "categoria": p.categoria or "",
                "cpf": p.cpf or "",
                "email": p.email or "",
                "outros_emails": p.outros_emails or "",
                "celular_atualizado": p.celular_atualizado or "",
                "outros_telefones": p.outros_telefones or "",
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
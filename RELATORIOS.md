# Sistema de Relatórios Avançado - ELEIÇÕES CRORS 2025

Este documento detalha o sistema completo de relatórios implementado para análise das ligações recebidas.

## Visão Geral

O sistema oferece múltiplos tipos de relatórios com visualizações interativas, filtros avançados e opções de exportação em CSV e PDF.

## Tipos de Relatórios Disponíveis

### 1. Distribuição por Tipo de Dúvida
- **Descrição**: Mostra a distribuição dos diferentes tipos de dúvidas registradas
- **Visualização**: Gráficos de barra ou pizza (alternáveis)
- **Utilidade**: Identificar os tipos de dúvidas mais frequentes

### 2. Ligações por Dia
- **Descrição**: Evolução temporal das ligações dia a dia
- **Visualização**: Gráfico de linha com recursos avançados
- **Recursos especiais**:
  - Média móvel de 7 dias
  - Zoom interativo (arraste para selecionar período)
  - Navegação com mouse wheel
  - Pan com Alt + arraste

### 3. Comparativo por Período *(NOVO)*
- **Descrição**: Agregação de dados por diferentes períodos
- **Opções de agrupamento**:
  - Por dia (padrão)
  - Por semana (formato ISO: YYYY-Www)
  - Por mês (YYYY-MM)
  - Por ano (YYYY)
- **Visualização**: Gráfico de barras
- **Utilidade**: Comparar volumes entre diferentes períodos

### 4. Pico de Horários *(NOVO)*
- **Descrição**: Análise do volume de ligações por hora do dia
- **Cobertura**: 24 horas (00:00 às 23:00)
- **Visualização**: Gráfico de barras
- **Informações adicionais**: 
  - Total de ligações
  - Identificação do horário de pico
  - Número de ligações no pico
- **Utilidade**: Planejamento de equipes e recursos

### 5. Ligações por Atendente *(NOVO)*
- **Descrição**: Performance individual dos atendentes
- **Dados**: Total de ligações atendidas por pessoa
- **Visualização**: Gráficos de barra ou pizza (alternáveis)
- **Ordenação**: Decrescente por número de ligações
- **Utilidade**: Acompanhamento de produtividade e distribuição de trabalho

## Sistema de Filtros

### Filtros Disponíveis

#### 1. Período
- **Campo Início**: Data inicial para análise
- **Campo Fim**: Data final para análise
- **Formato**: DD/MM/AAAA via seletor de data
- **Comportamento**: Se não informado, considera todos os registros

#### 2. Tipo de Dúvida
- **Seletor múltiplo**: Permite selecionar vários tipos simultaneamente
- **Controle**: Ctrl/Cmd + clique para múltipla seleção
- **Comportamento**: Se nenhum selecionado, considera todos os tipos

### Como Aplicar Filtros

1. Configure os filtros desejados nos campos superiores
2. Clique em **"Aplicar"** para atualizar todos os relatórios
3. Use **"Limpar"** para remover todos os filtros
4. Os filtros se aplicam a todos os relatórios simultaneamente

## Exportação de Dados

### Formatos Disponíveis

#### CSV (Comma-Separated Values)
Formato universal para planilhas e análises.

**CSV Resumo**:
- Dados agregados por tipo de dúvida
- Colunas: Tipo de Dúvida, Quantidade
- Exemplo de uso: Gráficos em Excel, análises estatísticas

**CSV Completo**:
- Listagem detalhada de todas as ligações filtradas
- Colunas: ID, CRO, Nome Inscrito, Dúvida, Observação, Atendente, Data/Hora
- Exemplo de uso: Análises detalhadas, auditoria, backup

#### PDF (Portable Document Format)
Formato profissional para apresentações e arquivo.

**PDF Resumo**:
- Relatório formatado com dados agregados
- Inclui percentuais e totais
- Cabeçalho institucional
- Informações de geração

**PDF Completo**:
- Listagem completa com formatação profissional
- **Limitação**: Máximo 100 registros (otimização)
- Tabela formatada com cabeçalhos
- Metadados de geração

### Nomenclatura de Arquivos

Os arquivos exportados seguem o padrão:
- `relatorio_[tipo]_YYYYMMDD_HHMM.[extensão]`
- Exemplo: `relatorio_por_duvida_20250925_1430.csv`

### Como Exportar

1. Configure os filtros desejados (se aplicável)
2. Na seção **"Exportar Relatórios"**, escolha:
   - **Formato**: CSV ou PDF
   - **Tipo**: Resumido ou Detalhado
3. Clique no botão correspondente
4. O arquivo será baixado automaticamente

## Interatividade e Navegação

### Controles dos Gráficos

#### Alternância de Visualização
- Botões **"Barra"** e **"Pizza"** alternam o tipo de gráfico
- Disponível para: Distribuição por Dúvida e Ligações por Atendente

#### Download de Gráficos
- Botão **"Baixar PNG"** em cada relatório
- Salva o gráfico atual como imagem
- Útil para apresentações e documentação

#### Controles Especiais

**Gráfico "Ligações por Dia"**:
- Checkbox "Média móvel 7d": Adiciona linha de tendência
- Botão "Reset Zoom": Restaura visualização completa
- Zoom: Arraste para selecionar período
- Pan: Alt + arraste para navegar

**Gráfico "Comparativo por Período"**:
- Dropdown de período: Altera agrupamento em tempo real
- Atualização automática ao mudar seleção

## APIs para Integração

### Endpoints Disponíveis

Todas as APIs requerem autenticação e permissão de acesso a relatórios.

#### Estatísticas
```
GET /api/stats/por_duvida
GET /api/stats/por_dia
GET /api/stats/comparativo_periodo
GET /api/stats/pico_horarios
GET /api/stats/por_atendente
```

#### Exportação
```
GET /api/export/csv
GET /api/export/pdf
```

### Parâmetros de Consulta

#### Filtros Comuns
- `start`: Data inicial (YYYY-MM-DD)
- `end`: Data final (YYYY-MM-DD)
- `tipos`: Lista de tipos separados por vírgula

#### Específicos

**Comparativo por Período**:
- `periodo`: "dia", "semana", "mes", "ano"

**Exportação**:
- `tipo`: "por_duvida", "detalhado"

### Exemplos de Uso

```bash
# Estatísticas do último mês
curl "/api/stats/por_duvida?start=2025-08-25&end=2025-09-25"

# Comparativo mensal
curl "/api/stats/comparativo_periodo?periodo=mes&start=2025-01-01&end=2025-12-31"

# Exportar CSV detalhado de um período
curl "/api/export/csv?tipo=detalhado&start=2025-09-01&end=2025-09-30"
```

## Casos de Uso Práticos

### 1. Gestão Operacional
- **Pico de Horários**: Dimensionar equipe nos horários de maior demanda
- **Por Atendente**: Monitorar produtividade e distribuição de carga
- **Por Dia**: Identificar tendências e sazonalidade

### 2. Análise Estratégica
- **Comparativo por Período**: Avaliar crescimento/redução de demanda
- **Por Tipo de Dúvida**: Focar treinamento nos tipos mais frequentes
- **Exportação**: Criar apresentações para direção

### 3. Auditoria e Compliance
- **CSV Detalhado**: Backup completo dos dados
- **PDF Completo**: Documentação formal
- **Filtros por período**: Análises específicas para auditorias

### 4. Planejamento
- **Média móvel**: Suavizar variações e identificar tendências
- **Comparativo anual**: Planejamento de recursos para próximo período
- **Análise horária**: Otimizar escalas de trabalho

## Requisitos de Permissão

### Acesso aos Relatórios
- Função `can_access_reports()` determina o acesso
- Usuários sem permissão não veem o menu "Relatórios"
- APIs retornam erro 403 para usuários sem permissão

### Níveis de Acesso
- **Visualização**: Todos os relatórios e gráficos
- **Exportação**: CSV e PDF com dados completos
- **APIs**: Acesso programático aos mesmos dados

## Suporte e Manutenção

### Monitoramento
- Logs de acesso às APIs
- Controle de sessão e autenticação
- Validação de parâmetros de entrada

### Performance
- Consultas otimizadas com índices
- Limitação de registros em PDFs (100)
- Cache de sessão para autenticação

### Troubleshooting

**Gráficos não carregam**:
- Verifique conectividade com CDN do Chart.js
- Console do navegador mostra erros de JavaScript

**Exportação falha**:
- Verificar permissões de usuário
- Validar filtros aplicados
- Logs do servidor para erros específicos

**Performance lenta**:
- Reduzir período de análise
- Usar filtros para limitar dados
- Verificar índices do banco de dados
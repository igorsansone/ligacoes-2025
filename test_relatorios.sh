#!/bin/bash

echo "🧪 TESTE DO SISTEMA DE RELATÓRIOS AVANÇADO"
echo "================================================="

# Verificar se o servidor está rodando
echo "Verificando servidor..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ | grep -q "302\|200"; then
    echo "✅ Servidor está rodando"
else
    echo "❌ Servidor não está acessível em localhost:8080"
    echo "   Certifique-se de que o servidor está rodando"
    exit 1
fi

echo ""
echo "=== TESTE DOS ENDPOINTS DE RELATÓRIOS ==="

endpoints=(
    "/api/stats/comparativo_periodo"
    "/api/stats/pico_horarios"
    "/api/stats/por_atendente"
)

for endpoint in "${endpoints[@]}"; do
    echo ""
    echo "Testando: $endpoint"
    status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080$endpoint")
    echo "Status: $status"
    
    if [ "$status" = "401" ]; then
        echo "⚠️  Endpoint requer autenticação (esperado)"
    elif [ "$status" = "200" ]; then
        echo "✅ Endpoint funcionando"
    else
        echo "❌ Erro inesperado"
    fi
done

echo ""
echo "=== TESTE DOS ENDPOINTS DE EXPORTAÇÃO ==="

export_endpoints=(
    "/api/export/csv?tipo=por_duvida"
    "/api/export/csv?tipo=detalhado"
    "/api/export/pdf?tipo=por_duvida"
    "/api/export/pdf?tipo=detalhado"
)

for endpoint in "${export_endpoints[@]}"; do
    echo ""
    echo "Testando: $endpoint"
    status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080$endpoint")
    echo "Status: $status"
    
    if [ "$status" = "401" ]; then
        echo "⚠️  Endpoint requer autenticação (esperado)"
    elif [ "$status" = "200" ]; then
        echo "✅ Endpoint funcionando"
    else
        echo "❌ Erro inesperado"
    fi
done

echo ""
echo "=== VALIDAÇÃO DA ESTRUTURA DAS APIs ==="
echo ""
echo "📋 Estruturas esperadas:"
echo "   por_duvida: labels, counts, total"
echo "   por_dia: labels, counts"
echo "   comparativo_periodo: labels, counts, periodo, total"
echo "   pico_horarios: labels, counts, total"
echo "   por_atendente: labels, counts, total"

echo ""
echo "=== DADOS DE TESTE ==="
echo "Para testes completos, adicione dados via interface:"
echo "1. Faça login no sistema (http://localhost:8080)"
echo "2. Cadastre algumas ligações com diferentes:"
echo "   - Tipos de dúvida"
echo "   - Horários"
echo "   - Atendentes"
echo "3. Execute os testes novamente"

echo ""
echo "================================================="
echo "✅ TESTES CONCLUÍDOS"
echo "📖 Veja RELATORIOS.md para documentação completa"
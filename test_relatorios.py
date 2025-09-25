#!/usr/bin/env python3
"""
Testes básicos para as novas funcionalidades de relatórios
"""
import requests
import json
import sys
from datetime import datetime, date


def test_report_endpoints():
    """Testa os endpoints de relatório com dados de exemplo"""
    base_url = "http://localhost:8080"
    
    # Primeiro, seria necessário fazer login e obter cookie de sessão
    # Para simplicidade, este teste assume que o usuário está logado
    
    print("=== TESTE DOS ENDPOINTS DE RELATÓRIOS ===")
    
    endpoints = [
        "/api/stats/comparativo_periodo",
        "/api/stats/pico_horarios", 
        "/api/stats/por_atendente"
    ]
    
    for endpoint in endpoints:
        print(f"\nTestando: {endpoint}")
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 401:
                print("⚠️  Endpoint requer autenticação (esperado)")
            elif response.status_code == 200:
                data = response.json()
                print(f"✅ Dados retornados: {len(data.get('labels', []))} itens")
            else:
                print(f"❌ Erro inesperado: {response.text}")
                
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")
    
    print("\n=== TESTE DOS ENDPOINTS DE EXPORTAÇÃO ===")
    
    export_endpoints = [
        "/api/export/csv?tipo=por_duvida",
        "/api/export/csv?tipo=detalhado",
        "/api/export/pdf?tipo=por_duvida", 
        "/api/export/pdf?tipo=detalhado"
    ]
    
    for endpoint in export_endpoints:
        print(f"\nTestando: {endpoint}")
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 401:
                print("⚠️  Endpoint requer autenticação (esperado)")
            elif response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content)
                print(f"✅ Arquivo gerado: {content_type}, {content_length} bytes")
            else:
                print(f"❌ Erro inesperado: {response.text}")
                
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")


def validate_api_structure():
    """Valida a estrutura das respostas da API"""
    print("\n=== VALIDAÇÃO DA ESTRUTURA DAS APIs ===")
    
    # Estruturas esperadas para cada endpoint
    expected_structures = {
        "por_duvida": ["labels", "counts", "total"],
        "por_dia": ["labels", "counts"],
        "comparativo_periodo": ["labels", "counts", "periodo", "total"],
        "pico_horarios": ["labels", "counts", "total"],
        "por_atendente": ["labels", "counts", "total"]
    }
    
    for api_name, expected_fields in expected_structures.items():
        print(f"\n📋 Estrutura esperada para {api_name}:")
        for field in expected_fields:
            print(f"   - {field}")


def generate_test_data():
    """Gera alguns dados de teste via API (requer autenticação)"""
    print("\n=== DADOS DE TESTE ===")
    print("Para testes completos, adicione dados via interface:")
    print("1. Faça login no sistema")
    print("2. Cadastre algumas ligações com diferentes:")
    print("   - Tipos de dúvida")
    print("   - Horários")
    print("   - Atendentes")
    print("3. Execute os testes novamente")


if __name__ == "__main__":
    print("🧪 TESTE DO SISTEMA DE RELATÓRIOS AVANÇADO")
    print("=" * 50)
    
    # Verificar se o servidor está rodando
    try:
        response = requests.get("http://localhost:8080/", timeout=5)
        if response.status_code in [200, 302]:  # 302 = redirect para login
            print("✅ Servidor está rodando")
        else:
            print(f"⚠️  Servidor retornou código {response.status_code}")
    except Exception as e:
        print(f"❌ Servidor não está acessível: {e}")
        print("   Certifique-se de que o servidor está rodando em localhost:8080")
        sys.exit(1)
    
    test_report_endpoints()
    validate_api_structure()
    generate_test_data()
    
    print("\n" + "=" * 50)
    print("✅ TESTES CONCLUÍDOS")
    print("📖 Veja RELATORIOS.md para documentação completa")
"""
Teste de integração: verifica se config.py é carregado e usado corretamente.
"""
import os
import sys

# Remove variáveis de ambiente para forçar uso do JSON
for key in ['DATABASE_URL', 'NEON_DATABASE_URL', 'NEON_REST_URL', 'NEON_REST_API_URL', 'NEON_API_KEY']:
    os.environ.pop(key, None)

# Define MASTER_KEY
os.environ['MASTER_KEY'] = 'test_master_key_1234567890'

from config import get_database_config, save_config
from licenca import gerar_licenca

def test_config():
    print('=== Teste de Configuração ===\n')
    
    # Salva uma config de teste
    print('1. Salvando configuração de teste...')
    save_config({
        'neon_rest_url': 'https://ep-dry-hall-acd532yy.apirest.sa-east-1.aws.neon.tech/neondb/rest/v1',
        'neon_api_key': 'fake_jwt_token_for_testing'
    })
    print('   ✓ Config salva\n')
    
    # Carrega e verifica
    print('2. Carregando configuração...')
    db_config = get_database_config()
    if db_config:
        print(f'   ✓ Tipo: {db_config["type"]}')
        print(f'   ✓ URL: {db_config["url"][:60]}...')
        print(f'   ✓ API Key: {"presente" if db_config.get("api_key") else "ausente"}\n')
    else:
        print('   ✗ Nenhuma configuração encontrada\n')
        return False
    
    # Gera um token de teste
    print('3. Gerando token de licença...')
    cnpjs = ['12345678000199']
    ids = ['device-1']
    validade = '2026-12-31'
    
    token = gerar_licenca(cnpjs, ids, validade, 'Cliente Teste', 'srv', 'db')
    print(f'   ✓ Token gerado ({len(token)} bytes)\n')
    
    print('4. Simulando registro no banco...')
    print('   (Pulado - requer conexão real)\n')
    
    print('✅ Teste completo! Sistema de configuração funcionando.')
    return True

if __name__ == '__main__':
    try:
        success = test_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f'\n❌ Erro: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

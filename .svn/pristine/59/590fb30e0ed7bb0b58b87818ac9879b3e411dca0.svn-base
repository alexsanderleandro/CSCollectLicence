"""
Script de configuração rápida para CSCollectLicence.
Execute este script para configurar a conexão com o banco de dados Neon.
"""
import os
import sys

# Adiciona o diretório do script ao path para importar config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import configure_database_interactive, get_config_path, load_config

def main():
    print('=' * 60)
    print('CSCollectLicence - Configuração de Banco de Dados')
    print('=' * 60)
    
    # Mostra configuração atual se existir
    current = load_config()
    if current:
        print('\n📋 Configuração atual:')
        if current.get('database_url'):
            print(f"  DATABASE_URL: {current['database_url'][:60]}...")
        print(f'\n📁 Arquivo: {get_config_path()}\n')
    else:
        print('\n⚠ Nenhuma configuração encontrada.\n')
    
    # Menu interativo
    configure_database_interactive()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\nCancelado pelo usuário.')
    except Exception as e:
        print(f'\n❌ Erro: {e}')

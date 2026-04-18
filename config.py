"""
Gerenciamento de configurações salvas em JSON local.
"""
import os
import json
import sys


def get_app_dir():
    """Retorna o diretório onde o executável está rodando (ou o script em desenvolvimento)."""
    if getattr(sys, 'frozen', False):
        # PyInstaller: usa o diretório do executável
        return os.path.dirname(sys.executable)
    else:
        # Desenvolvimento: usa o diretório do script
        return os.path.dirname(os.path.abspath(__file__))


def get_config_path():
    """Retorna o caminho completo do arquivo de configuração JSON."""
    return os.path.join(get_app_dir(), 'cscollect_config.json')


def load_config():
    """Carrega configurações do arquivo JSON. Retorna dict vazio se não existir."""
    path = get_config_path()
    if not os.path.isfile(path):
        return {}
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'Aviso: erro ao carregar config: {e}')
        return {}


def save_config(config_dict):
    """Salva configurações no arquivo JSON."""
    path = get_config_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f'Erro ao salvar config: {e}')
        return False


def get_database_config():
    """Retorna a configuração de banco a partir do JSON ou variáveis de ambiente.
    
    Prioridade:
    1. Variável de ambiente DATABASE_URL
    2. Arquivo JSON local (database_url)
    
    Retorna: dict com chaves 'type' ('sql'), 'url'
    """
    # Prioridade 1: DATABASE_URL de env
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
    if db_url:
        return {'type': 'sql', 'url': db_url}
    
    # Prioridade 2: arquivo JSON
    config = load_config()
    if config.get('database_url'):
        return {'type': 'sql', 'url': config['database_url']}
    
    return None


def configure_database_interactive():
    """Menu interativo para configurar a conexão com o banco."""
    print('\n=== Configuração de Banco de Dados ===')
    print('Digite a connection string (DATABASE_URL) do PostgreSQL.')
    print('Formato: postgresql://user:password@host:port/database')
    print('\nPressione Enter sem digitar nada para cancelar.\n')
    
    url = input('DATABASE_URL: ').strip()
    
    if not url:
        print('Cancelado.')
        return
    
    config = load_config()
    config['database_url'] = url
    
    if save_config(config):
        print(f'\n✓ Configuração salva em: {get_config_path()}')
    else:
        print('\n✗ Erro ao salvar configuração')


if __name__ == '__main__':
    # Teste/configuração interativa
    configure_database_interactive()

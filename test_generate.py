import os

# Define MASTER_KEY antes de importar o módulo
os.environ['MASTER_KEY'] = os.environ.get('MASTER_KEY', 'test_master_key_1234567890')

from licenca import gerar_licenca, salvar_licenca, carregar_licenca_de_arquivo

cnpjs = ['12345678000199']
ids = ['device-1']
validade = '2026-12-31'
nome = 'Cliente Teste'
sql_servidor = 'srv'
sql_banco = 'db'

token = gerar_licenca(cnpjs, ids, validade, nome, sql_servidor, sql_banco)
meta = {'cnpjs': cnpjs, 'ids_celular': ids, 'validade': validade}
caminho = 'test_Licenca_CSCollectManager_cliente.key'

salvar_licenca(token, caminho, payload_meta=meta)

print('Arquivo salvo:', caminho)
payload, token_loaded = carregar_licenca_de_arquivo(caminho)
print('Payload carregado:', payload)
print('Token recuperado (len):', len(token_loaded))

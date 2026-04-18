import os
from licenca import gerar_licenca, registrar_tokens_por_cnpjs

def main():
    # garante MASTER_KEY para gerar token localmente
    os.environ.setdefault('MASTER_KEY', 'test_master_key_1234567890')

    cnpjs = ['12345678000199']
    ids = ['device-1']
    validade = '2026-12-31'
    nome = 'Cliente Teste'
    sql_servidor = 'srv'
    sql_banco = 'db'

    token = gerar_licenca(cnpjs, ids, validade, nome, sql_servidor, sql_banco)

    print('Tentando registrar CNPJs via Neon REST...')
    res = registrar_tokens_por_cnpjs(cnpjs, token)
    print('Resposta do registro:', res)


if __name__ == '__main__':
    main()

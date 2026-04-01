"""Módulo com funções para o CSCollectManager verificar licenças geradas.

Fornece API programática para:
 - `verify_token(token, master_key)` -> retorna payload dict se válido
 - `load_and_verify_file(path, master_key=None)` -> lê arquivo .key e verifica
 - `get_relevant_fields(payload)` -> dicionário com campos esperados pelo app

Use estas funções dentro do CSCollectManager para verificar assinatura e
extrair `sql_servidor` e `sql_banco` de forma robusta.
"""
from __future__ import annotations
import os
import json
import base64
import hmac
import hashlib
from typing import Tuple, Dict, Any, Optional


def _b64u_decode(s: str) -> bytes:
    padding = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + padding).encode('ascii'))


def split_token(token: str) -> Tuple[bytes, bytes]:
    parts = token.strip().split('.')
    if len(parts) != 2:
        raise ValueError('Formato de token inválido; esperado payload.signature')
    dados = _b64u_decode(parts[0])
    assinatura = _b64u_decode(parts[1])
    return dados, assinatura


def verify_token(token: str, master_key: str) -> Dict[str, Any]:
    """Verifica assinatura HMAC-SHA256 e retorna o payload JSON como dict.

    Lança `ValueError` em caso de formato inválido ou assinatura incorreta, e
    `json.JSONDecodeError` se o payload não for um JSON válido.
    """
    if not master_key:
        raise ValueError('master_key não fornecida')
    dados, assinatura = split_token(token)
    esperado = hmac.new(master_key.encode('utf-8'), dados, hashlib.sha256).digest()
    if not hmac.compare_digest(esperado, assinatura):
        raise ValueError('Assinatura inválida')
    payload = json.loads(dados.decode('utf-8'))
    return payload


def load_and_verify_file(path: str, master_key: Optional[str] = None) -> Dict[str, Any]:
    """Lê um arquivo contendo o token e verifica sua assinatura.

    Se `master_key` for None, a função tenta ler a variável de ambiente
    `MASTER_KEY`. Lança exceções em caso de erro (arquivo não encontrado,
    formato inválido, assinatura inválida).
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, 'r', encoding='utf-8') as f:
        token = f.read().strip()
    mk = master_key or os.environ.get('MASTER_KEY')
    if not mk:
        raise ValueError('MASTER_KEY não fornecida (passar master_key ou definir variável de ambiente).')
    return verify_token(token, mk)


def get_relevant_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna um dicionário com os campos que o CSCollectManager precisa."""
    return {
        'nome_cliente': payload.get('nome_cliente', ''),
        'sql_servidor': payload.get('sql_servidor', ''),
        'sql_banco': payload.get('sql_banco', ''),
        'validade': payload.get('validade', ''),
        'gerado_em': payload.get('gerado_em', ''),
        'cnpjs': payload.get('cnpjs', []),
        'ids_celular': payload.get('ids_celular', []),
    }


if __name__ == '__main__':
    # Exemplo mínimo de uso rápido para testes
    import argparse
    parser = argparse.ArgumentParser(description='Verifica arquivo de licença e imprime campos')
    parser.add_argument('path', help='Caminho para o arquivo .key')
    parser.add_argument('--master-key', help='Chave mestra (ou use env MASTER_KEY)')
    args = parser.parse_args()
    try:
        payload = load_and_verify_file(args.path, args.master_key)
    except Exception as e:
        print('Erro:', e)
        raise SystemExit(2)
    fields = get_relevant_fields(payload)
    print(json.dumps(fields, ensure_ascii=False, indent=2))

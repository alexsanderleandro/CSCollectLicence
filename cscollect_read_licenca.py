#!/usr/bin/env python3
"""Leitor de licença para CSCollectManager

Este utilitário lê um arquivo de licença gerado pelo `gerar_licenca` (formato
base64url(payload).base64url(signature)) e imprime o payload JSON de forma
legível. Opcionalmente verifica a assinatura HMAC-SHA256 usando a chave mestra
fornecida via `--master-key` ou pela variável de ambiente `MASTER_KEY`.

Uso:
  python cscollect_read_licenca.py caminho/para/Licenca.key
  python cscollect_read_licenca.py --token "<token>" --master-key ABCDEF
  python cscollect_read_licenca.py caminho/para/Licenca.key --no-verify

O script exibe os campos principais (`nome_cliente`, `sql_servidor`, `sql_banco`,
`cnpjs`, `ids_celular`, `validade`, `gerado_em`) que o CSCollectManager espera.
"""
from __future__ import annotations
import os
import sys
import argparse
import json
import base64
import hmac
import hashlib
from typing import Tuple


def _b64u_decode(s: str) -> bytes:
    padding = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + padding).encode('ascii'))


def split_token(token: str) -> Tuple[bytes, bytes]:
    parts = token.strip().split('.')
    if len(parts) != 2:
        raise ValueError('Formato de token inválido (esperado payload.signature)')
    dados = _b64u_decode(parts[0])
    assinatura = _b64u_decode(parts[1])
    return dados, assinatura


def verify_signature(dados: bytes, assinatura: bytes, master_key: str) -> bool:
    if master_key is None:
        raise ValueError('master_key não fornecida')
    mac = hmac.new(master_key.encode('utf-8'), dados, hashlib.sha256).digest()
    return hmac.compare_digest(mac, assinatura)


def load_token_from_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def pretty_print_payload(payload: dict) -> None:
    # Imprime JSON formatado e campos principais em linhas legíveis
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print('\nCampos relevantes:')
    for k in ('nome_cliente', 'sql_servidor', 'sql_banco', 'validade', 'gerado_em'):
        v = payload.get(k)
        print(f'- {k}: {v}')
    print('- cnpjs: %s' % (', '.join(payload.get('cnpjs', [])) or ''))
    print('- ids_celular: %s' % (', '.join(payload.get('ids_celular', [])) or ''))


def main(argv=None):
    p = argparse.ArgumentParser(description='Lê e verifica arquivo de licença CSCollect')
    p.add_argument('path', nargs='?', help='Caminho para o arquivo .key contendo o token')
    p.add_argument('--token', help='Fornece o token diretamente em vez de arquivo')
    p.add_argument('--master-key', help='Chave mestra para verificação HMAC (ou env MASTER_KEY)')
    p.add_argument('--no-verify', dest='verify', action='store_false', help='Não verificar assinatura')
    p.set_defaults(verify=True)
    args = p.parse_args(argv)

    if not args.path and not args.token:
        p.error('Informe o caminho do arquivo ou --token')

    token = args.token or load_token_from_file(args.path)

    try:
        dados, assinatura = split_token(token)
    except Exception as e:
        print('Erro ao decodificar token:', e, file=sys.stderr)
        return 2

    if args.verify:
        master_key = args.master_key or os.environ.get('MASTER_KEY')
        if not master_key:
            print('Verificação habilitada, mas MASTER_KEY não fornecida (use --master-key ou variável de ambiente).', file=sys.stderr)
            return 3
        try:
            ok = verify_signature(dados, assinatura, master_key)
        except Exception as e:
            print('Erro durante verificação:', e, file=sys.stderr)
            return 4
        if not ok:
            print('Assinatura inválida!', file=sys.stderr)
            return 5
        else:
            print('Assinatura válida.')
    else:
        print('Verificação de assinatura desabilitada (--no-verify).')

    try:
        payload = json.loads(dados.decode('utf-8'))
    except Exception as e:
        print('Falha ao decodificar JSON do payload:', e, file=sys.stderr)
        return 6

    pretty_print_payload(payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

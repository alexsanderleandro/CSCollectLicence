import os
import json
import base64
import hmac
import hashlib
import secrets
import copy
import urllib.parse
try:
    import requests
except Exception:
    requests = None

try:
    from config import get_database_config
except ImportError:
    get_database_config = None
from datetime import datetime, date, timezone


# Tenta carregar variáveis de ambiente a partir de um arquivo .env, se disponível
try:
    from dotenv import load_dotenv
    import sys

    if getattr(sys, 'frozen', False):
        # Executável congelado pelo PyInstaller
        # 1. Tenta o .env extraído no diretório temporário (sys._MEIPASS)
        _meipass_env = os.path.join(sys._MEIPASS, '.env')
        if os.path.isfile(_meipass_env):
            load_dotenv(_meipass_env)
        # 2. Tenta o .env ao lado do próprio executável
        _exe_env = os.path.join(os.path.dirname(sys.executable), '.env')
        if os.path.isfile(_exe_env):
            load_dotenv(_exe_env, override=False)
    else:
        load_dotenv()
except Exception:
    # `python-dotenv` pode não estar instalado — isso é opcional.
    pass


# Lê a chave mestra da variável de ambiente `MASTER_KEY` (obrigatória)
MASTER_KEY = os.environ.get("MASTER_KEY")
if MASTER_KEY is None:
    raise RuntimeError(
        "Variável de ambiente MASTER_KEY não definida. Defina-a ou instale python-dotenv e crie um arquivo .env com MASTER_KEY."
    )
MASTER_KEY_BYTES = MASTER_KEY.encode("utf-8")


def _b64u_encode(b: bytes) -> str:
    """Encode bytes em base64 URL-safe sem padding.

    Retorna uma string ASCII sem os caracteres de preenchimento '='.
    """
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    """Decodifica uma string base64 URL-safe possivelmente sem padding.

    Reconstitui o padding necessário e retorna os bytes originais.
    """
    padding = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + padding).encode('ascii'))


def _ensure_token_complete(token: str) -> str:
    """Garante que o `token` contém payload + '.' + signature.

    Se `token` já contém um ponto ('.') é retornado sem alterações.
    Se parece ser apenas o payload (base64url do JSON), tenta decodificar
    e calcular a assinatura HMAC-SHA256 usando `MASTER_KEY_BYTES`, anexando
    a parte de assinatura codificada em base64url.
    Em caso de falha na decodificação, retorna o token original.
    """
    if not token or '.' in token:
        return token
    try:
        dados = _b64u_decode(token)
    except Exception:
        return token
    assinatura = hmac.new(MASTER_KEY_BYTES, dados, hashlib.sha256).digest()
    return f"{token}.{_b64u_encode(assinatura)}"


def gerar_licenca(cnpjs, ids_celular, validade, nome_cliente, sql_servidor, sql_banco):
    """Gera um token de licença.

    O token é uma string compacta e assinada que contém o payload JSON
    com os campos informados. Formato final:

        base64url(json_payload) + '.' + base64url(hmac_sha256_signature)

    Passos principais:
     1) Validações: exige pelo menos um CNPJ, pelo menos um ID de celular
         e um `nome_cliente` (máx 30 caracteres).
    2) Constrói o payload (lista de `cnpjs`, `ids_celular`, `validade` e metadados).
    3) Serializa o payload em JSON UTF-8.
    4) Calcula HMAC-SHA256 sobre os bytes do JSON usando `MASTER_KEY`.
    5) Codifica payload e assinatura em base64url e concatena com '.' — esse é o token.

    Observações de uso:
    - O token pode ser salvo em disco (por exemplo, em `licenca.key`) ou exibido
      para cópia/colagem. É a única informação necessária para validar a licença
      no lado do cliente, via `verificar_licenca`.
    - Mantemos `gerado_em` no payload para rastreabilidade.
    """

    # 1) Validações mínimas de entrada
    if not cnpjs:
        raise ValueError("É obrigatório informar pelo menos um CNPJ.")
    if not ids_celular:
        raise ValueError("É obrigatório informar pelo menos um ID de celular.")
    # valida nome do cliente
    if not nome_cliente or not str(nome_cliente).strip():
        raise ValueError("É obrigatório informar o nome do cliente.")
    nome_cliente = str(nome_cliente).strip()
    if len(nome_cliente) > 30:
        raise ValueError("O nome do cliente deve ter no máximo 30 caracteres.")

    # valida servidor SQL e banco
    if not sql_servidor or not str(sql_servidor).strip():
        raise ValueError("É obrigatório informar o nome do servidor SQL.")
    sql_servidor = str(sql_servidor).strip()
    if len(sql_servidor) > 30:
        raise ValueError("O nome do servidor SQL deve ter no máximo 30 caracteres.")
    if not sql_banco or not str(sql_banco).strip():
        raise ValueError("É obrigatório informar o nome do banco de dados.")
    sql_banco = str(sql_banco).strip()
    if len(sql_banco) > 30:
        raise ValueError("O nome do banco de dados deve ter no máximo 30 caracteres.")

    # 2) Monta o payload com os dados informados e metadados
    # registrar hora local com offset correto (ex: 2026-04-01T12:34:56+03:00)
    payload = {
        "cnpjs": cnpjs,
        "ids_celular": ids_celular,
        "validade": validade,
        "nome_cliente": nome_cliente,
        "sql_servidor": sql_servidor,
        "sql_banco": sql_banco,
        "gerado_em": datetime.now().astimezone().replace(microsecond=0).isoformat(),
    }

    # 3) Serializa para JSON (bytes UTF-8)
    dados = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    # 4) Calcula assinatura HMAC-SHA256 usando a chave mestra
    assinatura = hmac.new(MASTER_KEY_BYTES, dados, hashlib.sha256).digest()

    # 5) Codifica em base64url sem padding e concatena para formar o token
    token = f"{_b64u_encode(dados)}.{_b64u_encode(assinatura)}"
    return token


def verificar_licenca(token, validar_validade=True):
    """Verifica e valida um token de licença.

    Retorna o payload (dict) decodificado se a assinatura for válida e,
    se `validar_validade` for True, também verifica se a validade não expirou.

    Lança `ValueError` em casos de formato inválido, assinatura incorreta ou
    validade expirada. Pode lançar outras exceções de I/O/parse se houverem
    problemas ao decodificar o payload.
    """
    try:
        parts = token.split('.')
        if len(parts) != 2:
            raise ValueError("Formato de token inválido")

        dados_b64, sig_b64 = parts
        dados = _b64u_decode(dados_b64)
        assinatura_recebida = _b64u_decode(sig_b64)

        assinatura_esperada = hmac.new(MASTER_KEY_BYTES, dados, hashlib.sha256).digest()

        if not secrets.compare_digest(assinatura_recebida, assinatura_esperada):
            raise ValueError("Assinatura inválida")

        payload = json.loads(dados.decode('utf-8'))

        if validar_validade and payload.get('validade'):
            val = payload['validade']
            try:
                # Se contém 'T' ou termina com 'Z', trata como datetime
                if isinstance(val, str) and ("T" in val or val.endswith('Z')):
                    v = val.replace('Z', '+00:00')
                    validade_dt = datetime.fromisoformat(v)
                    if validade_dt.tzinfo is None:
                        validade_dt = validade_dt.replace(tzinfo=timezone.utc)
                    hoje = datetime.now(timezone.utc)
                    if validade_dt < hoje:
                        raise ValueError("Licença expirada")
                else:
                    # Assume formato YYYY-MM-DD
                    validade_date = date.fromisoformat(val)
                    if validade_date < date.today():
                        raise ValueError("Licença expirada")
            except ValueError:
                raise ValueError("Formato de validade desconhecido ou licença expirada")

        return payload

    except Exception as e:
        raise


def salvar_licenca(token, caminho="licenca.key", payload_meta=None):
    """Salva a licença no arquivo especificado.

    Comportamentos:
    - Se `payload_meta` for fornecido (dict), salva um JSON contendo
      os campos recomendados do manager: `cnpjs`, `ids`, `token`, `validade`, `database_url`.
    - Caso contrário, salva apenas a string do token (compatibilidade).

    Parâmetros:
    - token: string do token gerado por `gerar_licenca`.
    - caminho: caminho do arquivo onde será gravado.
    - payload_meta: dict opcional com chaves semelhantes ao payload
      (por exemplo: {'cnpjs': [...], 'ids_celular': [...], 'validade': 'YYYY-MM-DD', 'database_url': '...'}).
    """
    # garante que o token salvo no arquivo contém payload + assinatura
    token = _ensure_token_complete(token)

    if payload_meta:
        # Normaliza nomes: nosso payload usa `ids_celular`, mas o manager
        # espera `ids` no JSON final.
        out = {
            "cnpjs": payload_meta.get("cnpjs") or payload_meta.get("cnpj") or [],
            "ids": payload_meta.get("ids") or payload_meta.get("ids_celular") or [],
            "token": token,
            "validade": payload_meta.get("validade"),
            "api_url": payload_meta.get("api_url") or "",
            "database_url": payload_meta.get("database_url"),
            "nome_cliente": payload_meta.get("nome_cliente") or "",
            "sql_servidor": payload_meta.get("sql_servidor") or "",
            "sql_banco": payload_meta.get("sql_banco") or "",
        }
        # grava JSON legível (cp1252/latin-1 para compatibilidade com caracteres como ô)
        with open(caminho, "w", encoding='cp1252') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    else:
        with open(caminho, "w", encoding='cp1252') as f:
            f.write(token)


def carregar_licenca_de_arquivo(caminho="licenca.key"):
    """Lê token (ou JSON de manager) de `caminho`, verifica e retorna o payload (dict) e o token.

    Suporta dois formatos de arquivo:
    - Texto simples contendo o token.
    - JSON contendo pelo menos a chave `token` (ex.: manager key).
    """
    try:
        raw = open(caminho, "rb").read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    # Remove BOM UTF-8 se presente
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]

    # Tenta decodificar: UTF-8 → cp1252 → latin-1 (fallback universal)
    for enc in ('utf-8', 'cp1252', 'latin-1'):
        try:
            conteudo = raw.decode(enc).strip()
            break
        except UnicodeDecodeError:
            continue

    token = None
    payload = None
    # tenta detectar JSON com campo `token`
    if conteudo.startswith('{'):
        try:
            doc = json.loads(conteudo)
            token = doc.get('token')
            # Monta payload a partir dos campos do JSON (formato CSCollect Manager)
            # IDs podem vir como 'ids' ou 'ids_celular'
            ids = doc.get('ids_celular') or doc.get('ids') or []
            cnpjs = doc.get('cnpjs') or []
            if cnpjs or ids:
                payload = {
                    'cnpjs': cnpjs,
                    'ids_celular': ids,
                    'validade': doc.get('validade', ''),
                    'nome_cliente': doc.get('nome_cliente', ''),
                    'sql_servidor': doc.get('sql_servidor', ''),
                    'sql_banco': doc.get('sql_banco', ''),
                    'database_url': doc.get('database_url', ''),
                    'api_url': doc.get('api_url', ''),
                }
        except Exception:
            token = None

    # Se já temos o payload do JSON envelope, tenta validar o token mas não bloqueia se falhar
    if payload is not None:
        if token:
            try:
                payload_verificado = verificar_licenca(token)
                # Mescla campos extras que só existem no payload assinado
                # (prioridade: valor existente no envelope > valor do token)
                for k, v in payload_verificado.items():
                    if not payload.get(k):
                        payload[k] = v
            except Exception:
                # Token em formato externo (ex: CSCollect Manager) — tenta decodificar
                # o payload da primeira parte do token sem verificar assinatura
                try:
                    parte_payload = token.split('.')[0]
                    import base64 as _b64
                    padding = '=' * (-len(parte_payload) % 4)
                    raw_payload = _b64.urlsafe_b64decode((parte_payload + padding).encode('ascii'))
                    doc_token = json.loads(raw_payload.decode('utf-8'))
                    for k in ('nome_cliente', 'sql_servidor', 'sql_banco', 'validade', 'cnpjs', 'ids_celular'):
                        if not payload.get(k) and doc_token.get(k):
                            payload[k] = doc_token[k]
                except Exception:
                    pass
        return payload, token or ''

    if not token:
        token = conteudo

    payload = verificar_licenca(token)
    return payload, token


def _get_db_dsn_from_env():
    """Constrói DSN a partir de variáveis de ambiente ou config JSON.

    Aceita `DATABASE_URL` (preferencial) ou as variáveis NEON_HOST/NEON_DB/NEON_USER/NEON_PASSWORD/NEON_PORT.
    Se não encontrar em env, tenta carregar do arquivo JSON local.
    """
    url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
    if url:
        return url

    # Tenta carregar do JSON
    if get_database_config:
        db_config = get_database_config()
        if db_config and db_config.get('type') == 'sql':
            return db_config.get('url')

    host = os.environ.get('NEON_HOST')
    db = os.environ.get('NEON_DB') or os.environ.get('NEON_DATABASE')
    user = os.environ.get('NEON_USER')
    password = os.environ.get('NEON_PASSWORD')
    port = os.environ.get('NEON_PORT') or os.environ.get('NEON_PORTA') or '5432'

    if not (host and db and user and password):
        return None

    return f"host={host} port={port} dbname={db} user={user} password={password}"


def _exec_db_statements(statements):
    """Executa uma lista de (query, params) no banco Postgres (Neon).

    Tenta usar `psycopg2` ou `psycopg` (v3). Lança erro explicativo se nenhum estiver instalado
    ou se variáveis de conexão estiverem ausentes.
    """
    dsn = _get_db_dsn_from_env()
    if not dsn:
        raise RuntimeError('Credenciais do banco não encontradas nas variáveis de ambiente (DATABASE_URL ou NEON_*).')

    # importa dinamicamente
    db = None
    try:
        import psycopg2 as db
        _psycopg_v3 = False
    except Exception:
        try:
            import psycopg as db
            _psycopg_v3 = True
        except Exception:
            raise RuntimeError('Instale psycopg2 ou psycopg para ativar registro no banco (pip install psycopg2-binary).')

    conn = None
    try:
        if _psycopg_v3:
            conn = db.connect(dsn)
            with conn:
                with conn.cursor() as cur:
                    for q, p in statements:
                        cur.execute(q, p)
        else:
            conn = db.connect(dsn)
            conn.autocommit = False
            cur = conn.cursor()
            try:
                for q, p in statements:
                    cur.execute(q, p)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def registrar_tokens_por_cnpjs(cnpjs, token):
    """Insere/atualiza o `token` para cada CNPJ na tabela `clientes`.

    Usa INSERT ... ON CONFLICT (cnpj) DO UPDATE SET token = EXCLUDED.token;
    Prioridade: env DATABASE_URL > env REST > JSON config
    """
    if not cnpjs:
        return
    
    # Tenta obter configuração (env ou JSON)
    db_config = None
    if get_database_config:
        db_config = get_database_config()
    
    # Fallback: tenta env direto se config.py não disponível
    if not db_config:
        db_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
        rest_url = os.environ.get('NEON_REST_URL') or os.environ.get('NEON_REST_API_URL')
        if db_url:
            db_config = {'type': 'sql', 'url': db_url}
        elif rest_url:
            db_config = {'type': 'rest', 'url': rest_url, 'api_key': os.environ.get('NEON_API_KEY')}
    
    if not db_config:
        raise RuntimeError('Configuração de banco não encontrada. Execute config.py ou defina DATABASE_URL.')
    
    # garante que o token contém assinatura (payload.signature)
    token = _ensure_token_complete(token)

    # Executa conforme o tipo
    if db_config['type'] == 'sql':
        statements = []
        q = (
            "INSERT INTO clientes (cnpj, token, ativo, reginclusao, dataalteracao) "
            "VALUES (%s, %s, true, now(), now()) "
            "ON CONFLICT (cnpj) DO UPDATE SET token = EXCLUDED.token, dataalteracao = now();"
        )
        for c in cnpjs:
            statements.append((q, (c, token)))
        return _exec_db_statements(statements)
    elif db_config['type'] == 'rest':
        return _registrar_tokens_por_cnpjs_rest(db_config['url'], cnpjs, token, db_config.get('api_key'))
    else:
        raise RuntimeError('Tipo de configuração desconhecido.')


def deletar_registro_por_cnpjs(cnpjs_str):
    """Deleta um registro da tabela `clientes` pela chave primária cnpj.
    
    Parâmetros:
    - cnpjs_str: string com CNPJs separados por vírgula (chave primária)
    """
    if not cnpjs_str:
        return
    
    # Tenta obter configuração (env ou JSON)
    db_config = None
    if get_database_config:
        db_config = get_database_config()
    
    # Fallback: tenta env direto
    if not db_config:
        db_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
        if db_url:
            db_config = {'type': 'sql', 'url': db_url}
    
    if not db_config:
        raise RuntimeError('Configuração de banco não encontrada. Execute config.py ou defina DATABASE_URL.')
    
    # Executa DELETE
    q = "DELETE FROM clientes WHERE cnpj = %s;"
    statements = [(q, (cnpjs_str,))]
    return _exec_db_statements(statements)


def registrar_tokens_por_cnpjs_single(cnpjs_str, ids_str, token, validade='', ativa=True, nome_cliente='', sql_servidor='', sql_banco=''):
    """Insere/atualiza um ÚNICO registro na tabela `clientes` com CNPJs e IDs separados por vírgula.
    
    Parâmetros:
    - cnpjs_str: string com CNPJs separados por vírgula (ex: "12345678000199,98765432000188")
    - ids_str: string com IDs de celular separados por vírgula
    - token: token assinado
    - validade: data de validade (YYYY-MM-DD) ou string vazia para sem validade
    - ativa: boolean indicando se a licença está ativa (padrão: True)
    - nome_cliente: nome do cliente vinculado à licença (máx 30 caracteres)
    - sql_servidor: nome do servidor SQL (máx 30 caracteres)
    - sql_banco: nome do banco de dados (máx 30 caracteres)
    
    Tabela esperada: clientes (cnpj VARCHAR PRIMARY KEY, idcelular TEXT, token TEXT, validade VARCHAR, ativo BOOLEAN, nome_cliente VARCHAR, sql_servidor VARCHAR, sql_banco VARCHAR)
    """
    if not cnpjs_str:
        return
    
    # Tenta obter configuração (env ou JSON)
    db_config = None
    if get_database_config:
        db_config = get_database_config()
    
    # Fallback: tenta env direto
    if not db_config:
        db_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
        if db_url:
            db_config = {'type': 'sql', 'url': db_url}
    
    if not db_config:
        raise RuntimeError('Configuração de banco não encontrada. Execute config.py ou defina DATABASE_URL.')
    
    # garante que o token contém assinatura (payload.signature)
    token = _ensure_token_complete(token)

    # Executa SQL
    if db_config['type'] == 'rest':
        return _registrar_tokens_single_rest(
            db_config['url'], cnpjs_str, ids_str, token, validade,
            api_key=db_config.get('api_key'),
            nome_cliente=nome_cliente, sql_servidor=sql_servidor, sql_banco=sql_banco
        )
    q = (
        "INSERT INTO clientes (cnpj, idcelular, token, validade, ativo, nome_cliente, sql_servidor, sql_banco, reginclusao, dataalteracao) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), now()) "
        "ON CONFLICT (cnpj) DO UPDATE SET idcelular = EXCLUDED.idcelular, token = EXCLUDED.token, validade = EXCLUDED.validade, ativo = EXCLUDED.ativo, nome_cliente = EXCLUDED.nome_cliente, sql_servidor = EXCLUDED.sql_servidor, sql_banco = EXCLUDED.sql_banco, dataalteracao = now();"
    )
    # converte string vazia de validade para NULL para colunas do tipo DATE
    validade_param = validade if validade else None
    statements = [(q, (cnpjs_str, ids_str, token, validade_param, ativa, nome_cliente, sql_servidor or None, sql_banco or None))]
    return _exec_db_statements(statements)


def _registrar_tokens_single_rest(base_url, cnpjs_str, ids_str, token, validade='', api_key=None, nome_cliente='', sql_servidor='', sql_banco=''):
    """Registra via REST um único registro com CNPJs e IDs separados por vírgula."""
    if requests is None:
        raise RuntimeError('Biblioteca requests não está disponível. Instale com pip install requests')

    if not api_key:
        api_key = os.environ.get('NEON_API_KEY')
    if not api_key:
        raise RuntimeError('NEON_API_KEY não definido. Configure em config.py ou variável de ambiente.')
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'Prefer': 'resolution=merge-duplicates'
    }

    url = base_url.rstrip('/') + '/clientes'
    token = _ensure_token_complete(token)
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        'cnpj': cnpjs_str,
        'idcelular': ids_str,
        'token': token,
        'validade': validade if validade else None,
        'ativo': True,
        'nome_cliente': nome_cliente or None,
        'sql_servidor': sql_servidor or None,
        'sql_banco': sql_banco or None,
        'reginclusao': now_iso,
        'dataalteracao': now_iso,
    }
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f'Erro REST ({resp.status_code}): {resp.text}')
        return resp.json() if resp.text else None
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f'Falha na conexão REST: {e}')


def _registrar_tokens_por_cnpjs_rest(base_url, cnpjs, token, api_key=None):
    """Usa o endpoint REST do Neon/PostgREST para inserir/upsert em lote.

    Exige `api_key` (JWT service_role recomendado) passado como parâmetro ou em env.
    """
    if requests is None:
        raise RuntimeError('Biblioteca requests não está disponível. Instale com pip install requests')

    if not api_key:
        api_key = os.environ.get('NEON_API_KEY')
    if not api_key:
        raise RuntimeError('NEON_API_KEY não definido. Configure em config.py ou variável de ambiente.')
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'Prefer': 'resolution=merge-duplicates'
    }

    url = base_url.rstrip('/') + '/clientes'
    token = _ensure_token_complete(token)
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = [{'cnpj': c, 'token': token, 'ativo': True, 'reginclusao': now_iso, 'dataalteracao': now_iso} for c in cnpjs]
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f'Erro REST ({resp.status_code}): {resp.text}')
        return resp.json() if resp.text else None
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f'Falha na conexão REST: {e}')


def remover_cnpjs_do_db(cnpjs):
    """Remove registros dos CNPJs informados da tabela `clientes`."""
    if not cnpjs:
        return
    
    # Tenta obter configuração (env ou JSON)
    db_config = None
    if get_database_config:
        db_config = get_database_config()
    
    # Fallback: tenta env direto
    if not db_config:
        db_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
        rest_url = os.environ.get('NEON_REST_URL') or os.environ.get('NEON_REST_API_URL')
        if db_url:
            db_config = {'type': 'sql', 'url': db_url}
        elif rest_url:
            db_config = {'type': 'rest', 'url': rest_url, 'api_key': os.environ.get('NEON_API_KEY')}
    
    if not db_config:
        raise RuntimeError('Configuração de banco não encontrada. Execute config.py ou defina DATABASE_URL.')
    
    if db_config['type'] == 'sql':
        statements = []
        q = "DELETE FROM clientes WHERE cnpj = %s;"
        for c in cnpjs:
            statements.append((q, (c,)))
        return _exec_db_statements(statements)
    elif db_config['type'] == 'rest':
        return _remover_cnpjs_do_db_rest(db_config['url'], cnpjs, db_config.get('api_key'))
    else:
        raise RuntimeError('Tipo de configuração desconhecido.')


def _remover_cnpjs_do_db_rest(base_url, cnpjs, api_key=None):
    if requests is None:
        raise RuntimeError('Biblioteca requests não está disponível. Instale com pip install requests')

    if not api_key:
        api_key = os.environ.get('NEON_API_KEY')
    if not api_key:
        raise RuntimeError('NEON_API_KEY não definido. Configure em config.py ou variável de ambiente.')
    
    headers = {
        'Authorization': f'Bearer {api_key}'
    }

    # usa operador in. (PostgREST) para deletar em lote
    # construir lista URL-encoded: in.("c1","c2")
    quoted_cnpjs = ','.join(f'"{c}"' for c in cnpjs)
    filter_part = f"cnpj=in.({quoted_cnpjs})"
    url = base_url.rstrip('/') + f"/clientes?{filter_part}"
    
    try:
        resp = requests.delete(url, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f'Erro REST DELETE ({resp.status_code}): {resp.text}')
        return resp.json() if resp.text else None
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f'Falha na conexão REST: {e}')


def _input_cnpjs_inicial():
    """Modo interativo: lê vários CNPJs do usuário até linha em branco.

    Retorna uma lista de CNPJs (apenas dígitos), na ordem informada.
    """
    cnpjs = []
    print("Digite os CNPJs (apenas dígitos). Enter em branco para terminar:")
    while True:
        v = input("CNPJ: ").strip()
        if not v:
            break
        # simples normalização: manter apenas dígitos
        v_clean = ''.join(ch for ch in v if ch.isdigit())
        if v_clean:
            cnpjs.append(v_clean)
    return cnpjs


def _menu_edicao(payload):
    """Menu de edição interativo para ajustar o payload da licença.

    Permite adicionar/remover CNPJs e IDs de celular, atualizar validade,
    e retornar o payload modificado.
    """
    while True:
        print("\nEstado atual da licença:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print('\nAções: [a]dicionar CNPJ, [r]emover CNPJ, [c]adicionar ID celular, [d]remover ID celular, [u]pdate validade, [s]alvar e sair, [q]cancelar')
        op = input('Escolha: ').strip().lower()
        if op == 'a':
            v = input('CNPJ a adicionar: ').strip()
            v_clean = ''.join(ch for ch in v if ch.isdigit())
            if v_clean and v_clean not in payload.get('cnpjs', []):
                payload.setdefault('cnpjs', []).append(v_clean)
                print('CNPJ adicionado.')
            else:
                print('CNPJ inválido ou já presente.')
        elif op == 'r':
            v = input('CNPJ a remover: ').strip()
            v_clean = ''.join(ch for ch in v if ch.isdigit())
            if v_clean in payload.get('cnpjs', []):
                payload['cnpjs'].remove(v_clean)
                print('CNPJ removido.')
            else:
                print('CNPJ não encontrado na licença.')
        elif op == 'c':
            v = input('ID de celular a adicionar: ').strip()
            if v and v not in payload.get('ids_celular', []):
                payload.setdefault('ids_celular', []).append(v)
                print('ID de celular adicionado.')
            else:
                print('ID inválido ou já presente.')
        elif op == 'd':
            v = input('ID de celular a remover: ').strip()
            if v in payload.get('ids_celular', []):
                payload['ids_celular'].remove(v)
                print('ID de celular removido.')
            else:
                print('ID de celular não encontrado na licença.')
        elif op == 'u':
            v = input('Nova validade (YYYY-MM-DD ou ISO): ').strip()
            if v:
                payload['validade'] = v
                print('Validade atualizada.')
        elif op == 's':
            return payload
        elif op == 'q':
            raise KeyboardInterrupt('Edição cancelada pelo usuário')
        else:
            print('Opção inválida.')


if __name__ == "__main__":
    try:
        print('Modo interativo de gerenciamento de licença')
        usar_existente = input('Ler arquivo de licença existente? (s/n): ').strip().lower() == 's'
        if usar_existente:
            caminho = input("Caminho do arquivo [licenca.key]: ").strip() or 'licenca.key'
            try:
                payload, token = carregar_licenca_de_arquivo(caminho)
                print('Licença carregada com sucesso.')
            except Exception as e:
                print('Erro ao carregar licença:', e)
                raise SystemExit(1)
            # manter cópia original antes da edição para detectar remoções
            original_payload = copy.deepcopy(payload)
            # permitir edição
            payload = _menu_edicao(payload)
            # regenerar token
            novo_token = gerar_licenca(
                payload.get('cnpjs', []),
                payload.get('ids_celular', []),
                payload.get('validade', ''),
                payload.get('nome_cliente', ''),
                payload.get('sql_servidor', ''),
                payload.get('sql_banco', ''),
            )

            # registrar/upsert no banco para CNPJs atuais
            try:
                registrar_tokens_por_cnpjs(payload.get('cnpjs', []), novo_token)
                print('✓ CNPJs registrados no banco com sucesso.')
            except Exception as e:
                print(f'⚠ Aviso: falha ao registrar token no banco: {e}')

            # remover CNPJs que foram removidos da licença
            try:
                orig = original_payload.get('cnpjs', [])
                removed = [c for c in orig if c not in payload.get('cnpjs', [])]
                if removed:
                    remover_cnpjs_do_db(removed)
                    print(f'✓ {len(removed)} CNPJ(s) removido(s) do banco.')
            except Exception as e:
                print(f'⚠ Aviso: falha ao remover CNPJs no banco: {e}')

            salvar_licenca(novo_token, caminho, payload_meta=payload)
            print('Licença atualizada e salva em', caminho)
        else:
            cnpjs = _input_cnpjs_inicial()
            ids_celular = []
            print("Digite os IDs de celular. Enter em branco para terminar:")
            while True:
                v = input("ID Celular: ").strip()
                if not v:
                    break
                if v not in ids_celular:
                    ids_celular.append(v)
            validade = input('Validade (YYYY-MM-DD ou ISO, vazio para sem validade): ').strip()
            # solicita nome do cliente (obrigatório, máx 30)
            nome_cliente = ''
            while True:
                nome_cliente = input('Nome do cliente (obrigatório, máx 30): ').strip()
                if not nome_cliente:
                    print('Nome do cliente é obrigatório.')
                    continue
                if len(nome_cliente) > 30:
                    print('Nome muito longo (máx 30 caracteres).')
                    continue
                break

            # solicita servidor SQL e banco (mesma lógica)
            sql_servidor = ''
            while True:
                sql_servidor = input('Servidor SQL (obrigatório, máx 30): ').strip()
                if not sql_servidor:
                    print('Servidor SQL é obrigatório.')
                    continue
                if len(sql_servidor) > 30:
                    print('Nome do servidor muito longo (máx 30 caracteres).')
                    continue
                break

            sql_banco = ''
            while True:
                sql_banco = input('Banco de dados (obrigatório, máx 30): ').strip()
                if not sql_banco:
                    print('Nome do banco é obrigatório.')
                    continue
                if len(sql_banco) > 30:
                    print('Nome do banco muito longo (máx 30 caracteres).')
                    continue
                break

            token = gerar_licenca(cnpjs, ids_celular, validade, nome_cliente, sql_servidor, sql_banco)
            # nome padrão do arquivo
            safe = ''.join(ch for ch in nome_cliente if (ch.isalnum() or ch in (' ', '_', '-'))).strip().replace(' ', '_')
            if not safe:
                safe = 'cliente'
            default_name = f"Licenca_CSCollectManager_{safe}.key"
            caminho = input(f"Salvar em (padrão '{default_name}'): ").strip() or default_name
            # salva também metadados no formato recomendado para o manager
            meta = {
                'cnpjs': cnpjs,
                'ids_celular': ids_celular,
                'validade': validade,
            }
            # salva arquivo e tenta registrar no banco
            try:
                registrar_tokens_por_cnpjs(cnpjs, token)
                print('✓ CNPJs registrados no banco com sucesso.')
            except Exception as e:
                print(f'⚠ Aviso: falha ao registrar token no banco: {e}')

            salvar_licenca(token, caminho, payload_meta=meta)
            print('Licença gerada e salva em', caminho)
    except KeyboardInterrupt:
        print('\nOperação cancelada.')
    except Exception as err:
        print('Erro:', err)

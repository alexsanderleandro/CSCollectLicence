import os
import json
import base64
import hmac
import hashlib
import secrets
import copy
import urllib.parse

import functools
import logging

# Importa módulo de criptografia para campos sensíveis
try:
    from encryption import encrypt_field, decrypt_field, is_encrypted
except ImportError:
    # Fallback se encryption não estiver disponível (compatibilidade)
    def encrypt_field(v):
        return v
    def decrypt_field(v):
        return v
    def is_encrypted(v):
        return False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _AESGCM_AVAILABLE = True
except ImportError:
    _AESGCM_AVAILABLE = False
try:
    import requests
except ImportError:
    requests = None
    import warnings
    warnings.warn(
        "Biblioteca 'requests' não instalada. Funcionalidades REST não estarão disponíveis.",
        ImportWarning,
        stacklevel=1
    )
except Exception:
    requests = None

try:
    from config import get_database_config
except ImportError:
    get_database_config = None
from datetime import datetime, date, timezone
from typing import Optional, List, Tuple, Dict, Any

# Logger para avisos e depuração
_logger = logging.getLogger("licenca")



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


@functools.lru_cache(maxsize=1)
def _derive_encryption_key() -> bytes:
    """Deriva chave AES-256 a partir de MASTER_KEY usando PBKDF2-HMAC-SHA256.

    R6: 100 000 iterações com salt fixo — mesmos parâmetros de mobile_activation.py.
    ATENÇÃO: qualquer mudança requer re-criptografar campos no banco Neon.
    """
    return hashlib.pbkdf2_hmac(
        'sha256',
        MASTER_KEY_BYTES,
        b'cscollect_aes_salt_v2',
        100_000,
        dklen=32,
    )


def _encrypt_field(plaintext: str) -> str:
    """Criptografa um campo de texto usando AES-256-GCM.

    Retorna string base64 no formato: base64(nonce[12] + ciphertext+tag).
    Retorna string vazia se `plaintext` for vazio/None.
    Lança RuntimeError se a biblioteca `cryptography` não estiver instalada.
    """
    if not plaintext:
        return ''
    if not _AESGCM_AVAILABLE:
        raise RuntimeError(
            'Biblioteca `cryptography` não instalada. Execute: pip install cryptography>=41.0.0'
        )
    key = _derive_encryption_key()
    nonce = os.urandom(12)  # 96 bits recomendados para GCM
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    return base64.b64encode(nonce + ct).decode('ascii')


def _decrypt_field(ciphertext: str) -> str:
    """Descriptografa um campo criptografado por `_encrypt_field`.

    Retorna string vazia se `ciphertext` for vazio/None.
    Lança RuntimeError se a biblioteca `cryptography` não estiver instalada.
    """
    if not ciphertext:
        return ''
    if not _AESGCM_AVAILABLE:
        raise RuntimeError(
            'Biblioteca `cryptography` não instalada. Execute: pip install cryptography>=41.0.0'
        )
    key = _derive_encryption_key()
    raw = base64.b64decode(ciphertext.encode('ascii'))
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode('utf-8')


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


def resolver_nomes(cnpjs: List[str], nomes: Any = None, nome_cliente: str = '') -> List[str]:
    """Devolve um nome por CNPJ, na mesma ordem, aplicando retrocompatibilidade.

    Licenças geradas antes do suporte multi-empresa têm um único `nome_cliente`
    para N CNPJs. Regras, em ordem:
      1) `nomes` já pareado com `cnpjs` -> usa direto;
      2) senão, split de `nome_cliente` por vírgula;
      3) sobrando 1 nome para N CNPJs -> replica em todas as posições;
      4) posição sem nome -> usa o próprio CNPJ como rótulo.
    """
    cnpjs = [str(c).strip() for c in (cnpjs or [])]

    if isinstance(nomes, str):
        lista = [n.strip() for n in nomes.split(',') if n.strip()]
    elif nomes:
        lista = [str(n).strip() for n in nomes if str(n).strip()]
    else:
        lista = []

    if not lista and nome_cliente:
        lista = [n.strip() for n in str(nome_cliente).split(',') if n.strip()]

    if len(lista) == 1 and len(cnpjs) > 1:
        lista = lista * len(cnpjs)

    return [lista[i] if i < len(lista) else cnpjs[i] for i in range(len(cnpjs))]


def serializar_licenca(
    token: str,
    payload_meta: Optional[Dict[str, Any]] = None,
    qtde_cnpjs: Optional[int] = None,
    qtde_devices: Optional[int] = None,
) -> str:
    """Retorna o conteúdo textual que será gravado no arquivo de licença.

    Campos sensíveis (api_authorization, api_database_url) são criptografados
    antes de serem salvos em disco.

    `qtde_cnpjs`/`qtde_devices` são gravados apenas no envelope JSON, para fins
    visuais/controle interno — NÃO fazem parte do token assinado (não afetam a
    validação da licença no APK/app desktop).
    """
    token = _ensure_token_complete(token)

    if payload_meta:
        # SEGURANÇA (R2): api_authorization e api_database_url são criptografados
        # no arquivo .key para evitar exposição de credenciais em texto puro.
        # Esses campos são descriptografados em runtime durante validação.
        _cnpjs = payload_meta.get("cnpjs") or payload_meta.get("cnpj") or []
        _ids = payload_meta.get("ids") or payload_meta.get("ids_celular") or []
        out = {
            "cnpjs": _cnpjs,
            "nomes": resolver_nomes(
                _cnpjs,
                payload_meta.get("nomes"),
                payload_meta.get("nome_cliente") or "",
            ),
            "ids": _ids,
            "token": token,
            "validade": payload_meta.get("validade"),
            "api_url": payload_meta.get("api_url") or "",
            "api_authorization": encrypt_field(payload_meta.get("api_authorization")),
            "api_database_url": encrypt_field(payload_meta.get("api_database_url")),
            "nome_cliente": payload_meta.get("nome_cliente") or "",
            "sql_servidor": payload_meta.get("sql_servidor") or "",
            "sql_banco": payload_meta.get("sql_banco") or "",
            "qtde_cnpjs": qtde_cnpjs if qtde_cnpjs is not None else len(_cnpjs),
            "qtde_devices": qtde_devices if qtde_devices is not None else len(_ids),
            "tipo_licenca": payload_meta.get("tipo_licenca") or "Lite",
        }
        return json.dumps(out, ensure_ascii=False, indent=2)

    return token


def gerar_licenca(
    cnpjs: List[str],
    ids_celular: List[str],
    validade: str,
    nomes: Any,
    sql_servidor: str,
    sql_banco: str,
    api_authorization: str,
    api_database_url: str,
    tipo_licenca: str = 'Lite',
) -> str:
    """Gera um token de licença.

    O token é uma string compacta e assinada que contém o payload JSON
    com os campos informados. Formato final:

        base64url(json_payload) + '.' + base64url(hmac_sha256_signature)

    Passos principais:
     1) Validações: exige pelo menos um CNPJ, pelo menos um ID de celular
         e um nome por CNPJ (máx 30 caracteres cada).
    2) Constrói o payload (lista de `cnpjs`, `nomes`, `ids_celular`, `validade` e metadados).
    3) Serializa o payload em JSON UTF-8.
    4) Calcula HMAC-SHA256 sobre os bytes do JSON usando `MASTER_KEY`.
    5) Codifica payload e assinatura em base64url e concatena com '.' — esse é o token.

    Observações de uso:
    - O token pode ser salvo em disco (por exemplo, em `licenca.key`) ou exibido
      para cópia/colagem. É a única informação necessária para validar a licença
      no lado do cliente, via `verificar_licenca`.
    - Mantemos `gerado_em` no payload para rastreabilidade.
    """
    if not api_authorization:
        raise ValueError("O campo 'api_authorization' é obrigatório e não pode ser vazio.")
    if not api_database_url:
        raise ValueError("O campo 'api_database_url' é obrigatório e não pode ser vazio.")

    # 1) Validações mínimas de entrada
    if not cnpjs:
        raise ValueError("É obrigatório informar pelo menos um CNPJ.")
    if not ids_celular:
        raise ValueError("É obrigatório informar pelo menos um ID de celular.")
    # valida os nomes: um por CNPJ, na mesma ordem
    if isinstance(nomes, str):
        nomes = [n.strip() for n in nomes.split(',')]
    nomes = [str(n).strip() for n in (nomes or [])]
    if not nomes or not any(nomes):
        raise ValueError("É obrigatório informar o nome do cliente.")
    if len(nomes) != len(cnpjs):
        raise ValueError(
            f"Informe um nome para cada CNPJ: {len(cnpjs)} CNPJ(s) e {len(nomes)} nome(s)."
        )
    for i, n in enumerate(nomes):
        if not n:
            raise ValueError(f"O nome do CNPJ {cnpjs[i]} não pode ser vazio.")
        if len(n) > 30:
            raise ValueError(
                f"O nome do cliente deve ter no máximo 30 caracteres: '{n}'."
            )
    nome_cliente = ','.join(nomes)

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

    # valida tipo de licença
    tipo_licenca = str(tipo_licenca).strip()
    if tipo_licenca not in ('Lite', 'Pro'):
        raise ValueError(f"tipo_licenca deve ser 'Lite' ou 'Pro', recebido: '{tipo_licenca}'.")

    # Valida formato da validade se fornecido
    if validade:
        try:
            if 'T' in validade or validade.endswith('Z'):
                datetime.fromisoformat(validade.replace('Z', '+00:00'))
            else:
                date.fromisoformat(validade)
        except ValueError:
            raise ValueError(f"Formato de validade inválido: '{validade}'. Use YYYY-MM-DD ou formato ISO 8601.")

    # 2) Monta o payload com os dados informados e metadados
    # registrar hora local com offset correto (ex: 2026-04-01T12:34:56+03:00)
    payload = {
        "cnpjs": cnpjs,
        "nomes": nomes,
        "ids_celular": ids_celular,
        "validade": validade,
        "nome_cliente": nome_cliente,
        "sql_servidor": sql_servidor,
        "sql_banco": sql_banco,
        "tipo_licenca": tipo_licenca,
        "gerado_em": datetime.now().astimezone().replace(microsecond=0).isoformat(),
    }
    # NOTA (correção 2026-07-02): api_authorization/api_database_url NÃO são
    # embutidos no payload do token. O token é apenas assinado (HMAC), não
    # criptografado, então qualquer valor aqui seria legível por qualquer um
    # via base64url-decode. Esses dois campos só devem existir no arquivo
    # .key criptografados via encrypt_field(), gravados por serializar_licenca().

    # 3) Serializa para JSON (bytes UTF-8)
    dados = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    # 4) Calcula assinatura HMAC-SHA256 usando a chave mestra
    assinatura = hmac.new(MASTER_KEY_BYTES, dados, hashlib.sha256).digest()

    # 5) Codifica em base64url sem padding e concatena para formar o token
    token = f"{_b64u_encode(dados)}.{_b64u_encode(assinatura)}"
    return token


def verificar_licenca(token: str, validar_validade: bool = True) -> Dict[str, Any]:
    """Verifica e valida um token de licença.

    Retorna o payload (dict) decodificado se a assinatura for válida e,
    se `validar_validade` for True, também verifica se a validade não expirou.

    Lança `ValueError` em casos de formato inválido, assinatura incorreta ou
    validade expirada. Pode lançar outras exceções de I/O/parse se houverem
    problemas ao decodificar o payload.
    """
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
                expirada = validade_dt < hoje
            else:
                # Assume formato YYYY-MM-DD
                validade_date = date.fromisoformat(val)
                expirada = validade_date < date.today()
        except ValueError:
            raise ValueError("Formato de validade desconhecido")

        if expirada:
            raise ValueError("Licença expirada")

    return payload


def salvar_licenca(
    token: str,
    caminho: str = "licenca.key",
    payload_meta: Optional[Dict[str, Any]] = None,
    qtde_cnpjs: Optional[int] = None,
    qtde_devices: Optional[int] = None,
) -> str:
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
    - qtde_cnpjs/qtde_devices: quantidades contratadas, gravadas apenas no
      envelope JSON (uso interno/visual, não fazem parte do token assinado).
    """
    conteudo = serializar_licenca(
        token, payload_meta=payload_meta, qtde_cnpjs=qtde_cnpjs, qtde_devices=qtde_devices
    )

    # R7: utf-8 garante compatibilidade com caracteres especiais em qualquer plataforma
    with open(caminho, "w", encoding='utf-8') as f:
        f.write(conteudo)

    return conteudo


def carregar_licenca_de_arquivo(caminho: str = "licenca.key") -> Tuple[Dict[str, Any], str]:
    """Lê token (ou JSON de manager) de `caminho`, verifica e retorna o payload (dict) e o token.

    Suporta dois formatos de arquivo:
    - Texto simples contendo o token.
    - JSON contendo pelo menos a chave `token` (ex.: manager key).
    """
    try:
        with open(caminho, "rb") as f:
            raw = f.read()
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
                # Descriptografa campos sensíveis ao carregar
                api_auth_raw = doc.get('api_authorization', '')
                api_db_raw = doc.get('api_database_url', '')
                
                payload = {
                    'cnpjs': cnpjs,
                    'nomes': resolver_nomes(cnpjs, doc.get('nomes'), doc.get('nome_cliente', '')),
                    'ids_celular': ids,
                    'validade': doc.get('validade', ''),
                    'nome_cliente': doc.get('nome_cliente', ''),
                    'sql_servidor': doc.get('sql_servidor', ''),
                    'sql_banco': doc.get('sql_banco', ''),
                    'api_url': doc.get('api_url', ''),
                    # Descriptografa se estiver criptografado
                    'api_authorization': decrypt_field(api_auth_raw) if is_encrypted(api_auth_raw) else api_auth_raw,
                    'api_database_url': decrypt_field(api_db_raw) if is_encrypted(api_db_raw) else api_db_raw,
                    # Uso interno/visual — ausente em licenças antigas: cai para a contagem real
                    'qtde_cnpjs': doc.get('qtde_cnpjs') if doc.get('qtde_cnpjs') is not None else len(cnpjs),
                    'qtde_devices': doc.get('qtde_devices') if doc.get('qtde_devices') is not None else len(ids),
                    'tipo_licenca': doc.get('tipo_licenca') or 'Lite',
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
            except Exception as e:
                # Token em formato externo (ex: CSCollect Manager) — tenta decodificar
                # o payload da primeira parte do token sem verificar assinatura
                if isinstance(e, ValueError) and str(e) == "Licença expirada":
                    _logger.warning(f"Licença expirada, tentando fallback: {e}")
                else:
                    _logger.warning(f"Assinatura do token inválida ou erro na verificação, tentando fallback: {e}")
                try:
                    parte_payload = token.split('.')[0]
                    import base64 as _b64
                    padding = '=' * (-len(parte_payload) % 4)
                    raw_payload = _b64.urlsafe_b64decode((parte_payload + padding).encode('ascii'))
                    doc_token = json.loads(raw_payload.decode('utf-8'))
                    for k in ('nome_cliente', 'nomes', 'sql_servidor', 'sql_banco', 'validade', 'cnpjs', 'ids_celular'):
                        if not payload.get(k) and doc_token.get(k):
                            payload[k] = doc_token[k]
                except Exception:
                    pass
        return payload, token or ''

    if not token:
        token = conteudo

    payload = verificar_licenca(token)
    return payload, token


def _resolve_db_config() -> dict:
    """Resolve a configuração do banco a partir de config.py ou variáveis de ambiente.
    
    Raises:
        RuntimeError: Se nenhuma configuração for encontrada.
    """
    config = get_database_config() if get_database_config else None
    if not config:
        db_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
        rest_url = os.environ.get('NEON_REST_URL') or os.environ.get('NEON_REST_API_URL')
        if db_url:
            config = {'type': 'sql', 'url': db_url}
        elif rest_url:
            config = {'type': 'rest', 'url': rest_url, 'api_key': os.environ.get('NEON_API_KEY')}
        else:
            # Fallback para parâmetros individuais NEON_*
            host = os.environ.get('NEON_HOST')
            db = os.environ.get('NEON_DB') or os.environ.get('NEON_DATABASE')
            user = os.environ.get('NEON_USER')
            password = os.environ.get('NEON_PASSWORD')
            port = os.environ.get('NEON_PORT') or os.environ.get('NEON_PORTA') or '5432'
            if host and db and user and password:
                dsn = f"host={host} port={port} dbname={db} user={user} password={password}"
                config = {'type': 'sql', 'url': dsn}
    if not config:
        raise RuntimeError('Configuração de banco não encontrada. Configure DATABASE_URL ou use config.py.')
    return config


def _get_db_dsn_from_env() -> Optional[str]:
    """Constrói DSN a partir da configuração unificada."""
    try:
        config = _resolve_db_config()
        if config.get('type') == 'sql':
            return config.get('url')
    except Exception:
        pass
    return None


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


def _fetch_all(query: str) -> Tuple[List[str], List[tuple]]:
    """Executa uma consulta somente leitura e retorna (colunas, linhas).

    Usado pelo painel administrativo (leitura). Colunas são obtidas
    dinamicamente via `cursor.description`, então funcionam mesmo para
    tabelas cujo schema completo não está documentado neste repositório
    (ex.: `activation_tokens`).
    """
    dsn = _get_db_dsn_from_env()
    if not dsn:
        raise RuntimeError('Credenciais do banco não encontradas nas variáveis de ambiente (DATABASE_URL ou NEON_*).')

    db = None
    try:
        import psycopg2 as db
    except Exception:
        try:
            import psycopg as db
        except Exception:
            raise RuntimeError('Instale psycopg2 ou psycopg para consultar o banco (pip install psycopg2-binary).')

    conn = db.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            colunas = [desc[0] for desc in cur.description]
            linhas = cur.fetchall()
            return colunas, [tuple(row) for row in linhas]
    finally:
        conn.close()


def listar_clientes() -> Tuple[List[str], List[tuple]]:
    """Lista todos os registros da tabela `clientes` (somente leitura).

    Retorna (colunas, linhas) para popular o painel administrativo.
    """
    return _fetch_all("SELECT * FROM clientes ORDER BY dataalteracao DESC NULLS LAST;")


def listar_activation_tokens() -> Tuple[List[str], List[tuple]]:
    """Lista todos os registros da tabela `activation_tokens` (somente leitura).

    Retorna (colunas, linhas) para popular o painel administrativo.
    """
    return _fetch_all("SELECT * FROM activation_tokens ORDER BY criado_em DESC;")


def registrar_tokens_por_cnpjs(cnpjs: List[str], token: str, arq_licenca: Optional[str] = None) -> Any:
    """Insere/atualiza o `token` para cada CNPJ na tabela `clientes`.

    Usa INSERT ... ON CONFLICT (cnpj) DO UPDATE SET token = EXCLUDED.token;
    Prioridade: env DATABASE_URL > env REST > JSON config
    """
    if not cnpjs:
        return
    
    db_config = _resolve_db_config()
    token = _ensure_token_complete(token)

    # Executa conforme o tipo
    if db_config['type'] == 'sql':
        statements = []
        q = (
            "INSERT INTO clientes (cnpj, token, arq_licenca, ativo, reginclusao, dataalteracao) "
            "VALUES (%s, %s, %s, true, now(), now()) "
            "ON CONFLICT (cnpj) DO UPDATE SET token = EXCLUDED.token, arq_licenca = EXCLUDED.arq_licenca, dataalteracao = now();"
        )
        for c in cnpjs:
            statements.append((q, (c, token, arq_licenca)))
        return _exec_db_statements(statements)
    elif db_config['type'] == 'rest':
        return _registrar_tokens_por_cnpjs_rest(db_config['url'], cnpjs, token, db_config.get('api_key'), arq_licenca=arq_licenca)
    else:
        raise RuntimeError('Tipo de configuração desconhecido.')


def deletar_registro_por_cnpjs(cnpjs_str: str) -> Any:
    """Deleta um registro da tabela `clientes` pela chave primária cnpj.
    
    Parâmetros:
    - cnpjs_str: string com CNPJs separados por vírgula (chave primária)
    """
    if not cnpjs_str:
        return
    
    db_config = _resolve_db_config()
    
    # Executa DELETE
    q = "DELETE FROM clientes WHERE cnpj = %s;"
    statements = [(q, (cnpjs_str,))]
    return _exec_db_statements(statements)


def registrar_tokens_por_cnpjs_single(
    cnpjs_str: str,
    ids_str: str,
    token: str,
    validade: str = '',
    ativa: bool = True,
    nome_cliente: str = '',
    sql_servidor: str = '',
    sql_banco: str = '',
    api_authorization: str = '',
    api_database_url: str = '',
    arq_licenca: Optional[str] = None,
    qtde_cnpjs: Optional[int] = None,
    qtde_devices: Optional[int] = None,
    tipo_licenca: str = 'Lite',
) -> Any:
    """Insere/atualiza um ÚNICO registro na tabela `clientes` com CNPJs e IDs separados por vírgula.

    `qtde_cnpjs`/`qtde_devices` são gravados apenas para uso interno/visual
    (controle de quantos CNPJs/devices foram liberados) — não afetam o token.
    `tipo_licenca` ('Lite'/'Pro') faz parte do token assinado — aqui é apenas
    espelhado na coluna para permitir consulta/filtro no painel administrativo.
    """
    if not cnpjs_str:
        return

    db_config = _resolve_db_config()
    token = _ensure_token_complete(token)

    if qtde_cnpjs is None:
        qtde_cnpjs = len([c for c in cnpjs_str.split(',') if c.strip()])
    if qtde_devices is None:
        qtde_devices = len([i for i in ids_str.split(',') if i.strip()])

    # Criptografa em repouso os campos sensíveis ANTES de enviar ao banco
    api_authorization_enc = _encrypt_field(api_authorization) if api_authorization else None
    api_database_url_enc  = _encrypt_field(api_database_url)  if api_database_url  else None

    # Executa SQL
    if db_config['type'] == 'rest':
        return _registrar_tokens_single_rest(
            db_config['url'], cnpjs_str, ids_str, token, validade,
            api_key=db_config.get('api_key'),
            nome_cliente=nome_cliente, sql_servidor=sql_servidor, sql_banco=sql_banco,
            api_authorization_enc=api_authorization_enc,
            api_database_url_enc=api_database_url_enc,
            arq_licenca=arq_licenca,
            qtde_cnpjs=qtde_cnpjs, qtde_devices=qtde_devices,
            tipo_licenca=tipo_licenca,
        )
    q = (
        "INSERT INTO clientes (cnpj, idcelular, token, validade, ativo, nome_cliente, sql_servidor, sql_banco, api_authorization, api_database_url, arq_licenca, qtde_cnpjs, qtde_devices, tipo_licenca, reginclusao, dataalteracao) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now()) "
        "ON CONFLICT (cnpj) DO UPDATE SET idcelular = EXCLUDED.idcelular, token = EXCLUDED.token, "
        "validade = EXCLUDED.validade, ativo = EXCLUDED.ativo, nome_cliente = EXCLUDED.nome_cliente, "
        "sql_servidor = EXCLUDED.sql_servidor, sql_banco = EXCLUDED.sql_banco, "
        "api_authorization = EXCLUDED.api_authorization, api_database_url = EXCLUDED.api_database_url, "
        "arq_licenca = EXCLUDED.arq_licenca, qtde_cnpjs = EXCLUDED.qtde_cnpjs, qtde_devices = EXCLUDED.qtde_devices, "
        "tipo_licenca = EXCLUDED.tipo_licenca, "
        "dataalteracao = now();"
    )
    # converte string vazia de validade para NULL para colunas do tipo DATE
    validade_param = validade if validade else None
    statements = [(q, (
        cnpjs_str, ids_str, token, validade_param, ativa,
        nome_cliente, sql_servidor or None, sql_banco or None,
        api_authorization_enc, api_database_url_enc, arq_licenca,
        qtde_cnpjs, qtde_devices, tipo_licenca,
    ))]
    return _exec_db_statements(statements)


def _registrar_tokens_single_rest(base_url, cnpjs_str, ids_str, token, validade='', api_key=None, nome_cliente='', sql_servidor='', sql_banco='', api_authorization_enc=None, api_database_url_enc=None, arq_licenca=None, qtde_cnpjs=None, qtde_devices=None, tipo_licenca='Lite'):
    """Registra via REST um único registro com CNPJs e IDs separados por vírgula.
    
    `api_authorization_enc` e `api_database_url_enc` devem chegar já criptografados
    (saída de `_encrypt_field`). São armazenados diretamente como texto no banco.
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
    payload = {
        'cnpj': cnpjs_str,
        'idcelular': ids_str,
        'token': token,
        'validade': validade if validade else None,
        'ativo': True,
        'nome_cliente': nome_cliente or None,
        'sql_servidor': sql_servidor or None,
        'sql_banco': sql_banco or None,
        'api_authorization': api_authorization_enc,   # já criptografado
        'api_database_url': api_database_url_enc,     # já criptografado
        'arq_licenca': arq_licenca,
        'qtde_cnpjs': qtde_cnpjs,
        'qtde_devices': qtde_devices,
        'tipo_licenca': tipo_licenca,
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


def _registrar_tokens_por_cnpjs_rest(base_url, cnpjs, token, api_key=None, arq_licenca=None):
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
    payload = [
        {'cnpj': c, 'token': token, 'arq_licenca': arq_licenca, 'ativo': True, 'reginclusao': now_iso, 'dataalteracao': now_iso}
        for c in cnpjs
    ]
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f'Erro REST ({resp.status_code}): {resp.text}')
        return resp.json() if resp.text else None
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f'Falha na conexão REST: {e}')


def gerar_activation_token(cnpjs, device_id='', ttl_horas=24, gerado_por='', tipo_licenca='Lite'):
    """Gera um token de ativação avulso para uso no fluxo "Ativar Online".

    O token raw (43 chars URL-safe) é retornado UMA única vez para ser
    exibido/enviado ao cliente. Apenas seu hash SHA-256 é armazenado no banco.

    Parâmetros:
    - cnpjs: lista de CNPJs (ou string com um CNPJ) para os quais o token é válido.
    - device_id: ID do celular do cliente (obtido na primeira abertura do app).
    - ttl_horas: tempo de vida em horas (padrão 24h).
    - gerado_por: identificação do operador (para auditoria).
    - tipo_licenca: 'Lite' ou 'Pro' — plano associado a este token de ativação.

    Retorna: (raw_token: str, expira_em: datetime)
    Lança RuntimeError se a inserção no banco falhar.
    """
    tipo_licenca = str(tipo_licenca).strip()
    if tipo_licenca not in ('Lite', 'Pro'):
        raise ValueError(f"tipo_licenca deve ser 'Lite' ou 'Pro', recebido: '{tipo_licenca}'.")
    def _normalizar_lista(valor):
        if valor is None:
            return []
        if isinstance(valor, str):
            partes = valor.replace(';', ',').replace('\n', ',').split(',')
        else:
            partes = []
            for item in valor:
                partes.extend(str(item).replace(';', ',').replace('\n', ',').split(','))

        vistos = set()
        saida = []
        for item in partes:
            item = item.strip()
            if item and item not in vistos:
                vistos.add(item)
                saida.append(item)
        return saida

    cnpjs = _normalizar_lista(cnpjs)
    device_ids = _normalizar_lista(device_id)
    if not cnpjs:
        raise ValueError("Informe pelo menos um CNPJ para o token de ativação.")

    if not device_ids:
        raise ValueError("Informe pelo menos um Device ID para o token de ativacao.")

    raw_token  = secrets.token_urlsafe(32)      # 43 chars base64url
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    cnpj_str   = ','.join(cnpjs)
    device_id_str = ','.join(device_ids)

    from datetime import timezone as _tz, timedelta as _td
    now_utc    = datetime.now(_tz.utc)
    expira_em  = now_utc + _td(hours=ttl_horas)

    # Determinar configuração do banco
    db_config = _resolve_db_config()

    if db_config['type'] == 'sql':
        try:
            import sqlalchemy as _sa
            engine = _sa.create_engine(db_config['url'], pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(_sa.text("""
                    INSERT INTO activation_tokens
                        (cnpj, token_hash, criado_em, expira_em, device_id_autorizado, gerado_por, tipo_licenca)
                    VALUES (:cnpj, :hash, :criado, :expira, :dev, :gby, :tipo)
                """), {
                    'cnpj': cnpj_str,
                    'hash': token_hash,
                    'criado': now_utc,
                    'expira': expira_em,
                    'dev': device_id_str,
                    'gby': gerado_por or '',
                    'tipo': tipo_licenca,
                })
                conn.commit()
        except Exception as e:
            raise RuntimeError(f'Erro ao inserir activation_token no banco: {e}')
    else:
        raise RuntimeError('gerar_activation_token: suporta apenas db_config type=sql no momento.')

    return raw_token, expira_em


def remover_cnpjs_do_db(cnpjs: List[str]) -> Any:
    """Remove registros dos CNPJs informados da tabela `clientes`."""
    if not cnpjs:
        return
    
    db_config = _resolve_db_config()
    
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
    """Modo interativo: lê pares CNPJ/nome do usuário até linha em branco.

    Retorna `(cnpjs, nomes)` — duas listas pareadas por posição, na ordem informada.
    """
    cnpjs = []
    nomes = []
    print("Digite os CNPJs (apenas dígitos) e o nome da empresa. Enter em branco no CNPJ para terminar:")
    while True:
        v = input("CNPJ: ").strip()
        if not v:
            break
        # simples normalização: manter apenas dígitos
        v_clean = ''.join(ch for ch in v if ch.isdigit())
        if not v_clean:
            continue
        nome = _input_nome_empresa(v_clean)
        cnpjs.append(v_clean)
        nomes.append(nome)
    return cnpjs, nomes


def _input_nome_empresa(cnpj: str) -> str:
    """Lê o nome da empresa de um CNPJ, aplicando a mesma regra de `gerar_licenca`."""
    while True:
        nome = input(f'Nome da empresa do CNPJ {cnpj} (obrigatório, máx 30): ').strip()
        if not nome:
            print('O nome é obrigatório.')
            continue
        if len(nome) > 30:
            print('O nome deve ter no máximo 30 caracteres.')
            continue
        return nome


def _menu_edicao(payload: dict) -> dict:
    """Menu de edição interativo para ajustar o payload da licença.

    Permite adicionar/remover CNPJs (com o nome da empresa) e IDs de celular,
    atualizar validade, e retornar o payload modificado.
    """
    # Garante `nomes` pareado com `cnpjs` mesmo em licenças antigas (1 nome p/ N CNPJs)
    payload['nomes'] = resolver_nomes(
        payload.get('cnpjs', []), payload.get('nomes'), payload.get('nome_cliente', '')
    )
    while True:
        print("\nEstado atual da licença:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print('\nAções: [a]dicionar CNPJ, [r]emover CNPJ, [c]adicionar ID celular, [d]remover ID celular, [u]pdate validade, [s]alvar e sair, [q]cancelar')
        try:
            op = input('Escolha: ').strip().lower()
        except EOFError:
            print('\nEntrada encerrada (EOF). Saindo.')
            raise KeyboardInterrupt('Edição cancelada devido a EOF')
        if op == 'a':
            v = input('CNPJ a adicionar: ').strip()
            v_clean = ''.join(ch for ch in v if ch.isdigit())
            if v_clean and v_clean not in payload.get('cnpjs', []):
                payload.setdefault('cnpjs', []).append(v_clean)
                payload.setdefault('nomes', []).append(_input_nome_empresa(v_clean))
                print('CNPJ adicionado.')
            else:
                print('CNPJ inválido ou já presente.')
        elif op == 'r':
            v = input('CNPJ a remover: ').strip()
            v_clean = ''.join(ch for ch in v if ch.isdigit())
            if v_clean in payload.get('cnpjs', []):
                # remove o nome da mesma posição para manter as listas pareadas
                idx = payload['cnpjs'].index(v_clean)
                payload['cnpjs'].pop(idx)
                if idx < len(payload.get('nomes', [])):
                    payload['nomes'].pop(idx)
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

            # api_authorization e api_database_url são obrigatórios; solicita se ausentes
            api_authorization = payload.get('api_authorization', '')
            while not api_authorization:
                api_authorization = input('Token de autorização da API (obrigatório): ').strip()
            api_database_url = payload.get('api_database_url', '')
            while not api_database_url:
                api_database_url = input('URL do banco de dados da API (obrigatório): ').strip()
            payload['api_authorization'] = api_authorization
            payload['api_database_url'] = api_database_url

            # regenerar token
            novo_token = gerar_licenca(
                payload.get('cnpjs', []),
                payload.get('ids_celular', []),
                payload.get('validade', ''),
                payload.get('nomes', []),
                payload.get('sql_servidor', ''),
                payload.get('sql_banco', ''),
                api_authorization,
                api_database_url,
            )

            conteudo_licenca = salvar_licenca(novo_token, caminho, payload_meta=payload)
            print('Licença atualizada e salva em', caminho)

            # registrar/upsert no banco para CNPJs atuais
            try:
                registrar_tokens_por_cnpjs(payload.get('cnpjs', []), novo_token, arq_licenca=conteudo_licenca)
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
        else:
            cnpjs, nomes = _input_cnpjs_inicial()
            ids_celular = []
            print("Digite os IDs de celular. Enter em branco para terminar:")
            while True:
                v = input("ID Celular: ").strip()
                if not v:
                    break
                if v not in ids_celular:
                    ids_celular.append(v)
            validade = input('Validade (YYYY-MM-DD ou ISO, vazio para sem validade): ').strip()
            # os nomes já foram informados junto de cada CNPJ em _input_cnpjs_inicial()

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

            api_authorization = ''
            while not api_authorization:
                api_authorization = input('Token de autorização da API (obrigatório): ').strip()
            api_database_url = ''
            while not api_database_url:
                api_database_url = input('URL do banco de dados da API (obrigatório): ').strip()

            token = gerar_licenca(
                cnpjs, ids_celular, validade, nomes, sql_servidor, sql_banco,
                api_authorization, api_database_url,
            )
            # nome padrão do arquivo: primeira empresa da licença
            _nome_arq = nomes[0] if nomes else ''
            safe = ''.join(ch for ch in _nome_arq if (ch.isalnum() or ch in (' ', '_', '-'))).strip().replace(' ', '_')
            if not safe:
                safe = 'cliente'
            default_name = f"Licenca_CSCollectManager_{safe}.key"
            caminho = input(f"Salvar em (padrão '{default_name}'): ").strip() or default_name
            # salva também metadados no formato recomendado para o manager
            meta = {
                'cnpjs': cnpjs,
                'nomes': nomes,
                'nome_cliente': ','.join(nomes),
                'ids_celular': ids_celular,
                'validade': validade,
                'sql_servidor': sql_servidor,
                'sql_banco': sql_banco,
                'api_authorization': api_authorization,
                'api_database_url': api_database_url,
            }
            conteudo_licenca = salvar_licenca(token, caminho, payload_meta=meta)
            print('Licença gerada e salva em', caminho)

            # salva arquivo e tenta registrar no banco
            try:
                registrar_tokens_por_cnpjs(cnpjs, token, arq_licenca=conteudo_licenca)
                print('✓ CNPJs registrados no banco com sucesso.')
            except Exception as e:
                print(f'⚠ Aviso: falha ao registrar token no banco: {e}')
    except KeyboardInterrupt:
        print('\nOperação cancelada.')
    except Exception as err:
        print('Erro:', err)

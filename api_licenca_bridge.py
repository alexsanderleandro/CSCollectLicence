import json
import os
import urllib.parse
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

try:
    import psycopg
except Exception:
    psycopg = None

try:
    from config import load_config
except ImportError:
    load_config = None


def _load_local_config():
    if not load_config:
        return {}
    try:
        return load_config() or {}
    except Exception:
        return {}


def _get_runtime_config():
    local_config = _load_local_config()
    return {
        'database_url': os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL') or local_config.get('database_url'),
        'rest_url': os.environ.get('NEON_REST_URL') or os.environ.get('NEON_REST_API_URL') or local_config.get('neon_rest_url') or local_config.get('rest_url'),
        'rest_api_key': os.environ.get('NEON_API_KEY') or local_config.get('neon_api_key') or local_config.get('rest_api_key'),
        'bridge_token': os.environ.get('LICENSE_API_TOKEN') or os.environ.get('LICENCE_API_TOKEN') or local_config.get('license_api_token') or local_config.get('licence_api_token'),
        'host': os.environ.get('LICENSE_API_HOST') or local_config.get('license_api_host') or '0.0.0.0',
        'port': int(os.environ.get('LICENSE_API_PORT') or local_config.get('license_api_port') or 8080),
    }


def _split_csv(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(',') if item.strip()]


def _sanitize_filename(text):
    safe = ''.join(ch for ch in str(text or 'cliente') if ch.isalnum() or ch in (' ', '_', '-')).strip()
    safe = safe.replace(' ', '_')
    return safe or 'cliente'


def _parse_validade(value):
    if not value:
        return None
    raw_value = str(value).strip()
    if not raw_value:
        return None
    if 'T' in raw_value or raw_value.endswith('Z'):
        normalized = raw_value.replace('Z', '+00:00')
        return datetime.fromisoformat(normalized).date()
    return date.fromisoformat(raw_value)


def _validade_expirada(value):
    validade = _parse_validade(value)
    if validade is None:
        return False
    return validade < date.today()


def _matches_cnpj(row, cnpj):
    return cnpj in _split_csv(row.get('cnpj'))


def _matches_id_celular(row, id_celular):
    if not id_celular:
        return True
    return id_celular in _split_csv(row.get('idcelular'))


def _build_license_content(row):
    arq_licenca = row.get('arq_licenca')
    if arq_licenca:
        return str(arq_licenca), 'arq_licenca'
    token = row.get('token')
    if token:
        return str(token), 'token'
    raise LookupError('Registro encontrado, mas não possui arquivo de licença nem token.')


def _database_not_configured_message():
    return 'Configure DATABASE_URL/NEON_DATABASE_URL ou NEON_REST_URL + NEON_API_KEY para a API ponte.'


def _fetch_cliente_sql(database_url, cnpj):
    query = (
        'SELECT cnpj, idcelular, token, arq_licenca, validade, ativo, nome_cliente, dataalteracao '
        'FROM clientes '
        'WHERE cnpj = %s OR cnpj LIKE %s OR cnpj LIKE %s OR cnpj LIKE %s '
        'ORDER BY dataalteracao DESC NULLS LAST '
        'LIMIT 20;'
    )
    params = (cnpj, f'%,{cnpj}', f'{cnpj},%', f'%,{cnpj},%')

    if psycopg is not None:
        with psycopg.connect(database_url) as connection:
            with connection.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                for row in rows:
                    if _matches_cnpj(row, cnpj):
                        return dict(row)
                return None

    raise RuntimeError('Instale psycopg[binary] para consultar o banco via SQL direto.')


def _fetch_cliente_rest(rest_url, api_key, cnpj):
    if not api_key:
        raise RuntimeError('NEON_API_KEY é obrigatório para consultar a API REST do Neon.')

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json',
    }
    params = {
        'select': 'cnpj,idcelular,token,arq_licenca,validade,ativo,nome_cliente,dataalteracao',
        'cnpj': f'ilike.*{cnpj}*',
        'order': 'dataalteracao.desc.nullslast',
        'limit': '20',
    }
    response = requests.get(rest_url.rstrip('/') + '/clientes', headers=headers, params=params, timeout=30)
    if not response.ok:
        raise RuntimeError(f'Erro REST ({response.status_code}): {response.text}')

    rows = response.json() or []
    for row in rows:
        if _matches_cnpj(row, cnpj):
            return row
    return None


def buscar_cliente_por_cnpj(cnpj):
    runtime_config = _get_runtime_config()
    database_url = runtime_config.get('database_url')
    rest_url = runtime_config.get('rest_url')

    if database_url:
        return _fetch_cliente_sql(database_url, cnpj)
    if rest_url:
        return _fetch_cliente_rest(rest_url, runtime_config.get('rest_api_key'), cnpj)
    raise RuntimeError(_database_not_configured_message())


class LicenseBridgeHandler(BaseHTTPRequestHandler):
    server_version = 'CSCollectLicenseBridge/1.0'

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip('/') or '/'
        query = urllib.parse.parse_qs(parsed_url.query)

        try:
            if path == '/health':
                self._send_json(200, {'status': 'ok', 'service': 'license-bridge'})
                return
            if path == '/licencas/metadata':
                self._handle_metadata(query)
                return
            if path == '/licencas/download':
                self._handle_download(query)
                return
            self._send_json(404, {'error': 'Endpoint não encontrado.'})
        except PermissionError as exc:
            self._send_json(401, {'error': str(exc)})
        except LookupError as exc:
            self._send_json(404, {'error': str(exc)})
        except ValueError as exc:
            self._send_json(400, {'error': str(exc)})
        except RuntimeError as exc:
            self._send_json(500, {'error': str(exc)})
        except Exception as exc:
            self._send_json(500, {'error': f'Erro interno: {exc}'})

    def _handle_metadata(self, query):
        self._authorize_if_needed()
        cnpj = self._require_query_value(query, 'cnpj')
        id_celular = self._optional_query_value(query, 'id_celular')
        row = self._load_valid_cliente(cnpj, id_celular)
        conteudo_licenca, origem = _build_license_content(row)

        response = {
            'cnpj': row.get('cnpj'),
            'idcelular': row.get('idcelular'),
            'nome_cliente': row.get('nome_cliente'),
            'validade': row.get('validade'),
            'ativo': bool(row.get('ativo', False)),
            'origem_arquivo': origem,
            'tamanho_bytes': len(conteudo_licenca.encode('cp1252', errors='replace')),
            'download_url': f'/licencas/download?cnpj={urllib.parse.quote(cnpj)}',
        }
        if id_celular:
            response['download_url'] += f'&id_celular={urllib.parse.quote(id_celular)}'
        self._send_json(200, response)

    def _handle_download(self, query):
        self._authorize_if_needed()
        cnpj = self._require_query_value(query, 'cnpj')
        id_celular = self._optional_query_value(query, 'id_celular')
        row = self._load_valid_cliente(cnpj, id_celular)
        conteudo_licenca, _ = _build_license_content(row)

        nome_cliente = row.get('nome_cliente') or cnpj
        filename = f'Licenca_CSCollectManager_{_sanitize_filename(nome_cliente)}.key'
        payload = conteudo_licenca.encode('cp1252', errors='replace')

        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _load_valid_cliente(self, cnpj, id_celular):
        row = buscar_cliente_por_cnpj(cnpj)
        if not row:
            raise LookupError('Licença não encontrada para o CNPJ informado.')
        if not bool(row.get('ativo', False)):
            raise LookupError('Licença encontrada, mas está desativada.')
        if _validade_expirada(row.get('validade')):
            raise LookupError('Licença encontrada, mas está expirada.')
        if not _matches_id_celular(row, id_celular):
            raise LookupError('ID de celular não autorizado para esta licença.')
        return row

    def _authorize_if_needed(self):
        bridge_token = _get_runtime_config().get('bridge_token')
        if not bridge_token:
            return
        auth_header = self.headers.get('Authorization', '')
        expected = f'Bearer {bridge_token}'
        if auth_header != expected:
            raise PermissionError('Não autorizado.')

    def _require_query_value(self, query, key):
        value = self._optional_query_value(query, key)
        if not value:
            raise ValueError(f'Parâmetro obrigatório ausente: {key}')
        return value

    def _optional_query_value(self, query, key):
        values = query.get(key) or []
        if not values:
            return None
        value = str(values[0]).strip()
        return value or None

    def _send_json(self, status_code, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format_string, *args):
        return


def run_server():
    runtime_config = _get_runtime_config()
    server = ThreadingHTTPServer((runtime_config['host'], runtime_config['port']), LicenseBridgeHandler)
    host = runtime_config['host']
    port = runtime_config['port']
    print(f'API ponte de licença ouvindo em http://{host}:{port}')
    server.serve_forever()


if __name__ == '__main__':
    run_server()

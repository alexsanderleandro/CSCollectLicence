import os
import json
import base64
import hmac
import hashlib
import secrets
from datetime import datetime, date, timezone


# Tenta carregar variáveis de ambiente a partir de um arquivo .env, se disponível
try:
    from dotenv import load_dotenv

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


def gerar_licenca(cnpjs, ids_celular, validade):
    """Gera um token de licença.

    O token é uma string compacta e assinada que contém o payload JSON
    com os campos informados. Formato final:

        base64url(json_payload) + '.' + base64url(hmac_sha256_signature)

    Passos principais:
    1) Validações: exige pelo menos um CNPJ e pelo menos um ID de celular.
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

    # 2) Monta o payload com os dados informados e metadados
    payload = {
        "cnpjs": cnpjs,
        "ids_celular": ids_celular,
        "validade": validade,
        "gerado_em": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
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


def salvar_licenca(token, caminho="licenca.key"):
    """Salva o token de licença no arquivo especificado.

    Parâmetros:
    - token: string do token gerado por `gerar_licenca`.
    - caminho: caminho do arquivo onde o token será gravado.
    """
    with open(caminho, "w", encoding='utf-8') as f:
        f.write(token)


def carregar_licenca_de_arquivo(caminho="licenca.key"):
    """Lê token de `caminho`, verifica e retorna o payload (dict)."""
    try:
        with open(caminho, "r", encoding='utf-8') as f:
            token = f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    payload = verificar_licenca(token)
    return payload, token


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
            # permitir edição
            payload = _menu_edicao(payload)
            # regenerar token
            novo_token = gerar_licenca(payload.get('cnpjs', []), payload.get('ids_celular', []), payload.get('validade', ''))
            salvar_licenca(novo_token, caminho)
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
            token = gerar_licenca(cnpjs, ids_celular, validade)
            caminho = input("Salvar em (padrão 'licenca.key'): ").strip() or 'licenca.key'
            salvar_licenca(token, caminho)
            print('Licença gerada e salva em', caminho)
    except KeyboardInterrupt:
        print('\nOperação cancelada.')
    except Exception as err:
        print('Erro:', err)

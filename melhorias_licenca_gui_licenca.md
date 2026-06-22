# Melhorias para `licenca.py` e `gui_licenca.py`

---

## 📁 `licenca.py`

---

## 🔴 Prioridade Alta

### 1. `MASTER_KEY` exposta como variável global em memória sem proteção
- **Problema:** `MASTER_KEY_BYTES` fica em memória como objeto Python global acessível por
  qualquer parte do processo, incluindo bibliotecas de terceiros. Além disso,
  `_derive_encryption_key()` é chamado a cada operação sem cache seguro — se a função
  for chamada frequentemente, o overhead de 100 000 iterações PBKDF2 se torna significativo.
- **Solução:** Usar `functools.lru_cache` com `maxsize=1` para memoizar a chave derivada,
  e nunca expor `MASTER_KEY` como string em variável global — zerar a variável após derivação:
  ```python
  import functools

  @functools.lru_cache(maxsize=1)
  def _derive_encryption_key() -> bytes:
      return hashlib.pbkdf2_hmac(
          'sha256', MASTER_KEY_BYTES,
          b'cscollect_aes_salt_v2', 100_000, dklen=32
      )
Impacto: Segurança e Performance — chave derivada apenas uma vez por processo.
2. verificar_licenca tem bloco except Exception as e: raise desnecessário
Problema: O bloco final except Exception as e: raise não adiciona nenhum tratamento — apenas relança a exceção original, mas mascara o traceback real em alguns contextos de depuração:
python


except Exception as e:
    raise  # <- sem valor algum
Solução: Remover o bloco try/except externo ou substituí-lo por logging antes de relançar:
python


def verificar_licenca(token, validar_validade=True):
    parts = token.split('.')
    if len(parts) != 2:
        raise ValueError("Formato de token inválido")
    # ... restante sem try/except externo desnecessário
Impacto: Clareza e Debugabilidade — stack traces mais limpos.
3. carregar_licenca_de_arquivo decodifica payload sem verificar assinatura em fallback
Problema: Quando verificar_licenca(token) falha, o código silenciosamente decodifica o payload da primeira parte do token sem validar a assinatura:
python


except Exception:
    try:
        parte_payload = token.split('.')[0]
        # Decodifica sem verificar assinatura!
        raw_payload = _b64.urlsafe_b64decode(...)
        doc_token = json.loads(raw_payload.decode('utf-8'))
Isso permite que tokens adulterados sejam aceitos parcialmente.
Solução: Logar o aviso claramente e não usar dados de token não verificado:
python


except Exception as e:
    Logger.warning(f"[licenca] Token com assinatura inválida ignorado: {e}")
    # Não usar dados do token não verificado
Impacto: Segurança — impede aceitação silenciosa de tokens adulterados.
4. _exec_db_statements mistura psycopg2 e psycopg3 com lógica de transação diferente
Problema: O código distingue _psycopg_v3 e usa lógicas de transação completamente diferentes para cada driver, aumentando a complexidade e risco de bugs em um dos caminhos:
psycopg3: usa context manager with conn:
psycopg2: usa autocommit=False + commit()/rollback() manual
Se _psycopg_v3 for True mas o driver apresentar comportamento diferente do esperado, o rollback nunca ocorre.
Solução: Abstrair a transação em um helper ou usar SQLAlchemy como já feito em gerar_activation_token:
python


import sqlalchemy as sa

def _exec_db_statements(statements):
    dsn = _get_db_dsn_from_env()
    engine = sa.create_engine(dsn, pool_pre_ping=True)
    with engine.begin() as conn:  # auto-commit ou rollback
        for q, p in statements:
            conn.execute(sa.text(q), dict(zip(..., p)))
Impacto: Estabilidade — comportamento de transação consistente entre drivers.
5. gerar_activation_token executa ALTER TABLE em produção a cada chamada
Problema: O código executa ALTER TABLE activation_tokens ALTER COLUMN ... toda vez que um token de ativação é gerado, independente de a coluna já estar no tipo correto:
python


conn.execute(_sa.text("""
    ALTER TABLE activation_tokens
        ALTER COLUMN cnpj TYPE TEXT,
        ...
"""))
Isso é uma operação DDL em produção, potencialmente bloqueante em tabelas grandes.
Solução: Remover o ALTER TABLE do fluxo de runtime. Essa migração deve ser executada uma única vez via script de migração de banco:
python


# Remover completamente do código:
# conn.execute(_sa.text("ALTER TABLE activation_tokens ..."))
Impacto: Estabilidade e Performance — evita bloqueio de tabela em produção.
6. _ensure_token_complete usa hmac.new (inexistente) em vez de hmac.new
Problema: O código usa:
python


assinatura = hmac.new(MASTER_KEY_BYTES, dados, hashlib.sha256).digest()
hmac.new não existe no módulo hmac padrão do Python. O correto é hmac.new → isso lançaria AttributeError em runtime. A função correta é hmac.new do módulo ou instanciar via hmac.HMAC:
python


# ERRADO (mesmo padrão usado em gerar_licenca e verificar_licenca):
hmac.new(MASTER_KEY_BYTES, dados, hashlib.sha256)
# CORRETO:
hmac.new(MASTER_KEY_BYTES, dados, hashlib.sha256)  # <- Python tem hmac.new sim
Nota: hmac.new existe no Python 3 como alias de hmac.HMAC. Porém, a API oficial recomendada é hmac.new — verificar se o ambiente alvo suporta. O risco real é consistência: gerar_licenca usa hmac.new, mas se algum ambiente restrito não tiver o alias, falhará silenciosamente.

Solução: Padronizar para a forma explícita em todo o arquivo:
python


import hmac as _hmac

def _hmac_sign(data: bytes) -> bytes:
    return _hmac.new(MASTER_KEY_BYTES, data, hashlib.sha256).digest()
Impacto: Confiabilidade — assinatura consistente em todos os contextos.
🟡 Prioridade Média
7. Padrão de obtenção de db_config duplicado em 4+ funções
Problema: O bloco abaixo aparece literalmente em registrar_tokens_por_cnpjs, registrar_tokens_por_cnpjs_single, deletar_registro_por_cnpjs e remover_cnpjs_do_db:
python


db_config = None
if get_database_config:
    db_config = get_database_config()
if not db_config:
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
    ...
if not db_config:
    raise RuntimeError('Configuração de banco não encontrada...')
Solução: Extrair em uma função auxiliar:
python


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
    if not config:
        raise RuntimeError('Configuração de banco não encontrada. Configure DATABASE_URL ou use config.py.')
    return config
Impacto: Manutenibilidade — alteração de lógica de resolução em um único lugar.
8. serializar_licenca inclui api_authorization e api_database_url no dict de saída como vazios
Problema: O método explicitamente não grava esses campos por segurança (comentário R2), mas ainda os inclui como strings vazias "" no JSON do arquivo .key:
python


out = {
    ...
    # api_authorization e api_database_url NÃO são gravados — correto
    # mas o dict inclui outros campos que podem vazar info
}
Contudo, em gui_licenca.py o meta passado para salvar_licenca inclui api_authorization e api_database_url:
python


meta = {
    ...
    'api_authorization': api_authorization,  # VAZA para o .key!
    'api_database_url': api_database_url,
}
Solução: Garantir remoção explícita em serializar_licenca:
python


CAMPOS_SENSIVEIS = ('api_authorization', 'api_database_url')

def serializar_licenca(token, payload_meta=None):
    if payload_meta:
        out = {k: v for k, v in payload_meta.items() if k not in CAMPOS_SENSIVEIS}
        out['token'] = token
        return json.dumps(out, ensure_ascii=False, indent=2)
    return token
Impacto: Segurança — credenciais nunca escritas em disco no arquivo .key.
9. _get_db_dsn_from_env e _exec_db_statements coexistem com _resolve_db_config (duplicação)
Problema: _get_db_dsn_from_env retorna uma DSN string para uso direto com psycopg, enquanto _resolve_db_config (proposta acima) retorna um dict com type/url. Existem dois sistemas paralelos de resolução de conexão.
Solução: Unificar: _get_db_dsn_from_env pode ser um detalhe interno de _exec_db_statements sem exposição separada, ou tornar-se parte de _resolve_db_config.
Impacto: Manutenibilidade — uma única fonte de verdade para configuração de banco.
10. gerar_licenca não valida formato de validade
Problema: A função aceita qualquer string em validade sem validar se é uma data válida. Isso permite salvar licenças com validade inválida como "amanhã" ou "31/02/2025", que verificar_licenca irá rejeitar com erro confuso.
Solução:
python


if validade:
    try:
        if 'T' in validade or validade.endswith('Z'):
            datetime.fromisoformat(validade.replace('Z', '+00:00'))
        else:
            date.fromisoformat(validade)
    except ValueError:
        raise ValueError(f"Formato de validade inválido: '{validade}'. Use YYYY-MM-DD ou ISO 8601.")
Impacto: Confiabilidade — erro detectado na geração, não na verificação.
11. _menu_edicao usa input() diretamente — sem tratamento de EOF
Problema: Em ambientes não-interativos (pipes, CI, scripts automatizados), input() lança EOFError quando não há stdin disponível, encerrando o processo abruptamente sem mensagem amigável.
Solução:
python


try:
    op = input('Escolha: ').strip().lower()
except EOFError:
    print('\nEntrada encerrada (EOF). Saindo.')
    raise KeyboardInterrupt
Impacto: Robustez — processo encerra de forma controlada em scripts.
12. carregar_licenca_de_arquivo abre arquivo com open(...).read() sem fechar explicitamente
Problema:
python


raw = open(caminho, "rb").read()
O arquivo é aberto sem with, dependendo do GC para fechar. Em implementações não-CPython (ex.: PyPy) ou em sistemas com limite de file descriptors, isso pode vazar.
Solução:
python


with open(caminho, "rb") as f:
    raw = f.read()
Impacto: Confiabilidade — file descriptor sempre liberado.
🟢 Prioridade Baixa
13. Ausência de type hints nos métodos públicos principais
Problema: Funções como gerar_licenca, verificar_licenca, salvar_licenca e carregar_licenca_de_arquivo não possuem anotações de tipo.
Solução:
python


from typing import Optional, List, Tuple, Dict, Any

def gerar_licenca(
    cnpjs: List[str],
    ids_celular: List[str],
    validade: str,
    nome_cliente: str,
    sql_servidor: str,
    sql_banco: str,
    api_authorization: str = "",
    api_database_url: str = ""
) -> str: ...

def verificar_licenca(token: str, validar_validade: bool = True) -> Dict[str, Any]: ...

def carregar_licenca_de_arquivo(caminho: str = "licenca.key") -> Tuple[Dict[str, Any], str]: ...
Impacto: Qualidade de código — habilita mypy e melhora autocomplete.
14. _input_cnpjs_inicial e _menu_edicao misturam lógica de negócio com I/O de terminal
Problema: Essas funções fazem print/input diretamente, dificultando testes unitários.
Solução: Separar a lógica de mutação do payload da lógica de I/O:
python


def aplicar_operacao_menu(payload: dict, op: str, valor: str) -> Tuple[dict, str]:
    """Retorna (payload_atualizado, mensagem). Testável sem I/O."""
    ...
Impacto: Testabilidade — funções de core testáveis sem mock de stdin.
15. requests = None como fallback silencia erros de import
Problema:
python


try:
    import requests
except Exception:
    requests = None
Se requests não estiver instalado e uma função REST for chamada, o erro ocorre tarde demais (dentro de _registrar_tokens_por_cnpjs_rest), com mensagem menos clara.
Solução: Logar um aviso na importação:
python


try:
    import requests
except ImportError:
    requests = None
    import warnings
    warnings.warn(
        "Biblioteca 'requests' não instalada. Funcionalidades REST não estarão disponíveis.",
        ImportWarning, stacklevel=1
    )
Impacto: Debugabilidade — problema detectado mais cedo.
📁 gui_licenca.py
🔴 Prioridade Alta
16. api_authorization e api_database_url incluídos em meta e gravados no .key
Problema: Em save_license, o dict meta enviado para salvar_licenca inclui:
python


meta = {
    ...
    'api_authorization': api_authorization,  # CREDENCIAL EM DISCO!
    'api_database_url': api_database_url,
}
Mesmo que licenca.py tente filtrar, a intenção declarada em serializar_licenca (não gravar esses campos) é contornada pelo chamador que os passa explicitamente.
Solução: Remover esses campos do meta na GUI:
python


meta = {
    'cnpjs': cnpjs,
    'ids_celular': ids_celular,
    'validade': validade,
    'api_url': api_url,
    'nome_cliente': nome_cliente,
    'sql_servidor': sql_servidor,
    'sql_banco': sql_banco,
    # api_authorization e api_database_url NÃO vão para o .key
}
Impacto: Segurança — credenciais nunca expostas no arquivo de licença.
17. save_license silencia erro ao deletar_registro_por_cnpjs sem log
Problema:
python


try:
    deletar_registro_por_cnpjs(self.original_cnpjs_str)
except Exception:
    pass  # Ignora erro ao deletar
Se a deleção falhar (ex.: timeout, permissão), o registro antigo permanece no banco sem qualquer aviso, causando inconsistência silenciosa.
Solução: Logar o erro e notificar o usuário como aviso (não crítico):
python


except Exception as e:
    import logging
    logging.warning(f"[GUI] Falha ao deletar registro antigo ({self.original_cnpjs_str}): {e}")
    # Opcional: incluir no msg final como aviso
Impacto: Confiabilidade — inconsistências detectadas e reportadas.
18. Validação duplicada entre save_license e gerar_licenca
Problema: save_license repete todas as validações de comprimento e obrigatoriedade (nome_cliente, sql_servidor, sql_banco) que gerar_licenca já faz internamente. Isso cria dois lugares para manter as mesmas regras.
Solução: Manter apenas uma camada de validação — confiar na exceção de gerar_licenca e tratar o ValueError na GUI:
python


try:
    lic_token = gerar_licenca(cnpjs, ids_celular, validade or '9999-12-31',
                              nome_cliente, sql_servidor, sql_banco, ...)
except ValueError as e:
    QMessageBox.warning(self, 'Dados inválidos', str(e))
    return
Impacto: Manutenibilidade — regras de negócio em um único lugar.
🟡 Prioridade Média
19. generate_token_only existe mas não faz nada
Problema: O método está presente na classe mas retorna imediatamente:
python


def generate_token_only(self):
    """..."""
    # removido: geração direta de token via botão (fluxo mantido no salvar)
    return
Código morto — confunde futuros mantenedores.
Solução: Remover completamente o método ou marcá-lo explicitamente como deprecated:
python


# Método removido — mantido apenas para compatibilidade com chamadas externas.
# Use save_license() para gerar e salvar o token.
Impacto: Clareza — remove dead code.
20. LicencaWindow.__init__ com mais de 120 linhas — viola SRP
Problema: Todo o layout da janela é construído inline no __init__, incluindo seções de SQL, API, CNPJs, celulares, datas e botões. Isso dificulta manutenção e testes de partes individuais da UI.
Solução: Extrair seções em métodos auxiliares:
python


def __init__(self):
    super().__init__()
    self._setup_window()
    layout = QVBoxLayout(self.centralWidget())
    self._build_header(layout)
    self._build_cliente_section(layout)
    self._build_sql_section(layout)
    self._build_api_section(layout)
    self._build_cnpj_section(layout)
    self._build_celular_section(layout)
    self._build_validade_section(layout)
    self._build_actions(layout)
Impacto: Manutenibilidade — cada seção pode ser modificada isoladamente.
21. load_license usa getattr(self, 'nome_cliente_edit', None) desnecessariamente
Problema: O uso de getattr com fallback None para verificar atributos que sempre existem após __init__ indica incerteza sobre o estado do objeto. Isso ocorre em 6+ lugares em load_license e new_license.
Solução: Remover os getattr e acessar diretamente (os atributos são sempre inicializados em __init__):
python


# Antes:
if getattr(self, 'nome_cliente_edit', None):
    self.nome_cliente_edit.setText(nome)
# Depois:
self.nome_cliente_edit.setText(nome)
Impacto: Legibilidade — código mais claro e idiomático.
22. Campo api_authorization_edit com setMaxLength(100) mas sem validação real
Problema: Tokens Bearer modernos (JWT, OAuth2) frequentemente têm mais de 100 caracteres. Um JWT típico tem 200–500 chars. O limite arbitrário de 100 truncará tokens válidos silenciosamente.
Solução: Remover o limite rígido ou aumentá-lo substancialmente:
python


self.api_authorization_edit.setMaxLength(1000)  # JWT pode ser longo
# Ou sem limite:
# self.api_authorization_edit.setMaxLength(0)  # Qt: 0 = sem limite
Impacto: Confiabilidade — tokens reais não truncados.
23. configure_api verifica api_token obrigatório mas api_url pode ser vazio
Problema: O diálogo de configuração exige api_token mas aceita api_url vazio. Se a URL estiver vazia e a autenticação for tentada, o erro ocorrerá mais tarde com mensagem confusa.
Solução: Validar api_url também:
python


if not api_url:
    QMessageBox.warning(self, 'Atenção', 'A URL da API não pode ser vazia.')
    return
if not api_url.startswith(('http://', 'https://')):
    QMessageBox.warning(self, 'Atenção', 'A URL da API deve começar com http:// ou https://')
    return
Impacto: Usabilidade — erro detectado no momento da configuração.
🟢 Prioridade Baixa
24. gerar_token_ativacao copia para clipboard sem fallback visível ao usuário
Problema: Se a cópia para clipboard falhar (ex.: ambiente headless, Wayland sem xclip), a exceção é silenciada e a mensagem diz "(Copiado para a área de transferência)" incorretamente:
python


except Exception:
    pass  # Usuário acredita que foi copiado, mas não foi
Solução:
python


try:
    _QApp.clipboard().setText(raw_token)
    clipboard_msg = '\n\n✓ Copiado para a área de transferência'
except Exception:
    clipboard_msg = '\n\n⚠ Não foi possível copiar automaticamente — copie manualmente.'
msg += clipboard_msg
Impacto: Usabilidade — feedback honesto ao operador.
25. Ícones buscados em múltiplos formatos com lógica repetida em dois lugares
Problema: A lógica de busca de ícone (.ico → .svg → .png) aparece duas vezes em __init__: uma para o ícone da janela e outra para o header_label:
python


# Primeira vez: para setWindowIcon
icon_ico = os.path.join(base, 'assets', 'logo.ico')
icon_svg = ...
icon_png = ...
icon_path = (icon_ico if os.path.exists(icon_ico) else ...)

# Segunda vez: para header_label (lógica diferente — sem .svg)
logo_path = icon_ico if os.path.exists(icon_ico) else (icon_png ...)
Solução: Centralizar em um método auxiliar:
python


def _find_asset(self, *names: str) -> Optional[str]:
    base = os.path.dirname(__file__)
    for name in names:
        path = os.path.join(base, 'assets', name)
        if os.path.exists(path):
            return path
    return None

# No __init__:
icon_path = self._find_asset('logo.ico', 'logo.svg', 'logo.png')
Impacto: Manutenibilidade — adicionar novo formato de ícone em um lugar.
26. Ausência de type hints nos métodos públicos
Problema: Nenhum método da classe tem anotações de tipo.
Solução:
python


def add_cnpj(self) -> None: ...
def save_license(self) -> None: ...
def load_license(self) -> None: ...
def gerar_token_ativacao(self) -> None: ...
Impacto: Qualidade de código.
📋 Tabela Resumo



#	Melhoria	Arquivo	Prioridade	Impacto Principal
1*	Memoizar _derive_encryption_key com lru_cache	licenca.py	🔴 Alta	Segurança + Performance
2	Remover except Exception as e: raise desnecessário*	licenca.py	🔴 Alta	Debugabilidade
3	Fallback de token sem assinatura aceito silenciosamente	licenca.py	🔴 Alta	Segurança
4*	Unificar lógica de transação SQL entre psycopg2/3*	licenca.py	🔴 Alta	Estabilidade
5	ALTER TABLE executado em produção a cada ativação	licenca.py	🔴 Alta	Estabilidade
6*	Padronizar uso de hmac.new em todo o arquivo	licenca.py*	🔴 Alta*	Confiabilidade
7	Extrair _resolve_db_config() para eliminar duplicação 4×*	licenca.py	🟡 Média	Manutenibilidade
8	serializar_licenca não filtra campos sensíveis ativamente	licenca.py	🟡 Média*	Segurança
9	Dois sistemas paralelos de resolução de conexão	licenca.py	🟡 Média	Manutenibilidade
10	gerar_licenca não valida formato de validade	licenca.py	🟡 Média*	Confiabilidade
11	input() sem tratamento de EOFError	licenca.py	🟡 Média	Robustez
12*	open() sem with em carregar_licenca_de_arquivo	licenca.py*	🟡 Média	Confiabilidade
13	Ausência de type hints nas funções públicas	licenca.py	🟢 Baixa	Qualidade
14	Funções de menu misturam I/O com lógica de negócio	licenca.py*	🟢 Baixa	Testabilidade
15	requests = None sem aviso de importação	licenca.py	🟢 Baixa	Debugabilidade
16	meta com credenciais sendo gravado no arquivo .key	gui_licenca.py	🔴 Alta	Segurança
17*	Deleção de registro antigo falha silenciosamente	gui_licenca.py	🔴 Alta	Confiabilidade
18*	Validação duplicada entre GUI e gerar_licenca	gui_licenca.py	🔴 Alta	Manutenibilidade
19	generate_token_only é código morto	gui_licenca.py	🟡 Média	Clareza
20	__init__ com 120+ linhas — viola SRP	gui_licenca.py	🟡 Média*	Manutenibilidade
21	getattr desnecessário para atributos sempre existentes	gui_licenca.py	🟡 Média	Legibilidade
22	setMaxLength(100) trunca tokens JWT válidos	gui_licenca.py	🟡 Média	Confiabilidade
23	api_url não validado em configure_api	gui_licenca.py	🟡 Média*	Usabilidade
24	Clipboard: falha silenciosa reporta sucesso falso	gui_licenca.py	🟢 Baixa	Usabilidade
25*	Lógica de busca de ícone duplicada no __init__	gui_licenca.py	🟢 Baixa	Manutenibilidade
26	Ausência de type hints nos métodos da classe	gui_licenca.py	🟢 Baixa*	Qualidade
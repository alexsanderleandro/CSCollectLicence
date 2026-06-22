# Análise de Melhorias - `CSCollectLicence`

Esta análise avalia cada uma das melhorias propostas em [melhorias_licenca_gui_licenca.md](file:///c:/Users/alex.CEOSOFTWAREAD/Documents/Python/VSCode/CSCollectLicence/melhorias_licenca_gui_licenca.md) para garantir que as alterações propostas não impactem o funcionamento atual do sistema de licenças.

---

## 📁 `licenca.py`

### 🔴 Prioridade Alta

#### 1. `MASTER_KEY` exposta como variável global em memória sem proteção
* **Funcionamento Atual:** `MASTER_KEY_BYTES` é armazenada em escopo global. A derivação da chave AES (`_derive_encryption_key`) executa PBKDF2 com 100.000 iterações a cada criptografia/descriptografia de campo, o que causa lentidão.
* **Risco de Quebra:** **ALTO se implementado de forma ingênua.** A proposta sugere apagar a `MASTER_KEY` após a derivação. No entanto, a `MASTER_KEY_BYTES` é usada diretamente pelo HMAC em `gerar_licenca`, `verificar_licenca` e `_ensure_token_complete`. Se apagarmos a chave global, **a assinatura e verificação de licenças deixarão de funcionar**, impossibilitando o carregamento de qualquer licença.
* **Recomendação Segura:**
  * Implementar o cache com `functools.lru_cache(maxsize=1)` para a derivação da chave AES (`_derive_encryption_key`). Isso otimiza a performance.
  * **NÃO** apagar ou remover `MASTER_KEY_BYTES` da memória global, pois ela é necessária para a assinatura digital do token (HMAC-SHA256).

#### 2. `verificar_licenca` tem bloco `except Exception as e: raise` desnecessário
* **Funcionamento Atual:** Captura genérica que apenas faz `raise`.
* **Risco de Quebra:** **NENHUM.** A remoção do bloco try/except externo preserva o comportamento original e limpa a pilha de chamadas (traceback).
* **Recomendação Segura:** Remover o bloco externo de try/except e deixar as exceções subirem naturalmente.

#### 3. `carregar_licenca_de_arquivo` decodifica payload sem verificar assinatura em fallback
* **Funcionamento Atual:** Caso o token falhe na validação de assinatura, o código tenta decodificar a primeira parte (payload) sem assinar para fins de compatibilidade legada com envelopes do CSCollect Manager.
* **Risco de Quebra:** **MÉDIO.** Se houver sistemas utilizando arquivos de licença legados e não assinados gerados pelo Manager antigo, remover esse fallback quebrará a leitura dessas licenças.
* **Recomendação Segura:** Manter o fallback de decodificação apenas como leitura informativa, registrando um log de aviso (`logging.warning`) de que a assinatura é inválida, mas permitindo que a GUI exiba os dados se for uma licença antiga reconhecida.

#### 4. `_exec_db_statements` mistura psycopg2 e psycopg3 com lógica de transação diferente
* **Funcionamento Atual:** Código chaveia dinamicamente entre psycopg2 (usando autocommit manual) e psycopg3 (usando context manager).
* **Risco de Quebra:** **ALTO se trocado para SQLAlchemy.** A sugestão propõe usar SQLAlchemy. Contudo, SQLAlchemy adiciona uma dependência externa pesada e um pool de conexões desnecessário para chamadas pontuais de CLI. Além disso, as consultas usam a sintaxe de placeholder do psycopg (`%s`), enquanto o SQLAlchemy em modo puro espera parâmetros nomeados (`:param`). Mudar para SQLAlchemy pode gerar erros de sintaxe SQL em produção.
* **Recomendação Segura:** Manter o psycopg puro, mas abstrair a transação em uma função auxiliar que lide corretamente com o contexto de transação do driver ativo (v2 ou v3), sem introduzir SQLAlchemy nesta parte.

#### 5. `gerar_activation_token` executa `ALTER TABLE` em produção a cada chamada
* **Funcionamento Atual:** Executa `ALTER TABLE` para ajustar os tipos de coluna toda vez que gera um token de ativação.
* **Risco de Quebra:** **MÉDIO.** `ALTER TABLE` exige bloqueio exclusivo (`ACCESS EXCLUSIVE`) na tabela do banco de dados, o que causa lentidão e timeouts em produção. Remover o comando do código sem migrar o banco primeiro fará com que inserções de campos mais longos falhem.
* **Recomendação Segura:**
  1. Garantir que o banco de dados em produção já possua as colunas `cnpj` e `device_id_autorizado` configuradas como `TEXT` (ou tamanho adequado).
  2. Remover as linhas de `ALTER TABLE` de dentro de `gerar_activation_token`.

#### 6. `_ensure_token_complete` usa `hmac.new`
* **Funcionamento Atual:** O arquivo sugere que `hmac.new` não existiria ou seria inconsistente.
* **Risco de Quebra:** **NENHUM.** `hmac.new` é a API oficial e está presente em todas as versões do Python 3.
* **Recomendação Segura:** Padronizar o uso de `hmac.new` de forma explícita e consistente em todo o código.

---

### 🟡 Prioridade Média

#### 7. Padrão de obtenção de `db_config` duplicado em 4+ funções
* **Risco de Quebra:** **NENHUM.** A extração para `_resolve_db_config()` simplifica a manutenção.
* **Recomendação Segura:** Implementar `_resolve_db_config()` retornando o dicionário de configuração unificado.

#### 8. `serializar_licenca` inclui `api_authorization` e `api_database_url` no dict de saída como vazios
* **Risco de Quebra:** **NENHUM.** Atualmente o dicionário `out` já omite essas chaves. Garantir a filtragem explícita protege contra qualquer alteração futura acidental.
* **Recomendação Segura:** Adicionar a lista de exclusão `CAMPOS_SENSIVEIS` para sanitizar o dicionário antes da serialização.

#### 9. `_get_db_dsn_from_env` e `_exec_db_statements` coexistem com `_resolve_db_config`
* **Risco de Quebra:** **NENHUM.**
* **Recomendação Segura:** Unificar a lógica de conexão no helper `_resolve_db_config()`.

#### 10. `gerar_licenca` não valida formato de validade
* **Risco de Quebra:** **MÉDIO.** Se algum fluxo externo gerar licenças sem data de validade (ex: licenças vitalícias), a validação rígida de data pode rejeitar o token.
* **Recomendação Segura:** Permitir que o campo de validade seja nulo ou vazio (indicando sem expiração), e validar o formato apenas se houver um valor string preenchido.

#### 11. `_menu_edicao` sem tratamento de EOF
* **Risco de Quebra:** **NENHUM.**
* **Recomendação Segura:** Capturar `EOFError` e finalizar de forma elegante.

#### 12. `carregar_licenca_de_arquivo` sem `with`
* **Risco de Quebra:** **NENHUM.**
* **Recomendação Segura:** Substituir por `with open(caminho, "rb") as f:`.

---

### 🟢 Prioridade Baixa

#### 13. Ausência de type hints
* **Risco de Quebra:** **NENHUM.** Melhora a análise estática e a legibilidade.

#### 14. Mistura de I/O e lógica de negócio na CLI
* **Risco de Quebra:** **NENHUM.**
* **Recomendação Segura:** Manter o fluxo de console simples, focando a refatoração nos componentes de UI da GUI.

#### 15. `requests = None` silencia erros
* **Risco de Quebra:** **NENHUM.**
* **Recomendação Segura:** Adicionar um aviso (`warnings.warn`) se o módulo `requests` não estiver instalado ao iniciar a aplicação.

---
---

## 📁 `gui_licenca.py`

### 🔴 Prioridade Alta

#### 16. `api_authorization` e `api_database_url` incluídos em `meta` e gravados no `.key`
* **Funcionamento Atual:** A GUI passa esses dados sensíveis no dicionário `meta` para o método `salvar_licenca`.
* **Risco de Quebra:** **MÉDIO.** Embora `licenca.py` descarte essas chaves ao gravar no disco, a GUI atualmente tenta ler essas chaves ao carregar um arquivo `.key`. Se elas não forem gravadas, a GUI exibirá esses campos como vazios ao reabrir uma licença.
* **Recomendação Segura:** Como esses campos devem ser armazenados exclusivamente no banco de dados (Neon) de forma criptografada para segurança, o comportamento de mantê-los vazios no `.key` está correto. A GUI deve ser ajustada para não enviá-los no `meta`.

#### 17. `save_license` silencia erro ao `deletar_registro_por_cnpjs`
* **Risco de Quebra:** **NENHUM.**
* **Recomendação Segura:** Logar a falha utilizando o módulo `logging`, evitando uma caixa de diálogo intrusiva caso a deleção falhe por motivos secundários (como registro inexistente).

#### 18. Validação duplicada entre `save_license` e `gerar_licenca`
* **Funcionamento Atual:** A GUI faz as mesmas validações de string que `gerar_licenca`.
* **Risco de Quebra:** **BAIXO.** Se removermos a validação da GUI de forma simples, o usuário só receberá o alerta de validação *depois* que a caixa de diálogo para salvar o arquivo foi aberta e confirmada, o que prejudica a experiência de uso.
* **Recomendação Segura:** Chamar `gerar_licenca` antes de abrir a janela de diálogo `QFileDialog.getSaveFileName`. Se a geração lançar `ValueError`, exibir o alerta e interromper o processo imediatamente, sem solicitar o salvamento do arquivo antes.

---

### 🟡 Prioridade Média

#### 19. `generate_token_only` morto
* **Risco de Quebra:** **NENHUM.**
* **Recomendação Segura:** Remover o método obsoleto.

#### 20. `LicencaWindow.__init__` muito extenso
* **Risco de Quebra:** **BAIXO.** Requer cuidado para manter todas as referências de atributos (ex: `self.nome_cliente_edit`).
* **Recomendação Segura:** Modularizar a interface dividindo em métodos como `_setup_ui()`, `_create_sql_section()`, etc.

#### 21. `getattr` desnecessário em `load_license`
* **Risco de Quebra:** **NENHUM.** Os elementos são criados no inicializador, tornando o `getattr` redundante.
* **Recomendação Segura:** Acessar os campos diretamente (ex: `self.nome_cliente_edit.setText(...)`).

#### 22. Campo `api_authorization_edit` com `setMaxLength(100)`
* **Funcionamento Atual:** Trunca tokens longos de autenticação (como JWTs).
* **Risco de Quebra:** **CRÍTICO SE NÃO CORRIGIDO.** Tokens JWT frequentemente excedem 100 caracteres. O limite atual corrompe tokens longos silenciosa ao serem colados.
* **Recomendação Segura:** Aumentar o limite para `1000` ou remover a limitação rígida (`setMaxLength(0)` ou omitir).

#### 23. `configure_api` aceita `api_url` vazio
* **Risco de Quebra:** **NENHUM.** Melhora a validação antes de persistir as configurações da API.

---

### 🟢 Prioridade Baixa

#### 24. `gerar_token_ativacao` sem feedback de erro no Clipboard
* **Risco de Quebra:** **NENHUM.**
* **Recomendação Segura:** Informar ao usuário caso o clipboard falhe (comum em sistemas Linux headless ou permissões de Sandbox do Windows).

#### 25. Busca de ícones duplicada no `__init__`
* **Risco de Quebra:** **NENHUM.**
* **Recomendação Segura:** Criar a função auxiliar `_find_asset()` para centralizar a busca.

#### 26. Ausência de type hints na GUI
* **Risco de Quebra:** **NENHUM.**

# Licenciamento — CSCollectLicence

Instruções rápidas (Windows / PowerShell):

1. Crie e ative um ambiente virtual (recomendado):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Instale dependências:

```powershell
python -m pip install -r requirements.txt
```

Adicionalmente, se for usar integração com o Neon/Postgres (registro de tokens), instale `psycopg[binary]` (já incluido no `requirements.txt`) ou, manualmente:

```powershell
python -m pip install "psycopg[binary]"
```

**Configuração recomendada** (sem variáveis de ambiente):

Execute o script de configuração para salvar as credenciais localmente:

```powershell
python .\configurar_banco.py
```

Isso criará `cscollect_config.json` na pasta do projeto/executável com suas credenciais.

**Configuração via variáveis de ambiente** (alternativa):

Defina as variáveis de ambiente para conexão com o banco (uma das opções):

- `DATABASE_URL` com a URL completa (recomendada, ex: `postgres://user:pass@host:5432/dbname`)
OU
- `NEON_HOST`, `NEON_DB` (ou `NEON_DATABASE`), `NEON_USER`, `NEON_PASSWORD`, `NEON_PORT`

Ou, para integração via API REST do Neon/PostgREST, defina:

- `NEON_REST_URL` — ex: https://ep-dry-hall-acd532yy.apirest.sa-east-1.aws.neon.tech/neondb/rest/v1
- `NEON_API_KEY` — a chave (service role ou anon, conforme permissões) a usar nos headers

Exemplo PowerShell de definição temporária (não recomendado para produção):

```powershell
$env:NEON_REST_URL='https://ep-dry-hall-acd532yy.apirest.sa-east-1.aws.neon.tech/neondb/rest/v1'
$env:NEON_API_KEY='SUA_CHAVE_DE_API'
$env:MASTER_KEY='SUA_MASTER_KEY_SECRETA'
python .\licenca.py
```

Se preferir usar `DATABASE_URL`, certifique-se de que contém usuário e senha URL-encoded quando necessário.

3. Crie um arquivo `.env` a partir de `.env.example` e defina sua chave mestra:

```text
COPY .env.example .env
# Edite .env e substitua MASTER_KEY
```

4. **Configure a conexão com o banco de dados** (uma vez):

```powershell
python .\configurar_banco.py
```

Escolha entre:
- **SQL Direto**: Cole a `DATABASE_URL` completa do Neon
- **API REST**: Cole a URL REST + API Key (JWT service_role)

A configuração será salva em `cscollect_config.json` na mesma pasta.

Mudanças de Schema (Neon)
-------------------------

O projeto inclui migrations para ajustar o schema do banco Neon conforme necessário.
Arquivos de migration disponíveis:

- `migration.sql` — adiciona colunas `reginclusao` e `dataalteracao` e cria trigger `set_dataalteracao`.
- `migration_neon_schema.sql` — cria/ajusta tabelas `clientes` e `cargas` e cria a tabela `contagens`.
- `migration_neon_schema_v2.sql` — adiciona `idcelular` e `cnpj` em `clientes`, `cargas` e `contagens` e cria índices únicos compostos (`id, cnpj, idcelular`).
- `migration_neon_schema_v3.sql` — adiciona coluna `validade` do tipo `date` em `clientes`.
- `migration_neon_schema_v7.sql` — adiciona coluna `arq_licenca` em `clientes` para armazenar o conteúdo do arquivo `.key` e permitir download remoto via API ponte.

Resumo do schema esperado (após aplicar as migrations):

- `clientes`:
	- `id` (serial) — identificador
	- `nome_cliente` (text)
	- `cnpj` (text)
	- `token` (text) — token assinado (payload.signature)
	- `arq_licenca` (text) — conteúdo textual completo do arquivo `.key`
	- `idcelular` (text)
	- `reginclusao` (timestamptz) — timestamp de criação (DEFAULT now())
	- `dataalteracao` (timestamptz) — atualizado por trigger antes de UPDATE
	- `validade` (date)

- `cargas`:
	- `id` (serial)
	- `cliente_id` (integer)
	- `nome_arquivo` (text)
	- `data_envio` (timestamptz)
	- `nome_cliente` (text)
	- `cnpj` (text)
	- `idcelular` (text)

- `contagens` (nova tabela):
	- `id` (serial)
	- `cliente_id` (integer)
	- `nome_arquivo` (text)
	- `data_envio` (timestamptz)
	- `nome_cliente` (text)
	- `cnpj` (text)
	- `idcelular` (text)

Observações:
- As migrations criam índices únicos compostos `(id, cnpj, idcelular)` como preparação para uma possível PK composta no futuro.
- A trigger `set_dataalteracao` garante que `dataalteracao` seja atualizada automaticamente ao executar UPDATEs.
- `token` armazenado em `clientes.token` tem o formato `payload.signature` (base64url(payload).base64url(signature)).

Como aplicar as migrations
-------------------------

Use o script `apply_migration.py` (recomendado) dentro do `venv` ou `psql` diretamente. Exemplo com o `venv`:

```powershell
$env:DATABASE_URL='postgresql://USUARIO:SENHA@HOST/DB?sslmode=require&channel_binding=require'
.\venv\Scripts\python.exe .\apply_migration.py "%DATABASE_URL%" migration_neon_schema.sql
.\venv\Scripts\python.exe .\apply_migration.py "%DATABASE_URL%" migration_neon_schema_v2.sql
.\venv\Scripts\python.exe .\apply_migration.py "%DATABASE_URL%" migration_neon_schema_v3.sql
.\venv\Scripts\python.exe .\apply_migration.py "%DATABASE_URL%" migration_neon_schema_v7.sql
```

Ou com `psql`:

```powershell
psql 'postgresql://USUARIO:SENHA@HOST/DB?sslmode=require&channel_binding=require' -f migration_neon_schema.sql
psql 'postgresql://USUARIO:SENHA@HOST/DB?sslmode=require&channel_binding=require' -f migration_neon_schema_v2.sql
psql 'postgresql://USUARIO:SENHA@HOST/DB?sslmode=require&channel_binding=require' -f migration_neon_schema_v3.sql
psql 'postgresql://USUARIO:SENHA@HOST/DB?sslmode=require&channel_binding=require' -f migration_neon_schema_v7.sql
```

Após aplicar, verifique as colunas e a existência da trigger conforme descrito no README.

5. Execute o script:

```powershell
python .\licenca.py

Gerar executável (Windows):

1. Opcional: adicione um ícone em `assets/logo.ico` (formato .ico) para ser embutido no executável.
2. Execute o script de build PowerShell:

```powershell
.\build_exe.ps1
```

O build criará `dist\CSCollectLicence.exe`. Depois, forneça `MASTER_KEY` por variável de ambiente ou crie um `.env` no mesmo diretório do executável antes de rodar.
```

Alternativa rápida (não persistente) — definir `MASTER_KEY` apenas para a sessão atual do PowerShell:

```powershell
$env:MASTER_KEY='SUA_CHAVE_DE_TESTE'; python .\licenca.py
```

Segurança:
- Nunca comite sua `MASTER_KEY` em repositórios públicos.
- Para produção, guarde a chave em um cofre de segredos (Key Vault, AWS Secrets Manager, Windows Credential Manager, etc.).

Como o CSCollectManager deve carregar `MASTER_KEY`
-----------------------------------------------

O validador de licença usado pelo CSCollectManager precisa da mesma `MASTER_KEY`
utilizada para gerar o arquivo `.key`. Recomenda-se uma das seguintes abordagens
para carregar a chave no processo do CSCollectManager:

- Variável de ambiente (recomendado): defina `MASTER_KEY` no ambiente do
	sistema ou do serviço que roda o CSCollectManager. Exemplo PowerShell temporário:

```powershell
$env:MASTER_KEY='SUA_MASTER_KEY_SECRETA'
# Em seguida inicie o executável do CSCollectManager no mesmo terminal/session
```

- Arquivo `.env` ao lado do executável: crie um arquivo `.env` contendo `MASTER_KEY=...`
	e carregue-o com `python-dotenv` no startup do app. O projeto já inclui lógica
	para procurar e carregar `.env` quando empacotado com PyInstaller (veja `licenca.py`).

- Parâmetro de configuração/console: passe a chave por parâmetro ou fonte de
	configuração segura (cofre de segredos) na inicialização do serviço.

Notas úteis:
- Garanta que o processo que valida a licença remova aspas em torno do valor
	(ex.: `.env` com `MASTER_KEY='valor'` deve ser interpretado como `valor`).
- Ao implementar em C#/.NET, use decodificação base64 URL-safe e HMAC-SHA256
	com a mesma chave. Um helper C# de exemplo está disponível no repositório
	(veja histórico de commits / mensagens do workspace).

API ponte para download da licença
----------------------------------

O arquivo [api_licenca_bridge.py](api_licenca_bridge.py) expõe uma API HTTP simples para o APK e o CSCollectManager baixarem a licença pela internet a partir do campo `clientes.arq_licenca`.

Configuração mínima:

- Banco SQL direto: `DATABASE_URL` ou `NEON_DATABASE_URL`
- Ou REST do Neon: `NEON_REST_URL` (ou `NEON_REST_API_URL`) + `NEON_API_KEY`
- Opcional: `LICENSE_API_TOKEN` para exigir `Authorization: Bearer <token>` nas chamadas
- Opcional: `LICENSE_API_HOST` e `LICENSE_API_PORT` (padrão `0.0.0.0:8080`)

Executar:

```powershell
.\venv\Scripts\python.exe .\api_licenca_bridge.py
```

Endpoints:

- `GET /health`
- `GET /licencas/metadata?cnpj=12345678000199&id_celular=device-1`
- `GET /licencas/download?cnpj=12345678000199&id_celular=device-1`

Comportamento:

- Busca a licença pelo CNPJ, inclusive quando a coluna `cnpj` contém vários CNPJs separados por vírgula
- Valida `ativo = true`
- Bloqueia licença vencida com base na coluna `validade`
- Se `id_celular` for informado, valida se o dispositivo está autorizado
- Retorna o conteúdo de `arq_licenca`; se a coluna estiver vazia em registros antigos, faz fallback para `token`

Exemplo com token Bearer:

```powershell
$headers = @{ Authorization = 'Bearer SEU_TOKEN_DA_API' }
Invoke-WebRequest 'http://localhost:8080/licencas/download?cnpj=12345678000199&id_celular=device-1' -Headers $headers -OutFile '.\Licenca.key'
```

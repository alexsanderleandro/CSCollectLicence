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

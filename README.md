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

3. Crie um arquivo `.env` a partir de `.env.example` e defina sua chave mestra:

```text
COPY .env.example .env
# Edite .env e substitua MASTER_KEY
```

4. Execute o script:

```powershell
python .\licenca.py
```

Alternativa rápida (não persistente) — definir `MASTER_KEY` apenas para a sessão atual do PowerShell:

```powershell
$env:MASTER_KEY='SUA_CHAVE_DE_TESTE'; python .\licenca.py
```

Segurança:
- Nunca comite sua `MASTER_KEY` em repositórios públicos.
- Para produção, guarde a chave em um cofre de segredos (Key Vault, AWS Secrets Manager, Windows Credential Manager, etc.).

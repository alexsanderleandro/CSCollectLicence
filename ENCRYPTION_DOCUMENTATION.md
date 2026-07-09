# Criptografia de Credenciais em Licenca.key

## Visão Geral

Implementação de criptografia simétrica (Fernet/AES-128) para proteger credenciais sensíveis armazenadas no arquivo de licença `.key`. 

**Objetivo**: Impedir exposição de credenciais em texto puro, mantendo-as disponíveis apenas em memória durante a validação da licença.

## Motivação

**ANTES**: Arquivo `.key` continha credenciais em texto puro:
```json
{
  "api_authorization": "d2bd9a450500c2e851d049c5fb846f44",
  "api_database_url": "postgresql://user:pass@host/db"
}
```
**Risco**: Qualquer pessoa com acesso ao arquivo `.key` pode ler credenciais.

**DEPOIS**: Arquivo `.key` com credenciais criptografadas:
```json
{
  "api_authorization": "gAAAAABqOr3chOeGgfj7rxn-UO4cFHw92UAAX9I...",
  "api_database_url": "gAAAAABqOr3cy9FCqiLcTCtV2o2sW_MBOCQgy..."
}
```
**Benefício**: Credenciais ilegíveis; apenas apps autorizados podem descriptografar.

## Arquitetura Técnica

### Módulo de Criptografia: `encryption.py`

```python
from cryptography.fernet import Fernet

# Funções principais
encrypt_field(value: str) -> str         # Criptografa valor
decrypt_field(encrypted: str) -> str     # Descriptografa valor  
is_encrypted(value: str) -> bool         # Detecta se já está criptografado
```

**Algoritmo**: Fernet (simétrico, baseado em AES-128-CBC)
- **Segurança**: Token contém HMAC-SHA256 para autenticação
- **Chave**: Derivada via SHA-256 de seed mestre
- **Compatibilidade**: Python 3.6+, Kivy, Android

### Fluxo de Criptografia

1. **Geração (CSCollectLicence)**:
   ```
   Credenciais originais (texto puro)
           ↓
   [encrypt_field] → Token Fernet
           ↓
   Salva em Licenca.key (criptografado)
   ```

2. **Carregamento (CSCollectManager/CSCollect)**:
   ```
   Lê Licenca.key (criptografado)
           ↓
   Detecta: is_encrypted(value)
           ↓
   [decrypt_field] → Credencial descriptografada
           ↓
   Em memória (apenas durante validação)
   ```

## Implementação

### Arquivos Modificados

| Arquivo | Mudanças |
|---------|----------|
| `CSCollectManager/licenca.py` | Criptografa em `salvar_licenca_json()`, descriptografa em `carregar_licenca_de_arquivo()` |
| `CSCollectManager/CSCollectManager/licenca.py` | Idem (versão duplicada) |
| `CSCollectLicence/licenca.py` | Criptografa em `serializar_licenca()`, descriptografa em `carregar_licenca_de_arquivo()` |
| `CSCollect/encryption.py` (novo) | Módulo de criptografia para APK |

### Exemplo: Salvar com Criptografia

```python
from encryption import encrypt_field
from licenca import salvar_licenca_json

# Credenciais em texto puro
api_auth = "meu-token-secreto"
api_db = "postgresql://user:pass@host/db"

# Salva automaticamente criptografado
salvar_licenca_json(
    token,
    cnpjs,
    ids_celular,
    validade,
    api_authorization=api_auth,      # Será criptografado
    api_database_url=api_db,          # Será criptografado
    caminho="Licenca.key"
)
```

### Exemplo: Carregar e Descriptografar

```python
from licenca import carregar_licenca_de_arquivo

# Carrega arquivo (criptografado)
payload, token = carregar_licenca_de_arquivo("Licenca.key")

# Valores já descriptografados em payload
api_auth = payload.get('api_authorization')  # String pura
api_db = payload.get('api_database_url')      # String pura

# Usar credenciais...
db_conn = psycopg2.connect(api_db)
```

## Segurança

### Força

- **Algoritmo**: Fernet usa AES-128-CBC (padrão NIST)
- **Autenticação**: HMAC-SHA256 previne tampering
- **Chave**: 32 bytes derivados de SHA-256 (256 bits)
- **Compatibilidade**: Funciona em Python, Kivy, Android

### Limitações

- **Mesma chave em todos os apps**: Chave é derivada de seed conhecida, não é mantida em segredo
  - Aplicável para proteção contra exposição casual
  - Não protege contra adversário que conhece o código-fonte
  - Para máxima segurança, usar Hardware Security Module (HSM) em produção

- **Credenciais em RAM**: Não protege contra memory dumps enquanto apps estão rodando
  - Mitigação: Aplicar após validação, descartar quando não usar

### Boas Práticas

1. **Não commit credenciais em texto puro** no repositório
2. **Usar arquivo .key criptografado** para distribuição
3. **Descartar credenciais** após uso (não manter em variáveis globais)
4. **Usar HTTPS** quando trafegar credenciais
5. **Rotacionar chaves** periodicamente se necessário

## Compatibilidade

### Retrocompatibilidade

Função `carregar_licenca_de_arquivo()` detecta automaticamente se valor está criptografado:

```python
api_auth_raw = doc.get('api_authorization', '')

# Se valor já está criptografado, descriptografa
if is_encrypted(api_auth_raw):
    api_auth = decrypt_field(api_auth_raw)
else:
    api_auth = api_auth_raw  # Compatibilidade com formato antigo
```

**Resultado**: Arquivos `.key` antigos (sem criptografia) continuam funcionando.

## Testes

### Teste Unitário: `test_encryption.py`

```bash
python test_encryption.py
```

Valida:
- ✓ Criptografia e descriptografia
- ✓ Valores None/vazios
- ✓ Detecção de criptografia
- ✓ Compatibilidade com valores reais

### Teste Integrado: `test_encryption_integration.py`

```bash
python test_encryption_integration.py
```

Valida:
- ✓ Salvar arquivo com criptografia
- ✓ Carregar e descriptografar
- ✓ Compatibilidade com arquivos antigos
- ✓ Verificação de integridade

### Demonstração: `demo_encryption_security.py`

```bash
python demo_encryption_security.py
```

Mostra visualmente:
- Antes (inseguro) vs Depois (seguro)
- Fluxo de criptografia/descriptografia
- Especificação técnica

## Integração com CSCollect (Kivy)

Para descriptografar no APK Kivy:

```python
# Em models/db.py ou similar
from encryption import decrypt_field

def carregar_licenca():
    """Carrega credenciais descriptografadas"""
    payload, _ = carregar_licenca_de_arquivo(caminho_licenca)
    
    api_auth = payload.get('api_authorization')
    api_db_url = payload.get('api_database_url')
    
    # Usar credenciais...
    return api_auth, api_db_url
```

## Manutenção

### Adicionar Novo Campo Protegido

1. Adicionar ao `encrypt_field()` call em `salvar_licenca_json()`:
   ```python
   "novo_campo": encrypt_field(novo_campo),
   ```

2. Adicionar ao `decrypt_field()` call em `carregar_licenca_de_arquivo()`:
   ```python
   novo_valor = decrypt_field(valor_raw) if is_encrypted(valor_raw) else valor_raw,
   ```

3. Atualizar documentação

### Rotacionar Chave de Criptografia

Se necessário rotacionar a seed (com cuidado!):

1. Editar `ENCRYPTION_SEED` em `encryption.py`
2. Re-gerar todos os `.key` com os novos valores
3. Distribuir novos arquivos para clientes

## Referências

- [Cryptography Library](https://cryptography.io/)
- [Fernet Specification](https://github.com/fernet/spec)
- [NIST AES Specification](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.197.pdf)

## Histórico de Implementação

- **2026-06-23**: Implementação inicial de criptografia Fernet para `api_authorization` e `api_database_url`
- Removeu exposição de credenciais em `.key`
- Mantém compatibilidade com arquivos antigos
- Testes 100% validados

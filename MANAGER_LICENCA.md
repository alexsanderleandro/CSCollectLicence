# Guia de Integração - CSCollect Manager

## 📄 Formato do Arquivo de Licença (.key)

O arquivo `.key` gerado pelo CSCollectLicence está em formato **JSON** com a seguinte estrutura:

```json
{
  "cnpjs": ["12345678000199", "98765432000188"],
  "ids": ["a3e9e3a0a4659652", "device-123"],
  "token": "eyJjbnBqcyI6WyIxMjM0NTY3ODAwMDE5OSIsIjk4NzY1NDMyMDAwMTg4Il0sImlkc19jZWx1bGFyIjpbImEzZTllM2EwYTQ2NTk2NTIiLCJkZXZpY2UtMTIzIl0sInZhbGlkYWRlIjoiMjAyNi0xMi0zMSIsIm5vbWVfY2xpZW50ZSI6IkVtcHJlc2EgQUJDIiwic3FsX3NlcnZpZG9yIjoiU0VSVklET1IxIiwic3FsX2JhbmNvIjoiREJfUFJPRCIsImdlcmFkb19lbSI6IjIwMjYtMDQtMThUMTQ6MzA6NDVaIn0.abcd1234...",
  "validade": "2026-12-31",
  "database_url": "postgresql://user:pass@host.region.aws.neon.tech:5432/dbname"
}
```

### Campos do Arquivo

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cnpjs` | Array de strings | Lista de CNPJs autorizados a usar a licença |
| `ids` | Array de strings | Lista de IDs de celular/dispositivos autorizados |
| `token` | String | Token assinado (HMAC-SHA256) contendo payload + assinatura |
| `validade` | String ou null | Data de validade (YYYY-MM-DD) ou `null` para sem validade |
| `database_url` | String ou null | Connection string do PostgreSQL para validação online |

---

## 🔐 Validação da Licença

### 1. Carregamento do Arquivo

```python
import json

def carregar_licenca(caminho_key):
    """Carrega e parseia o arquivo .key"""
    try:
        with open(caminho_key, 'r', encoding='utf-8') as f:
            licenca = json.load(f)
        return licenca
    except FileNotFoundError:
        raise Exception(f"Arquivo de licença não encontrado: {caminho_key}")
    except json.JSONDecodeError:
        raise Exception("Arquivo de licença corrompido ou formato inválido")
```

### 2. Validação do Token (Offline)

O token contém um payload codificado + assinatura HMAC-SHA256. Para validar:

```python
import hmac
import hashlib
import base64

MASTER_KEY = "sua_chave_secreta_compartilhada"  # Deve ser a mesma do gerador

def validar_token(token):
    """Valida a assinatura do token e retorna o payload decodificado"""
    try:
        # Token formato: base64url(payload).base64url(signature)
        partes = token.split('.')
        if len(partes) != 2:
            raise ValueError("Formato de token inválido")
        
        payload_b64, assinatura_b64 = partes
        
        # Verifica a assinatura HMAC
        payload_bytes = payload_b64.encode('utf-8')
        assinatura_esperada = hmac.new(
            MASTER_KEY.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).digest()
        
        # Decodifica assinatura recebida (base64url -> bytes)
        assinatura_recebida = base64.urlsafe_b64decode(assinatura_b64 + '==')
        
        # Compara assinaturas (proteção contra timing attack)
        if not hmac.compare_digest(assinatura_esperada, assinatura_recebida):
            raise ValueError("Assinatura inválida - token foi adulterado")
        
        # Decodifica payload (base64url -> JSON)
        payload_json = base64.urlsafe_b64decode(payload_b64 + '==').decode('utf-8')
        payload = json.loads(payload_json)
        
        return payload
        
    except Exception as e:
        raise Exception(f"Falha ao validar token: {e}")
```

### 3. Validação de CNPJ e Device ID

```python
from datetime import datetime

def validar_licenca_completa(licenca, cnpj_atual, device_id_atual):
    """Valida licença completa: token, CNPJ, device ID e validade"""
    
    # 1. Valida o token e obtém o payload
    payload = validar_token(licenca['token'])
    
    # 2. Verifica CNPJ
    cnpjs_autorizados = licenca.get('cnpjs', [])
    if cnpj_atual not in cnpjs_autorizados:
        raise Exception(f"CNPJ {cnpj_atual} não autorizado nesta licença")
    
    # 3. Verifica Device ID
    ids_autorizados = licenca.get('ids', [])
    if device_id_atual not in ids_autorizados:
        raise Exception(f"Device ID {device_id_atual} não autorizado nesta licença")
    
    # 4. Verifica validade
    validade = licenca.get('validade')
    if validade:  # Se tiver validade definida
        data_validade = datetime.strptime(validade, '%Y-%m-%d').date()
        if datetime.now().date() > data_validade:
            raise Exception(f"Licença expirada em {validade}")
    
    # 5. Verifica consistência: payload do token deve corresponder ao arquivo
    if payload.get('cnpjs') != cnpjs_autorizados:
        raise Exception("Inconsistência detectada: CNPJs no token diferem do arquivo")
    
    if payload.get('ids_celular') != ids_autorizados:
        raise Exception("Inconsistência detectada: IDs no token diferem do arquivo")
    
    return True  # Licença válida!
```

---

## 🌐 Validação Online (Database)

### Obtendo a Connection String

```python
def obter_database_url(licenca):
    """Extrai a connection string da licença"""
    database_url = licenca.get('database_url')
    
    if not database_url:
        raise Exception("Licença não contém database_url para validação online")
    
    return database_url
```

### Validação no Banco de Dados

```python
import psycopg2

def validar_licenca_online(licenca, cnpj_atual, device_id_atual):
    """Valida licença consultando o banco de dados online"""
    
    # 1. Obtém a connection string
    database_url = obter_database_url(licenca)
    
    # 2. Conecta ao banco
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # 3. Busca registro pela combinação de CNPJs
        cnpjs_str = ','.join(sorted(licenca['cnpjs']))  # Ordena para consistência
        
        query = """
            SELECT cnpj, idcelular, token, validade, ativo, nome_cliente 
            FROM clientes 
            WHERE cnpj = %s
        """
        cursor.execute(query, (cnpjs_str,))
        resultado = cursor.fetchone()
        
        if not resultado:
            raise Exception("Licença não encontrada no banco de dados")
        
        cnpj_db, idcelular_db, token_db, validade_db, ativo_db, nome_cliente_db = resultado
        
        # 4. Verifica se está ativa
        if not ativo_db:
            raise Exception("Licença desativada no servidor")
        
        # 5. Verifica se o token corresponde
        if token_db != licenca['token']:
            raise Exception("Token não corresponde ao registrado no servidor")
        
        # 6. Verifica CNPJ específico (dentro da lista)
        cnpjs_db_list = cnpj_db.split(',')
        if cnpj_atual not in cnpjs_db_list:
            raise Exception(f"CNPJ {cnpj_atual} não autorizado")
        
        # 7. Verifica Device ID
        ids_db_list = idcelular_db.split(',') if idcelular_db else []
        if device_id_atual not in ids_db_list:
            raise Exception(f"Device ID {device_id_atual} não autorizado")
        
        # 8. Verifica validade
        if validade_db:
            data_validade = datetime.strptime(validade_db, '%Y-%m-%d').date()
            if datetime.now().date() > data_validade:
                raise Exception(f"Licença expirada em {validade_db}")
        
        cursor.close()
        conn.close()
        
        return {
            'valida': True,
            'nome_cliente': nome_cliente_db,
            'validade': validade_db,
            'ativo': ativo_db
        }
        
    except psycopg2.Error as e:
        raise Exception(f"Erro ao validar licença online: {e}")
```

---

## 🔄 Fluxo Recomendado de Validação

### Estratégia Híbrida (Offline + Online)

```python
def validar_licenca_hibrida(caminho_key, cnpj_atual, device_id_atual, online=True):
    """
    Valida licença com estratégia híbrida:
    1. Sempre valida offline (token, CNPJ, device, validade)
    2. Se online=True e database_url disponível, valida também no servidor
    """
    
    # Carrega licença
    licenca = carregar_licenca(caminho_key)
    
    # Validação offline (obrigatória)
    try:
        validar_licenca_completa(licenca, cnpj_atual, device_id_atual)
        print("✓ Validação offline: OK")
    except Exception as e:
        raise Exception(f"Validação offline falhou: {e}")
    
    # Validação online (opcional, mas recomendada)
    if online and licenca.get('database_url'):
        try:
            info_online = validar_licenca_online(licenca, cnpj_atual, device_id_atual)
            print(f"✓ Validação online: OK - Cliente: {info_online['nome_cliente']}")
            return info_online
        except Exception as e:
            print(f"⚠ Validação online falhou: {e}")
            print("  Prosseguindo com validação offline...")
            # Não bloqueia se online falhar (servidor pode estar indisponível)
    
    return {'valida': True}
```

---

## 📋 Exemplo Completo de Uso

```python
# manager_licenca.py
import json
import hmac
import hashlib
import base64
from datetime import datetime
import psycopg2

# Configurações
MASTER_KEY = "sua_chave_secreta_aqui"
CAMINHO_LICENCA = "licenca.key"

# Dados do ambiente
CNPJ_EMPRESA = "12345678000199"
DEVICE_ID = "a3e9e3a0a4659652"

def main():
    try:
        # Valida licença (offline + online)
        resultado = validar_licenca_hibrida(
            CAMINHO_LICENCA,
            CNPJ_EMPRESA,
            DEVICE_ID,
            online=True  # Tenta validação online se disponível
        )
        
        print("\n✅ LICENÇA VÁLIDA")
        print(f"   Cliente: {resultado.get('nome_cliente', 'N/A')}")
        print(f"   Validade: {resultado.get('validade', 'Sem validade')}")
        
        # Inicia aplicação...
        iniciar_aplicacao()
        
    except Exception as e:
        print(f"\n❌ LICENÇA INVÁLIDA: {e}")
        print("   Aplicação não pode iniciar.")
        exit(1)

if __name__ == "__main__":
    main()
```

---

## 🛠️ Dependências

### Python
```bash
pip install psycopg2-binary
```

### Android (APK)
```gradle
dependencies {
    implementation 'org.postgresql:postgresql:42.6.0'
    implementation 'org.json:json:20230618'
}
```

---

## 🔒 Segurança

### ⚠️ IMPORTANTE

1. **MASTER_KEY deve ser mantida em segredo absoluto**
   - Nunca commitar no Git
   - Armazenar em variáveis de ambiente ou configuração criptografada
   - Mesma chave usada no gerador e validador

2. **Connection String (database_url)**
   - Contém credenciais sensíveis
   - Usar usuário com permissões **somente leitura** (SELECT)
   - Considerar uso de connection pooling para APK

3. **Validação Offline sempre primeiro**
   - Impede uso sem conexão
   - Valida integridade criptográfica
   - Servidor online é camada adicional de segurança

4. **Tratamento de erros**
   - Não expor detalhes técnicos ao usuário final
   - Logar tentativas de acesso com licença inválida
   - Considerar limite de tentativas

---

## 📞 Suporte

Em caso de dúvidas sobre integração:
1. Verifique se está usando a mesma `MASTER_KEY`
2. Valide o formato do arquivo `.key` (deve ser JSON válido)
3. Teste a connection string isoladamente
4. Verifique se o registro existe no banco (consultar tabela `clientes`)

---

## 🆕 Changelog

### Versão 2.0 (Abril 2026)
- ✅ Formato JSON padronizado
- ✅ Campo `database_url` para validação online
- ✅ Suporte a múltiplos CNPJs e dispositivos
- ✅ Campo `nome_cliente` no banco de dados
- ✅ Validação híbrida (offline + online)

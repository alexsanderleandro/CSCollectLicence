# Referência de Integração — Leitura e Validação de Licença via Banco Neon

> **Versão:** 2026-05  
> **Aplica-se a:** CSCollectManager e APK Android 

---

## 1. Visão Geral do Fluxo

```
Banco Neon (tabela clientes)
  ├── cnpj                  → "12345678000199,98765432000188"  (chave primária)
  ├── idcelular             → "a3e9e3a0a4659652,device-123"
  ├── token                 → "eyJjbnBqcy....<sig>"            (HMAC-SHA256 assinado)
    ├── arq_licenca           → "{ ...conteúdo do arquivo .key... }"  (texto completo para download remoto)
  ├── validade              → "2026-12-31"
  ├── ativo                 → true
  ├── nome_cliente          → "Empresa ABC"
  ├── sql_servidor          → "SERVIDOR1"
  ├── sql_banco             → "DB_PROD"
  ├── api_authorization     → "<base64(nonce12 + AES-256-GCM ciphertext)>"  ← CRIPTOGRAFADO
  └── api_database_url      → "<base64(nonce12 + AES-256-GCM ciphertext)>"  ← CRIPTOGRAFADO
```

### Etapas obrigatórias para o cliente

1. **Consultar** o registro no banco pelo CNPJ da empresa
2. **Verificar** `ativo = true` e `validade >= hoje`
3. **Validar assinatura HMAC** do campo `token`
4. **Verificar** se o CNPJ e o ID do dispositivo estão autorizados no token
5. **Descriptografar** (apenas se necessário usar API) `api_authorization` e/ou `api_database_url` em memória
6. **Usar** o valor e **descartar** — jamais persistir em disco

---

## 2. Criptografia dos Campos Sensíveis

### 2.1 Algoritmo

| Parâmetro | Valor |
|-----------|-------|
| Algoritmo | AES-256-GCM |
| Tamanho da chave | 256 bits (32 bytes) |
| Tamanho do nonce | 96 bits (12 bytes) — gerado aleatoriamente por registro |
| Tag de autenticação | 128 bits (16 bytes) — concatenado ao ciphertext pelo GCM |
| Encoding de saída | Base64 padrão (RFC 4648) |
| Formato no banco | `Base64( nonce[12 bytes] ‖ ciphertext+tag[N+16 bytes] )` |

### 2.2 Derivação da chave AES

A chave AES-256 é derivada da **MASTER_KEY** usando **SHA-256**:

```
AES_KEY = SHA256( UTF8(MASTER_KEY) )   →  32 bytes
```

> ⚠️ A mesma `MASTER_KEY` usada para assinar tokens HMAC é usada para derivar a chave AES.  
> Ela **nunca** transita pela rede nem fica gravada no banco.

### 2.3 Formato do ciphertext no banco

```
campo_no_banco = Base64( nonce[0..11] || aes_gcm_ciphertext_with_tag[12..] )
```

- Bytes `[0..11]` (12 bytes) → **nonce/IV** aleatório
- Bytes `[12..]` → **ciphertext + GCM tag** (16 bytes de tag ao final, embutidos automaticamente pela biblioteca AES-GCM)

---

## 3. Implementações de Referência

### 3.1 C# (.NET 6+) — CSCollectManager

```csharp
using System;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

public static class LicencaCrypto
{
    /// <summary>
    /// Deriva a chave AES-256 a partir da MASTER_KEY (SHA-256).
    /// </summary>
    public static byte[] DeriveKey(string masterKey)
    {
        return SHA256.HashData(Encoding.UTF8.GetBytes(masterKey));
    }

    /// <summary>
    /// Descriptografa um campo AES-256-GCM armazenado no banco.
    /// Formato do ciphertext (Base64): nonce[12] || ciphertext+tag
    /// </summary>
    public static string DecryptField(string base64Ciphertext, string masterKey)
    {
        if (string.IsNullOrWhiteSpace(base64Ciphertext))
            return string.Empty;

        byte[] key   = DeriveKey(masterKey);
        byte[] raw   = Convert.FromBase64String(base64Ciphertext);

        byte[] nonce      = raw[..12];           // primeiros 12 bytes
        byte[] cipherData = raw[12..];           // restante (ciphertext + tag de 16 bytes)

        // GCM tag = últimos 16 bytes do cipherData
        byte[] tag        = cipherData[^16..];
        byte[] cipherOnly = cipherData[..^16];

        byte[] plaintext = new byte[cipherOnly.Length];

        using var aes = new AesGcm(key, AesGcm.TagByteSizes.MaxSize); // tag = 16 bytes
        aes.Decrypt(nonce, cipherOnly, tag, plaintext);

        return Encoding.UTF8.GetString(plaintext);
    }
}
```

#### Validação do token HMAC-SHA256

```csharp
using System;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

public static class LicencaToken
{
    /// <summary>
    /// Valida a assinatura do token e retorna o payload como JsonDocument.
    /// Formato do token: Base64Url(payload) + "." + Base64Url(hmac_sha256)
    /// </summary>
    public static JsonDocument VerifyToken(string token, string masterKey)
    {
        var parts = token.Split('.');
        if (parts.Length != 2)
            throw new InvalidOperationException("Formato de token inválido.");

        byte[] payloadBytes = Base64UrlDecode(parts[0]);
        byte[] sigReceived  = Base64UrlDecode(parts[1]);

        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(masterKey));
        byte[] sigExpected = hmac.ComputeHash(payloadBytes);

        if (!CryptographicOperations.FixedTimeEquals(sigExpected, sigReceived))
            throw new InvalidOperationException("Assinatura inválida — token adulterado.");

        return JsonDocument.Parse(payloadBytes);
    }

    private static byte[] Base64UrlDecode(string s)
    {
        // Reconstitui padding e converte de URL-safe para padrão
        s = s.Replace('-', '+').Replace('_', '/');
        switch (s.Length % 4)
        {
            case 2: s += "=="; break;
            case 3: s += "=";  break;
        }
        return Convert.FromBase64String(s);
    }
}
```

#### Exemplo completo de uso (C#)

```csharp
string masterKey = Environment.GetEnvironmentVariable("MASTER_KEY")
    ?? throw new Exception("MASTER_KEY não definida.");

// 1. Buscar registro no banco (Npgsql, Dapper, EF, etc.)
//    SELECT cnpj, idcelular, token, arq_licenca, validade, ativo, nome_cliente,
//           sql_servidor, sql_banco, api_authorization, api_database_url
//    FROM clientes WHERE cnpj LIKE '%' + cnpjEmpresa + '%'

string cnpjEmpresa  = "12345678000199";
string deviceId     = "a3e9e3a0a4659652";

// (assumindo que 'row' veio do banco)
if (!row.ativo)
    throw new Exception("Licença desativada.");

if (row.validade != null && DateTime.Parse(row.validade) < DateTime.Today)
    throw new Exception("Licença expirada.");

// 2. Validar assinatura do token
using var payload = LicencaToken.VerifyToken(row.token, masterKey);

// 3. Verificar CNPJ e device no token assinado
var cnpjsNoToken = payload.RootElement.GetProperty("cnpjs")
                           .EnumerateArray().Select(x => x.GetString()).ToList();
var idsNoToken   = payload.RootElement.GetProperty("ids_celular")
                           .EnumerateArray().Select(x => x.GetString()).ToList();

if (!cnpjsNoToken.Contains(cnpjEmpresa))
    throw new Exception($"CNPJ {cnpjEmpresa} não autorizado.");
if (!idsNoToken.Contains(deviceId))
    throw new Exception($"Device {deviceId} não autorizado.");

// 4. Descriptografar campos sensíveis (apenas se precisar usar)
string bearerToken  = LicencaCrypto.DecryptField(row.api_authorization, masterKey);
string databaseUrl  = LicencaCrypto.DecryptField(row.api_database_url,  masterKey);

// 5. Usar e DESCARTAR — nunca persistir
// Ex: httpClient.DefaultRequestHeaders.Authorization =
//         new AuthenticationHeaderValue("Bearer", bearerToken);
// bearerToken = null; // auxilia o GC
```

---

### 3.2 Kotlin (Android APK)

#### Dependências (`build.gradle.kts`)

```kotlin
// Sem dependências externas; usa javax.crypto nativo do Android
```

#### Descriptografia AES-256-GCM

```kotlin
import android.util.Base64
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

object LicencaCrypto {

    /** Deriva chave AES-256 a partir da MASTER_KEY via SHA-256. */
    fun deriveKey(masterKey: String): ByteArray =
        MessageDigest.getInstance("SHA-256")
            .digest(masterKey.toByteArray(Charsets.UTF_8))

    /**
     * Descriptografa um campo AES-256-GCM armazenado no banco.
     * Formato (Base64 padrão): nonce[12] || ciphertext+tag
     */
    fun decryptField(base64Ciphertext: String, masterKey: String): String {
        if (base64Ciphertext.isBlank()) return ""

        val raw    = Base64.decode(base64Ciphertext, Base64.DEFAULT)
        val nonce  = raw.copyOfRange(0, 12)
        val ctPlusTag = raw.copyOfRange(12, raw.size)

        val keySpec = SecretKeySpec(deriveKey(masterKey), "AES")
        val gcmSpec = GCMParameterSpec(128, nonce)   // tag = 128 bits

        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, keySpec, gcmSpec)

        return cipher.doFinal(ctPlusTag).toString(Charsets.UTF_8)
    }
}
```

#### Validação do token HMAC-SHA256

```kotlin
import android.util.Base64
import org.json.JSONObject
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

object LicencaToken {

    /**
     * Valida a assinatura HMAC-SHA256 do token e retorna o payload como JSONObject.
     * Formato: Base64Url(payload) + "." + Base64Url(hmac)
     */
    fun verifyToken(token: String, masterKey: String): JSONObject {
        val parts = token.split(".")
        require(parts.size == 2) { "Formato de token inválido." }

        val payloadBytes  = base64UrlDecode(parts[0])
        val sigReceived   = base64UrlDecode(parts[1])

        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(masterKey.toByteArray(Charsets.UTF_8), "HmacSHA256"))
        val sigExpected = mac.doFinal(payloadBytes)

        check(sigExpected.contentEquals(sigReceived)) {
            "Assinatura inválida — token adulterado."
        }

        return JSONObject(String(payloadBytes, Charsets.UTF_8))
    }

    private fun base64UrlDecode(s: String): ByteArray {
        var b64 = s.replace('-', '+').replace('_', '/')
        when (b64.length % 4) {
            2    -> b64 += "=="
            3    -> b64 += "="
        }
        return Base64.decode(b64, Base64.DEFAULT)
    }
}
```

#### Exemplo completo de uso (Kotlin)

```kotlin
val masterKey  = BuildConfig.MASTER_KEY   // definida em local.properties / CI, nunca no repo

// 1. Buscar registro no banco (Neon via HTTPS/REST ou JDBC conforme arquitetura)
//    GET /clientes?cnpj=eq.12345678000199  (PostgREST)
//    ou SELECT ... FROM clientes WHERE cnpj LIKE '%12345678000199%'

val cnpjEmpresa = "12345678000199"
val deviceId    = obterAndroidId()   // ID único do dispositivo

// (assumindo 'row' como data class preenchida da resposta)
check(row.ativo)                            { "Licença desativada." }
row.validade?.let {
    check(LocalDate.parse(it) >= LocalDate.now()) { "Licença expirada." }
}

// 2. Validar token assinado
val payload = LicencaToken.verifyToken(row.token, masterKey)

// 3. Verificar CNPJ e device
val cnpjsAutorizados = payload.getJSONArray("cnpjs")
    .let { a -> (0 until a.length()).map { a.getString(it) } }
val idsAutorizados   = payload.getJSONArray("ids_celular")
    .let { a -> (0 until a.length()).map { a.getString(it) } }

check(cnpjEmpresa in cnpjsAutorizados) { "CNPJ $cnpjEmpresa não autorizado." }
check(deviceId    in idsAutorizados)   { "Dispositivo $deviceId não autorizado." }

// 4. Descriptografar em memória apenas se precisar chamar a API
val bearerToken = LicencaCrypto.decryptField(row.apiAuthorization, masterKey)
val databaseUrl = LicencaCrypto.decryptField(row.apiDatabaseUrl,  masterKey)

// 5. Usar e DESCARTAR
// httpClient.addHeader("Authorization", "Bearer $bearerToken")
// bearerToken = ""   // ajuda o GC
```

---

## 4. Estrutura do Payload do Token

O campo `token` do banco contém:

```
<Base64Url(JSON_payload)>.<Base64Url(HMAC_SHA256)>
```

Após decodificar e verificar a assinatura, o JSON do payload tem a seguinte estrutura:

```json
{
  "cnpjs":        ["12345678000199", "98765432000188"],
  "ids_celular":  ["a3e9e3a0a4659652", "device-123"],
  "validade":     "2026-12-31",
  "nome_cliente": "Empresa ABC",
  "sql_servidor": "SERVIDOR1",
  "sql_banco":    "DB_PROD",
  "gerado_em":    "2026-05-15T14:30:00-03:00"
}
```

> Os campos `api_authorization` e `api_database_url` **não estão no payload do token** — eles existem apenas nas colunas criptografadas do banco.

---

## 5. Tabela de Campos — `clientes`

| Coluna | Tipo | Sensível | Como usar |
|--------|------|----------|-----------|
| `cnpj` | varchar(255) | Não | Chave primária. Um ou mais CNPJs separados por vírgula |
| `idcelular` | text | Não | Um ou mais IDs de dispositivo separados por vírgula |
| `token` | text | Não | Token HMAC-SHA256 — validar assinatura antes de usar |
| `arq_licenca` | text | Não | Conteúdo textual completo do arquivo `.key`, para download via API/ponte |
| `validade` | varchar(10) | Não | YYYY-MM-DD ou NULL (sem validade) |
| `ativo` | boolean | Não | Verificar antes de qualquer operação |
| `nome_cliente` | varchar(30) | Não | Nome do cliente para exibição |
| `sql_servidor` | varchar(30) | Não | Nome do servidor SQL local do cliente |
| `sql_banco` | varchar(30) | Não | Nome do banco SQL local do cliente |
| `api_authorization` | text | **SIM** | Bearer token criptografado AES-256-GCM — descriptografar em memória |
| `api_database_url` | text | **SIM** | Connection string criptografada AES-256-GCM — descriptografar em memória |
| `reginclusao` | timestamptz | Não | Data/hora de criação do registro |
| `dataalteracao` | timestamptz | Não | Data/hora da última atualização |

---

## 6. Regras de Segurança

| Regra | Descrição |
|-------|-----------|
| ✅ Sempre validar HMAC primeiro | Verificar assinatura do `token` **antes** de qualquer outra lógica |
| ✅ Descriptografar só em memória | Nunca persistir os valores descriptografados em disco, log ou variável de sessão de longa duração |
| ✅ Verificar `ativo` | Licença pode ser revogada; campo `ativo = false` deve bloquear acesso imediatamente |
| ✅ Verificar validade | Comparar `validade` com a data atual no servidor/dispositivo |
| ✅ Verificar CNPJ no token | O CNPJ deve estar na lista `cnpjs` do **payload do token** (não apenas no banco) |
| ✅ Verificar device ID no token | O ID do dispositivo deve estar em `ids_celular` do **payload do token** |
| ❌ Nunca logar o plaintext | Não escrever `bearerToken` ou `databaseUrl` descriptografados em logs |
| ❌ Nunca commitar MASTER_KEY | Usar variável de ambiente, KeyVault, HSM ou configuração segura de CI/CD |
| ❌ Nunca confiar só no banco | O banco pode ser manipulado; a assinatura HMAC do token é a raiz de confiança |

---

## 7. Consulta SQL Recomendada

### Busca por CNPJ único (mais comum)

```sql
SELECT cnpj, idcelular, token, arq_licenca, validade, ativo, nome_cliente,
       sql_servidor, sql_banco, api_authorization, api_database_url
FROM clientes
WHERE cnpj = '12345678000199'          -- CNPJ único (chave primária exata)
   OR cnpj LIKE '%,12345678000199'      -- último CNPJ na lista
   OR cnpj LIKE '12345678000199,%'      -- primeiro CNPJ na lista
   OR cnpj LIKE '%,12345678000199,%';   -- CNPJ no meio da lista
```

> **Sugestão de otimização:** se a coluna `cnpj` armazenar sempre um único CNPJ por linha (em vez de lista), use `WHERE cnpj = '...'` direto. Consulte a arquitetura atual do banco antes de escolher a query.

### Via PostgREST (Neon REST API)

```
GET /clientes?cnpj=eq.12345678000199
Authorization: Bearer <service_role_jwt>
```

---

## 8. Checklist de Validação

```
[ ] 1. Registro encontrado no banco pelo CNPJ
[ ] 2. ativo == true
[ ] 3. validade == null  OU  validade >= hoje
[ ] 4. Assinatura HMAC-SHA256 do token: VÁLIDA
[ ] 5. cnpj da empresa presente em payload.cnpjs
[ ] 6. device_id presente em payload.ids_celular
[ ] 7. (se necessário) api_authorization descriptografado em memória
[ ] 8. (se necessário) api_database_url  descriptografado em memória
[ ] 9. Valores sensíveis descartados após uso
```

---

## 9. Testando a Implementação

### Verificar criptografia (Python — ambiente do gerador)

```python
from licenca import _encrypt_field, _decrypt_field

enc = _encrypt_field("meu_bearer_token_secreto")
print("Criptografado:", enc)

dec = _decrypt_field(enc)
print("Descriptografado:", dec)
assert dec == "meu_bearer_token_secreto"
```

### Verificar token HMAC (Python)

```python
import os
os.environ["MASTER_KEY"] = "sua_master_key"
from licenca import verificar_licenca, carregar_licenca_de_arquivo

payload, token = carregar_licenca_de_arquivo("Licenca_CSCollectManager_CLIENTE.key")
print(payload)
```

---

## 10. Compatibilidade entre Plataformas

| Plataforma | Biblioteca AES-GCM | Biblioteca HMAC |
|------------|-------------------|-----------------|
| Python | `cryptography.hazmat.primitives.ciphers.aead.AESGCM` | `hmac` (stdlib) |
| C# / .NET 6+ | `System.Security.Cryptography.AesGcm` | `System.Security.Cryptography.HMACSHA256` |
| Kotlin / Android | `javax.crypto.Cipher("AES/GCM/NoPadding")` | `javax.crypto.Mac("HmacSHA256")` |
| Java | `javax.crypto.Cipher("AES/GCM/NoPadding")` | `javax.crypto.Mac("HmacSHA256")` |

> Todas as plataformas acima utilizam o **mesmo formato de dados** — Base64 padrão para os campos criptografados e Base64Url para o token HMAC. A interoperabilidade é garantida desde que a `MASTER_KEY` seja a mesma.

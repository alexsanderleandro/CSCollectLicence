# Integração: novo campo `tipo_licenca` no token de licença

Documento para orientar o ajuste da validação de licença/token no **APK** e da validação
de licença no **CSCollect Manager** (doravante "apps clientes"), após a mudança feita no
`CSCollectLicence` (gerador de licenças) que introduziu o campo `tipo_licenca` (`"Lite"` /
`"Pro"`).

## TL;DR — o que muda de fato para quem só valida assinatura

**Nada quebra.** A assinatura HMAC-SHA256 é calculada sobre os **bytes brutos** do JSON, não
sobre um conjunto fixo de campos. Qualquer verificador que:

1. decodifica a parte do payload em base64url para obter os bytes brutos,
2. recalcula `HMAC-SHA256(bytes_brutos, MASTER_KEY)` e compara com a assinatura,
3. só **depois** faz `JSON.parse` desses mesmos bytes para ler os campos que precisa,

continua validando normalmente licenças antigas e novas, sem nenhuma alteração de código —
o campo novo é só mais uma chave no JSON, ignorada por quem não olha para ela.

**Isso só deixa de ser verdade se o verificador re-serializa o JSON antes de comparar a
assinatura** (ex.: monta um objeto/dict a partir de campos conhecidos e gera JSON de novo
para validar) — nesse caso ele vai gerar bytes diferentes dos originais e a verificação vai
falhar para tokens novos. **Confirme qual dos dois padrões o APK e o Manager usam antes de
mexer em qualquer coisa** — se já seguem o padrão "bytes brutos primeiro", não é necessário
nenhum ajuste para continuar aceitando os tokens; só é necessário ajuste se quiserem
**usar** o campo `tipo_licenca` para liberar/bloquear funcionalidades.

## O que mudou no gerador (`CSCollectLicence`)

Repositório: `CSCollectLicence`, arquivo `licenca.py`, função `gerar_licenca()`.

Antes, o payload assinado tinha estas chaves:

```
cnpjs, nomes, ids_celular, validade, nome_cliente, sql_servidor, sql_banco, gerado_em
```

Agora tem uma chave nova, `tipo_licenca`, com valor **sempre** `"Lite"` ou `"Pro"` (validado
na geração — nenhum outro valor é aceito):

```
cnpjs, nomes, ids_celular, validade, nome_cliente, sql_servidor, sql_banco, tipo_licenca, gerado_em
```

Licenças/tokens gerados **antes** desta mudança não têm a chave `tipo_licenca` — devem ser
tratados como `"Lite"` por quem for consumir o campo (ver seção de compatibilidade).

O arquivo `.key` (envelope JSON salvo em disco, fora do token assinado) também passou a
incluir `tipo_licenca` (redundante com o token, por conveniência de leitura), junto com dois
outros campos novos que **não afetam a assinatura** (são só metadado, adicionados numa
mudança anterior): `qtde_cnpjs` e `qtde_devices`.

## Formato completo do token assinado

```
token = base64url(json_payload_bytes) + "." + base64url(hmac_sha256(json_payload_bytes, MASTER_KEY))
```

- `base64url` = Base64 URL-safe **sem padding** (`=` removido no encode; reconstituído no
  decode completando com `=` até o próximo múltiplo de 4).
- `json_payload_bytes` = `json.dumps(payload, separators=(",", ":"), ensure_ascii=False)`
  codificado em UTF-8 — **mas para efeitos de verificação isso não importa**: o verificador
  nunca precisa re-serializar, só decodificar o base64url e comparar/ler os bytes que já
  vieram prontos.
- `MASTER_KEY` = mesma chave secreta compartilhada entre `CSCollectLicence`, o APK e o
  Manager (variável de ambiente `MASTER_KEY`, UTF-8 encoded como bytes da chave HMAC).
- Algoritmo: `HMAC-SHA256`.

### Exemplo real de token gerado com `tipo_licenca = "Pro"`

Token completo:
```
eyJjbnBqcyI6WyIxMjM0NTY3ODAwMDE5OSIsIjk4NzY1NDMyMDAwMTg4Il0sIm5vbWVzIjpbIkVtcHJlc2EgRXhlbXBsbyBMdGRhIiwiRW1wcmVzYSBFeGVtcGxvIEZpbGlhbCJdLCJpZHNfY2VsdWxhciI6WyJkZXZpY2UtYWJjMTIzIl0sInZhbGlkYWRlIjoiMjAyNi0xMi0zMSIsIm5vbWVfY2xpZW50ZSI6IkVtcHJlc2EgRXhlbXBsbyBMdGRhLEVtcHJlc2EgRXhlbXBsbyBGaWxpYWwiLCJzcWxfc2Vydmlkb3IiOiJTUlYtRVhFTVBMTyIsInNxbF9iYW5jbyI6IkJBTkNPRVhFTVBMTyIsInRpcG9fbGljZW5jYSI6IlBybyIsImdlcmFkb19lbSI6IjIwMjYtMDgtMDdUMTE6MTY6MzItMDM6MDAifQ.IFvc9KQgtMnGy-B0RGozZtiQ4sF77NZJ97Eui_gh2TM
```

Payload decodificado (bytes exatos que foram assinados — é isso que precisa bater com a
assinatura, byte a byte):
```json
{"cnpjs":["12345678000199","98765432000188"],"nomes":["Empresa Exemplo Ltda","Empresa Exemplo Filial"],"ids_celular":["device-abc123"],"validade":"2026-12-31","nome_cliente":"Empresa Exemplo Ltda,Empresa Exemplo Filial","sql_servidor":"SRV-EXEMPLO","sql_banco":"BANCOEXEMPLO","tipo_licenca":"Pro","gerado_em":"2026-08-07T11:16:32-03:00"}
```

### Exemplo de arquivo `.key` completo (envelope, o que fica em disco)

```json
{
  "cnpjs": ["12345678000199"],
  "nomes": ["Empresa Exemplo Ltda"],
  "ids": ["device-abc123"],
  "token": "eyJjbnBqcyI6...6usGwqu4d-oprXZY1Q2o6EJ1oThcK2Z7SOHWxQY0qY4",
  "validade": "2026-12-31",
  "api_url": "https://api.exemplo.com",
  "api_authorization": "gAAAAABqdejJhtnsGxpq8EYI...(criptografado, Fernet)",
  "api_database_url": "gAAAAABqdejJLo6wk5taqFD3...(criptografado, Fernet)",
  "nome_cliente": "Empresa Exemplo Ltda",
  "sql_servidor": "SRV-EXEMPLO",
  "sql_banco": "BANCOEXEMPLO",
  "qtde_cnpjs": 1,
  "qtde_devices": 1,
  "tipo_licenca": "Pro"
}
```

Nota sobre `api_authorization`/`api_database_url`: continuam criptografados com **Fernet**
(biblioteca `cryptography`, módulo `encryption.py` do `CSCollectLicence`) — isso **não
mudou** nesta atualização e é independente da assinatura do token. Se o APK/Manager já
sabem decifrar esses dois campos, nenhum ajuste é necessário ali.

## Algoritmo de verificação (referência, para reimplementar/conferir em qualquer linguagem)

Pseudocódigo equivalente ao `verificar_licenca()` de `licenca.py`:

```
função verificar_licenca(token, master_key):
    partes = token.split(".")
    se len(partes) != 2: erro "formato inválido"

    payload_bytes = base64url_decode(partes[0])   # bytes BRUTOS, não re-serializar
    assinatura_recebida = base64url_decode(partes[1])

    assinatura_esperada = HMAC_SHA256(payload_bytes, master_key)
    se not comparar_em_tempo_constante(assinatura_recebida, assinatura_esperada):
        erro "assinatura inválida"

    payload = JSON.parse(payload_bytes)   # só agora, para LER os campos

    se payload.validade existir:
        # aceita "YYYY-MM-DD" (data) OU ISO 8601 com hora/timezone
        se validade < agora: erro "licença expirada"

    retorna payload
```

Pontos de atenção para portar a validação para outra linguagem/stack:
- Usar comparação de assinatura **em tempo constante** (ex.: `hmac.compare_digest` em
  Python, `MessageDigest.isEqual` / `MacUtil` equivalente em Java/Kotlin), não `==` simples.
- `base64url_decode` precisa reconstituir o padding (`=`) removido no encode — string
  original tem `-`/`_` no lugar de `+`/`/`, sem `=` no final.
- **Não** reconstruir o JSON a partir de campos individuais para depois assinar/comparar —
  sempre operar sobre os bytes brutos decodificados do token.

## Compatibilidade — tokens/licenças antigos sem `tipo_licenca`

Ao ler o payload verificado, se a chave `tipo_licenca` não existir (token gerado antes desta
mudança), tratar como `"Lite"`:

```
tipo_licenca = payload.get("tipo_licenca", "Lite")
```

Essa é a mesma regra usada no lado do gerador (`CSCollectLicence`) para o arquivo `.key` e
para o banco Neon: **licenças antigas = Lite por padrão**.

## O que o APK e o Manager precisam decidir/implementar

O `CSCollectLicence` só gera e assina o campo — a aplicação da regra de negócio (o que
"Lite" libera/bloqueia versus "Pro") é responsabilidade de cada app cliente. Sugestão de
escopo do que precisa ser feito em cada lugar:

1. **APK**: após validar a assinatura do token (fluxo que já existe), ler
   `payload.get("tipo_licenca", "Lite")` e usar esse valor para decidir quais telas/recursos
   ficam disponíveis. Definir a lista de features restritas ao Pro é decisão do time do APK,
   não deste documento.
2. **CSCollect Manager**: mesma leitura (`tipo_licenca`, fallback `"Lite"`) a partir do
   payload já validado, ao carregar a licença. Aplicar as mesmas restrições de feature-gating
   que o time do Manager definir.
3. Em ambos: se o fluxo de ativação online for usado (token avulso da tabela
   `activation_tokens`, gerado por `gerar_activation_token()`), essa tabela agora também tem
   uma coluna `tipo_licenca` (`'Lite'`/`'Pro'`, default `'Lite'`) — mas ela só existe no
   **banco** (Neon), não em nenhum token/arquivo assinado; é apenas para consulta/auditoria
   administrativa. O fluxo de ativação em si (o que o APK recebe do backend ao ativar) deve
   continuar vindo do token assinado gerado nesse momento (que já inclui `tipo_licenca` se
   gerado após esta atualização), não da coluna do banco diretamente.

## Referência rápida — banco de dados (Neon)

Migração aplicada: `migration_neon_schema_v10.sql` (repositório `CSCollectLicence`).

| Tabela | Coluna | Tipo | Default | Observação |
|---|---|---|---|---|
| `clientes` | `tipo_licenca` | `VARCHAR(10)` | `'Lite'` | `CHECK (tipo_licenca IN ('Lite','Pro'))`. Espelha o valor assinado no token da licença. |
| `activation_tokens` | `tipo_licenca` | `VARCHAR(10)` | `'Lite'` | `CHECK (tipo_licenca IN ('Lite','Pro'))`. Só para consulta administrativa (painel do `CSCollectLicence`) — o token avulso em si já carrega essa informação assinada. |

Ambas as colunas já foram aplicadas em produção; registros pré-existentes foram
automaticamente marcados `'Lite'` pelo `DEFAULT` do Postgres.

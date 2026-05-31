# CSCollectAPI — Ajustes de Licença (arq_licenca)

## Objetivo
Disponibilizar o arquivo de licença armazenado em `clientes.arq_licenca` para download remoto (APK e CSCollectManager), mantendo as validações já existentes (`cnpj`, `device_id`, `ativo`, `validade`).

---

## Endpoints esperados

### 1) `POST /validar-licenca`
**Entrada (JSON):**

```json
{
  "cnpj": "12345678000199",
  "device_id": "SEU_DEVICE"
}
```

**Saída esperada (quando válido):**

```json
{
  "ok": true,
  "mensagem": "Licenca valida",
  "validade": "2026-12-31",
  "nome_cliente": "Empresa X",
  "cnpjs": ["12345678000199"],
  "ids": ["SEU_DEVICE"],
  "sql_servidor": "SERVIDOR",
  "sql_banco": "BANCO",
  "token": "...",
  "arq_licenca": "{...conteudo do .key...}",
  "api_authorization": "...",
  "api_database_url": "...",
  "download_url": "/download-licenca?cnpj=12345678000199&device_id=SEU_DEVICE"
}
```

### 2) `GET /download-licenca?cnpj=...&device_id=...`
**Comportamento esperado:**
- Valida licença (registro, ativo, validade e device autorizado)
- Retorna o arquivo `.key` como `application/octet-stream`
- Nome sugerido: `Licenca_CSCollectManager_<cliente>.key`
- Fallback para `token` quando `arq_licenca` estiver vazio em registros antigos

---

## Query base (Neon)

```sql
SELECT cnpj, idcelular, token, arq_licenca, validade, ativo, nome_cliente,
       sql_servidor, sql_banco, api_authorization, api_database_url
FROM clientes
WHERE cnpj = :cnpj
   OR cnpj LIKE :like1
   OR cnpj LIKE :like2
   OR cnpj LIKE :like3
LIMIT 1;
```

Parâmetros:
- `:cnpj` = CNPJ exato
- `:like1` = `%,<cnpj>`
- `:like2` = `<cnpj>,%`
- `:like3` = `%,<cnpj>,%`

---

## Checklist de ajuste
- [ ] Endpoint `POST /validar-licenca` retorna `arq_licenca` e `download_url`
- [ ] Endpoint `GET /download-licenca` implementado
- [ ] Validação de `ativo` obrigatória
- [ ] Validação de `validade` obrigatória
- [ ] Validação de `device_id` obrigatório
- [ ] Fallback para `token` quando `arq_licenca` for vazio
- [ ] Respostas de erro padronizadas (`404`, `400`)

---

## Testes rápidos
1. Licença válida -> `ok=true` e download funciona
2. `device_id` inválido -> bloqueia
3. Licença desativada (`ativo=false`) -> bloqueia
4. Licença vencida -> bloqueia
5. Registro antigo sem `arq_licenca` -> baixa conteúdo via `token`

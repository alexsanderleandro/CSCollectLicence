# CSCollectManager — Integração com Download Remoto de Licença

## Objetivo
Permitir que o manager baixe/atualize o `.key` pela API, sem depender de distribuição manual de arquivo.

---

## Fluxo recomendado
1. Chamar `POST /validar-licenca` com `cnpj` e `device_id`
2. Se `ok=true`, obter `download_url`
3. Chamar `GET /download-licenca?...`
4. Salvar resposta como `.key` local
5. Carregar e validar normalmente (mesmo fluxo já existente)

---

## Contrato HTTP

### `POST /validar-licenca`
- Request:

```json
{
  "cnpj": "12345678000199",
  "device_id": "ID_DISPOSITIVO"
}
```

- Response esperada:
  - `ok=true` + `download_url`
  - ou `ok=false` + `motivo` + `mensagem`

### `GET /download-licenca?cnpj=...&device_id=...`
- Response: arquivo `.key` em binário
- Salvar com nome local padrão da aplicação

---

## Regras de decisão no Manager
- Se download remoto falhar, manter fallback local (arquivo já existente)
- Se `ok=false` no validar, interromper operação e mostrar mensagem amigável
- Não logar `token`, `api_authorization` e `api_database_url` em texto plano

---

## Checklist de ajuste
- [ ] Implementar cliente HTTP para `POST /validar-licenca`
- [ ] Implementar cliente HTTP para `GET /download-licenca`
- [ ] Persistir `.key` recebido
- [ ] Manter fallback local quando sem internet
- [ ] Melhorar mensagens de erro para usuário final

---

## Cenários de teste
1. Primeiro uso sem `.key` local -> baixa e salva
2. `.key` local antigo -> substitui por versão do servidor
3. Sem internet -> usa `.key` local (se existir)
4. CNPJ não autorizado -> bloqueia
5. `device_id` não autorizado -> bloqueia

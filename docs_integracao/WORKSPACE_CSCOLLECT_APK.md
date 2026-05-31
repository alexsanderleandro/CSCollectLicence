# CSCollect (APK) — Integração de Licença via API

## Objetivo
Baixar licença pela internet e validar acesso por `cnpj` + `device_id`, usando a API como ponte do campo `clientes.arq_licenca`.

---

## Fluxo no APK
1. Montar `device_id` do aparelho
2. Enviar `POST /validar-licenca` com `cnpj` e `device_id`
3. Se `ok=true`, usar `download_url`
4. Baixar `.key` via `GET /download-licenca`
5. Salvar em storage seguro do app
6. Reusar localmente quando offline

---

## Endpoints

### `POST /validar-licenca`
Request:

```json
{
  "cnpj": "12345678000199",
  "device_id": "ANDROID_ID_OU_EQUIVALENTE"
}
```

Response (válido):
- `ok=true`
- `download_url`
- metadados da licença

### `GET /download-licenca?cnpj=...&device_id=...`
- Retorna o conteúdo do `.key`

---

## Boas práticas (mobile)
- Cache local da licença com timestamp de última atualização
- Timeout e retry exponencial no download
- Não exibir segredos em logs
- Se houver licença local válida, permitir operação offline controlada

---

## Checklist de ajuste
- [ ] Criar serviço de validação remota
- [ ] Criar serviço de download de `.key`
- [ ] Persistir licença localmente
- [ ] Implementar fallback offline
- [ ] Tratar mensagens de bloqueio (`expirada`, `desativada`, `device não autorizado`)

---

## Testes mínimos
1. Instalação limpa com internet -> baixa licença
2. Reabertura sem internet -> usa cache local
3. Troca de `device_id` -> API bloqueia
4. Licença expirada -> API bloqueia

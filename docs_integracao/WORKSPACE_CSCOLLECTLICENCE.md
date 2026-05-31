# CSCollectLicence — Publicação da Licença no Banco (arq_licenca)

## Objetivo
Garantir que, ao gerar/salvar a licença, o conteúdo do arquivo `.key` seja persistido também na coluna `clientes.arq_licenca` no Neon.

---

## Pré-requisito de banco
Migration aplicada:

```sql
ALTER TABLE clientes
  ADD COLUMN IF NOT EXISTS arq_licenca text;
```

---

## Regras funcionais
- Continuar salvando `.key` localmente
- Salvar no banco o mesmo conteúdo textual do arquivo
- Em update de licença, atualizar também `arq_licenca`
- Fluxo SQL e REST precisam suportar `arq_licenca`

---

## Checklist de ajuste
- [ ] `salvar_licenca()` retornar conteúdo gerado
- [ ] Upsert SQL incluir `arq_licenca`
- [ ] Upsert REST incluir `arq_licenca`
- [ ] GUI enviar `arq_licenca` no registro
- [ ] Fluxo CLI enviar `arq_licenca` no registro

---

## Validação recomendada
1. Gerar licença nova
2. Confirmar arquivo local criado
3. Confirmar no Neon que `clientes.arq_licenca` foi preenchido
4. Atualizar licença e validar overwrite do campo

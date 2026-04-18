# Resumo das Alterações - Sistema de Configuração JSON

## 📋 O que foi implementado

### 1. Sistema de Configuração Local (`config.py`)
- ✅ Carrega/salva configurações em `cscollect_config.json`
- ✅ Detecta pasta do executável automaticamente (PyInstaller)
- ✅ Suporta SQL Direto e API REST do Neon
- ✅ Prioridade: variáveis de ambiente > arquivo JSON

### 2. Script de Configuração Interativo (`configurar_banco.py`)
- ✅ Menu amigável para configurar banco
- ✅ Mostra configuração atual
- ✅ Permite escolher entre SQL ou REST
- ✅ Salva credenciais em JSON local

### 3. Integração no `licenca.py`
- ✅ Importa e usa `get_database_config()`
- ✅ Fallback automático para env se JSON não existir
- ✅ Mensagens informativas de sucesso/erro
- ✅ Funções REST aceitam `api_key` como parâmetro

### 4. Documentação
- ✅ `GUIA_RAPIDO.md` criado
- ✅ `README.md` atualizado
- ✅ `.env.example` documentado
- ✅ `.gitignore` atualizado

### 5. Testes
- ✅ `test_config_integration.py` - valida sistema completo
- ✅ Teste bem-sucedido de carga de config JSON
- ✅ Geração de token funcionando

---

## 🗂️ Estrutura do JSON de Configuração

**Exemplo (API REST):**
```json
{
  "neon_rest_url": "https://ep-xxx.apirest.sa-east-1.aws.neon.tech/neondb/rest/v1",
  "neon_api_key": "eyJhbGciOi..."
}
```

**Exemplo (SQL Direto):**
```json
{
  "database_url": "postgresql://user:pass@host:5432/db?sslmode=require"
}
```

**Localização:** mesma pasta do executável ou script

---

## 🚀 Como o Vendedor Usa

### Primeira vez (configuração):
```powershell
# 1. Executar configurador
python .\configurar_banco.py

# 2. Escolher "2. API REST do Neon"
# 3. Colar URL: https://ep-dry-hall-acd532yy.apirest.sa-east-1.aws.neon.tech/neondb/rest/v1
# 4. Colar API Key (JWT service_role)
```

### Gerar licença:
```powershell
python .\licenca.py
```

O sistema:
1. Lê `cscollect_config.json` automaticamente
2. Gera token assinado
3. Salva arquivo `.key` (JSON com token)
4. Registra CNPJs no banco Neon via REST

---

## 🔄 Fluxo de Prioridade

```
1. Variável de ambiente DATABASE_URL
   ↓ (se não existir)
2. Variável de ambiente NEON_REST_URL + NEON_API_KEY
   ↓ (se não existir)
3. Arquivo JSON: database_url
   ↓ (se não existir)
4. Arquivo JSON: neon_rest_url + neon_api_key
   ↓ (se não existir)
5. ERRO: "Configuração não encontrada"
```

---

## ✅ Benefícios

- **Sem hardcoding**: credenciais não ficam no código
- **Portável**: JSON viaja com o executável
- **Fácil**: vendedor configura uma vez via menu
- **Seguro**: JSON não vai pro Git (`.gitignore`)
- **Flexível**: suporta env vars para DevOps/CI

---

## 📦 Para Distribuição

1. Compilar executável: `.\build_exe.ps1`
2. Criar `.env` com `MASTER_KEY`
3. Executar `configurar_banco.exe` ou script Python
4. Pronto! `cscollect_config.json` criado

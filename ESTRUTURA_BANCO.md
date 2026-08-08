# Estrutura do Banco de Dados - Clientes

## 📋 Tabela: `clientes`

### Esquema SQL

```sql
CREATE TABLE clientes (
  cnpj VARCHAR(255) PRIMARY KEY,
  idcelular TEXT,
  token TEXT NOT NULL,
  validade VARCHAR(10),
  ativo BOOLEAN DEFAULT true,
  nome_cliente VARCHAR(255),
  qtde_cnpjs INTEGER,
  qtde_devices INTEGER
);
```

### Campos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cnpj` | VARCHAR(255) | **Chave primária**. Contém um ou mais CNPJs separados por vírgula.<br>Exemplo: `"12345678000199,98765432000188"` |
| `idcelular` | TEXT | IDs de celulares autorizados, separados por vírgula.<br>Exemplo: `"a3e9e3a0a4659652,device-123"` |
| `token` | TEXT | Token assinado (HMAC-SHA256) contendo todos os dados da licença em formato base64url |
| `validade` | VARCHAR(10) | Data de validade no formato YYYY-MM-DD.<br>Exemplo: `"2026-12-31"` ou `NULL` para sem validade |
| `ativo` | BOOLEAN | Flag para indicar se o registro está ativo (padrão: `true`) |
| `nome_cliente` | VARCHAR(255) | Nomes das empresas separados por vírgula, **pareados por posição com a coluna `cnpj`** (máx 30 caracteres cada).<br>Exemplo: `"Empresa ABC Ltda,Empresa ABC Filial"` |
| `qtde_cnpjs` | INTEGER | Quantidade de CNPJs contratados/liberados (adicionado v9). Uso interno/visual — não faz parte do token assinado. |
| `qtde_devices` | INTEGER | Quantidade de devices contratados/liberados (adicionado v9). Uso interno/visual — não faz parte do token assinado. |
| `tipo_licenca` | VARCHAR(10) | Tipo/plano da licença: `'Lite'` ou `'Pro'` (adicionado v10, default `'Lite'`). Diferente dos campos acima, **faz parte do payload assinado** do token (`gerar_licenca`) — a coluna é só um espelho para consulta no painel. |

---

## 🔄 Comportamento do Sistema

### Ao Salvar Licença na GUI

1. **Gera token assinado** contendo:
   - Lista de CNPJs
   - Lista de nomes das empresas (pareada por posição com a de CNPJs)
   - Lista de IDs de celular
   - Validade
   - Nome do cliente (string completa, separada por vírgula)
   - Servidor SQL
   - Banco de dados
   - Data/hora de geração

2. **Salva arquivo `.key`** (JSON) com:
   ```json
   {
     "cnpjs": ["12345678000199", "98765432000188"],
     "nomes": ["Empresa ABC Ltda", "Empresa ABC Filial"],
     "ids": ["device-1", "device-2"],
     "token": "eyJjbnBqc...",
     "validade": "2026-12-31",
     "nome_cliente": "Empresa ABC Ltda,Empresa ABC Filial",
     "database_url": "postgresql://user:pass@host:5432/db"
   }
   ```

   `nomes[i]` corresponde a `cnpjs[i]`. Licenças geradas antes do suporte
   multi-empresa não têm a chave `nomes` — nesse caso o nome único de
   `nome_cliente` é replicado para todos os CNPJs (ver `resolver_nomes` em
   `licenca.py`).

3. **Registra no banco Neon** (se configurado):
   - CNPJs → concatenados com vírgula
   - Nomes das empresas → concatenados com vírgula, na mesma ordem dos CNPJs
   - IDs celular → concatenados com vírgula
   - Insere **1 registro único**
   - Usa `ON CONFLICT (cnpj) DO UPDATE` para atualizar se já existir
   - Se a string de CNPJs foi modificada (adição/remoção), **deleta o registro antigo** antes de inserir o novo

---

## 📊 Exemplo de Registro

**Licença com:**
- CNPJs: `65391113000120`, `21581137000157`
- Nomes: `Empresa XYZ`, `Empresa XYZ Filial`
- IDs: `a3e9e3a0a4659652`
- Validade: `2026-05-01`

**Registro no banco:**

| cnpj | idcelular | token | validade | ativo | nome_cliente |
|------|-----------|-------|----------|-------|-------------|
| 65391113000120,21581137000157 | a3e9e3a0a4659652 | eyJjbnBqcyI6WyI2NTM5M... | 2026-05-01 | true | Empresa XYZ,Empresa XYZ Filial |

---

## ⚙️ Configuração

### Via GUI

1. Clique no botão **"⚙ Config. Banco"**
2. Escolha:
   - **SQL Direto**: Cole a `DATABASE_URL`
   - **API REST**: Cole URL REST + API Key

### Manualmente (JSON)

Arquivo: `cscollect_config.json`

```json
{
  "neon_rest_url": "https://ep-dry-hall-acd532yy.apirest.sa-east-1.aws.neon.tech/neondb/rest/v1",
  "neon_api_key": "eyJhbGciOi..."
}
```

---

## 🔍 Consultas Úteis

### Listar todos os clientes ativos
```sql
SELECT * FROM clientes WHERE ativo = true;
```

### Buscar por CNPJ específico
```sql
SELECT * FROM clientes WHERE cnpj LIKE '%12345678000199%';
```

### Desativar um registro
```sql
UPDATE clientes SET ativo = false WHERE cnpj = '12345678000199,98765432000188';
```

### Limpar todos os registros (cuidado!)
```sql
TRUNCATE TABLE clientes;
```

---

## 🚀 Fluxo Completo

```
┌─────────────────────┐
│   GUI - Preencher   │
│   dados da licença  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Botão "Salvar"    │
└──────────┬──────────┘
           │
           ├─► Gera token assinado
           │
           ├─► Salva arquivo .key (JSON)
           │
           └─► Registra no Neon:
               • cnpj = "CNPJ1,CNPJ2,..."
               • idcelular = "ID1,ID2,..."
               • token = "eyJ..."
               • validade = "2026-12-31"
               • ativo = true
```

---

## ✅ Vantagens desta Abordagem

- **1 registro por licença** (ao invés de N registros para N CNPJs)
- **Consultas simples** pela chave primária
- **Compatível com PostgREST/Neon API**
- **Fácil auditoria**: ver todos CNPJs/IDs de uma licença em 1 linha
- **Atualização atômica**: UPDATE único ao renovar licença

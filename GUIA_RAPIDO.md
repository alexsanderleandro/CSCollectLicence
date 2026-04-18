# Guia Rápido - CSCollectLicence

## 🚀 Configuração Inicial (Uma vez)

### 1. Instalar dependências

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configurar MASTER_KEY

Crie arquivo `.env`:
```
MASTER_KEY=sua_chave_secreta_aqui
```

### 3. Configurar Banco de Dados Neon

Execute o configurador:
```powershell
python .\configurar_banco.py
```

**Para API REST do Neon** (recomendado):
- Escolha opção `2`
- Cole a URL: `https://ep-dry-hall-acd532yy.apirest.sa-east-1.aws.neon.tech/neondb/rest/v1`
- Cole o API Key (JWT service_role)

Isso cria `cscollect_config.json` com suas credenciais.

---

## 📝 Gerar Nova Licença

```powershell
python .\licenca.py
```

Escolha `n` (nova licença) e informe:
- CNPJs autorizados
- IDs dos celulares
- Validade (ex: `2026-12-31`)
- Nome do cliente
- Servidor SQL
- Banco de dados

O sistema irá:
✅ Gerar o token assinado  
✅ Salvar arquivo `.key` em formato JSON (com `cnpjs`, `ids`, `token`, `validade`)  
✅ Registrar CNPJs + token no banco Neon automaticamente

---

## 🔄 Editar Licença Existente

```powershell
python .\licenca.py
```

Escolha `s` (ler existente) e informe o caminho do arquivo `.key`.

Você pode:
- Adicionar/remover CNPJs
- Adicionar/remover IDs de celular
- Alterar validade

Ao salvar, o sistema:
✅ Atualiza tokens dos CNPJs no banco  
✅ Remove CNPJs que foram deletados da licença

---

## 📦 Gerar Executável

```powershell
.\build_exe.ps1
```

O executável estará em `dist\CSCollectLicence.exe`.

**Importante**: 
- Coloque `.env` ao lado do executável (com `MASTER_KEY`)
- Execute `configurar_banco.py` na pasta do executável para criar `cscollect_config.json`

---

## 🗄️ Estrutura do Banco (Neon)

Tabela `clientes`:
```sql
CREATE TABLE clientes (
  cnpj VARCHAR(255) PRIMARY KEY,
  idcelular TEXT,
  token TEXT NOT NULL,
  validade VARCHAR(10),
  ativo BOOLEAN DEFAULT true
);
```

**Observação importante:**
- Campo `cnpj` contém **todos os CNPJs separados por vírgula** (chave única por licença)
- Campo `idcelular` contém **todos os IDs separados por vírgula**
- Campo `validade` contém a data no formato YYYY-MM-DD (ou NULL para sem validade)
- Exemplo: `cnpj = "12345678000199,98765432000188"`

Para mais detalhes, veja [ESTRUTURA_BANCO.md](ESTRUTURA_BANCO.md)

---

## 🔐 Formato da Key

```json
{
  "cnpjs": ["12345678000199"],
  "ids": ["device-1", "device-2"],
  "token": "eyJjbnBqc...",
  "validade": "2026-12-31"
}
```

O `token` contém **todos** os dados assinados com HMAC-SHA256.

---

## ⚙️ Opções de Configuração

### Arquivo JSON (Recomendado)
`cscollect_config.json`:
```json
{
  "neon_rest_url": "https://...",
  "neon_api_key": "eyJhbGc..."
}
```

### Variáveis de Ambiente (Alternativa)
```powershell
$env:DATABASE_URL="postgresql://user:pass@host/db"
```

**Prioridade**: env > JSON

---

## 🛠️ Troubleshooting

### Erro: "Configuração de banco não encontrada"
Execute: `python .\configurar_banco.py`

### Erro: "NEON_API_KEY não definido"
Certifique-se de que salvou a API Key no configurador

### Erro: "MASTER_KEY não definida"
Crie arquivo `.env` com `MASTER_KEY=...`

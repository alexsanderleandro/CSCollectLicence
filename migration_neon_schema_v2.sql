-- Migração v2: adicionar idcelular e cnpj; criar índice único composto (id, cnpj, idcelular)
BEGIN;

-- ADICIONAR idcelular em CLIENTES
ALTER TABLE clientes
  ADD COLUMN IF NOT EXISTS idcelular text;

-- ADICIONAR idcelular e cnpj em CARGAS
ALTER TABLE cargas
  ADD COLUMN IF NOT EXISTS idcelular text,
  ADD COLUMN IF NOT EXISTS cnpj text;

-- ADICIONAR idcelular e cnpj em CONTAGENS
ALTER TABLE contagens
  ADD COLUMN IF NOT EXISTS idcelular text,
  ADD COLUMN IF NOT EXISTS cnpj text;

-- Normalizar nomes: garantir coluna nome_cliente em cargas (caso ainda exista cliente)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cargas' AND column_name='cliente') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cargas' AND column_name='nome_cliente') THEN
      EXECUTE 'ALTER TABLE cargas RENAME COLUMN cliente TO nome_cliente';
    END IF;
  END IF;
END$$;

-- Criar índices únicos compostos para cada tabela (preparação para PK composto)
-- Usamos UNIQUE INDEX em vez de alterar PK diretamente para evitar impactos imediatos.
CREATE UNIQUE INDEX IF NOT EXISTS ux_clientes_id_cnpj_idcel ON clientes ((id::text), cnpj, idcelular);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cargas_id_cnpj_idcel ON cargas ((id::text), cnpj, idcelular);
CREATE UNIQUE INDEX IF NOT EXISTS ux_contagens_id_cnpj_idcel ON contagens ((id::text), cnpj, idcelular);

COMMIT;

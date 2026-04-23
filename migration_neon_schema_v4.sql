-- Migração v4: adicionar coluna ativo (boolean) em clientes
BEGIN;

ALTER TABLE clientes
  ADD COLUMN IF NOT EXISTS ativo boolean DEFAULT true;

-- garante valores não nulos para linhas antigas
UPDATE clientes SET ativo = true WHERE ativo IS NULL;

COMMIT;

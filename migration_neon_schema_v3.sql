-- Migração v3: adicionar coluna validade (date) em clientes
BEGIN;

ALTER TABLE clientes
  ADD COLUMN IF NOT EXISTS validade date;

COMMIT;

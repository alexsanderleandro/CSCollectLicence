-- Migração v5: adicionar colunas sql_servidor e sql_banco em clientes
BEGIN;

ALTER TABLE clientes
  ADD COLUMN IF NOT EXISTS sql_servidor varchar(30),
  ADD COLUMN IF NOT EXISTS sql_banco    varchar(30);

COMMIT;

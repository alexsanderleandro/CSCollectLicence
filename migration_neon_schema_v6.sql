-- Migração v6: adicionar colunas api_authorization e api_database_url (criptografadas em repouso) em clientes
BEGIN;

ALTER TABLE clientes
  ADD COLUMN IF NOT EXISTS api_authorization text,
  ADD COLUMN IF NOT EXISTS api_database_url  text;

COMMENT ON COLUMN clientes.api_authorization IS 'Token de autorização Bearer da API do cliente, criptografado em repouso (AES-256-GCM, base64)';
COMMENT ON COLUMN clientes.api_database_url  IS 'Connection string do banco de dados do cliente, criptografada em repouso (AES-256-GCM, base64)';

COMMIT;

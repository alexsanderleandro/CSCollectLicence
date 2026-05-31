-- Migração v7: adicionar coluna arq_licenca para armazenar o conteúdo do arquivo de licença
BEGIN;

ALTER TABLE clientes
  ADD COLUMN IF NOT EXISTS arq_licenca text;

COMMENT ON COLUMN clientes.arq_licenca IS 'Conteúdo textual do arquivo .key gerado para a licença, usado pela API para download remoto';

COMMIT;
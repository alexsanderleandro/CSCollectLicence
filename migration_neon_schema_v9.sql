-- Migração v9: adiciona controle interno de quantidade de CNPJs e devices
-- liberados por licença (uso visual/administrativo apenas — não faz parte
-- do token assinado usado para validação no APK/app desktop).
BEGIN;

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS qtde_cnpjs INTEGER,
    ADD COLUMN IF NOT EXISTS qtde_devices INTEGER;

-- Backfill dos registros existentes a partir da contagem de itens já
-- gravados nas colunas cnpj/idcelular (separadas por vírgula).
UPDATE clientes
SET qtde_cnpjs = array_length(string_to_array(cnpj, ','), 1)
WHERE qtde_cnpjs IS NULL AND cnpj IS NOT NULL AND cnpj <> '';

UPDATE clientes
SET qtde_devices = array_length(string_to_array(idcelular, ','), 1)
WHERE qtde_devices IS NULL AND idcelular IS NOT NULL AND idcelular <> '';

COMMENT ON COLUMN clientes.qtde_cnpjs IS 'Quantidade de CNPJs contratados/licenciados (uso interno/visual, não faz parte do token assinado)';
COMMENT ON COLUMN clientes.qtde_devices IS 'Quantidade de devices (idcelular) contratados/licenciados (uso interno/visual, não faz parte do token assinado)';

COMMIT;

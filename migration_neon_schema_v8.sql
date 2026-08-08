-- Migração v8: nome_cliente passa a guardar um nome por CNPJ, separados por vírgula
-- (mesmo formato já usado pelas colunas cnpj e idcelular). varchar(30) cabia só um nome.
BEGIN;

ALTER TABLE clientes
  ALTER COLUMN nome_cliente TYPE varchar(255);

COMMENT ON COLUMN clientes.nome_cliente IS 'Nomes das empresas separados por vírgula, pareados por posição com a coluna cnpj (ex.: "GUIDAUTO,GUIDAUTO FILIAL"). Cada nome tem no máximo 30 caracteres';

COMMIT;

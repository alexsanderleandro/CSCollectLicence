-- Migração: adiciona colunas reginclusao e dataalteracao e cria trigger
BEGIN;

ALTER TABLE clientes
  ADD COLUMN IF NOT EXISTS reginclusao timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS dataalteracao timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS arq_licenca text;

-- cria/atualiza a função que atualiza dataalteracao
CREATE OR REPLACE FUNCTION trg_dataalteracao()
RETURNS trigger AS $$
BEGIN
  NEW.dataalteracao = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- garante que o trigger exista (substitui se houver)
DROP TRIGGER IF EXISTS set_dataalteracao ON clientes;
CREATE TRIGGER set_dataalteracao
  BEFORE UPDATE ON clientes
  FOR EACH ROW
  EXECUTE FUNCTION trg_dataalteracao();

COMMIT;

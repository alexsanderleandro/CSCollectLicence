-- Migração: ajustar esquema conforme solicitado
BEGIN;

-- CLIENTES: adicionar colunas se não existirem
ALTER TABLE clientes
  ADD COLUMN IF NOT EXISTS token text,
  ADD COLUMN IF NOT EXISTS reginclusao timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS dataalteracao timestamptz DEFAULT now(),
  ADD COLUMN IF NOT EXISTS cnpj text;

-- renomear coluna nome -> nome_cliente se necessário
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='clientes' AND column_name='nome') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='clientes' AND column_name='nome_cliente') THEN
      EXECUTE 'ALTER TABLE clientes RENAME COLUMN nome TO nome_cliente';
    END IF;
  END IF;
END$$;

-- garante função/trigger para atualizar dataalteracao
CREATE OR REPLACE FUNCTION trg_dataalteracao()
RETURNS trigger AS $$
BEGIN
  NEW.dataalteracao = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_dataalteracao ON clientes;
CREATE TRIGGER set_dataalteracao
  BEFORE UPDATE ON clientes
  FOR EACH ROW
  EXECUTE FUNCTION trg_dataalteracao();

-- CARGAS: adicionar colunas e renomear cliente -> nome_cliente
ALTER TABLE cargas
  ADD COLUMN IF NOT EXISTS cliente_id integer,
  ADD COLUMN IF NOT EXISTS nome_arquivo text,
  ADD COLUMN IF NOT EXISTS data_envio timestamptz;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cargas' AND column_name='cliente') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cargas' AND column_name='nome_cliente') THEN
      EXECUTE 'ALTER TABLE cargas RENAME COLUMN cliente TO nome_cliente';
    END IF;
  END IF;
END$$;

-- CONTAGENS: nova tabela
CREATE TABLE IF NOT EXISTS contagens (
  id serial PRIMARY KEY,
  cliente_id integer,
  nome_arquivo text,
  data_envio timestamptz DEFAULT now(),
  nome_cliente text
);

COMMIT;

-- Migração v10: adiciona tipo de licença (Lite/Pro) em clientes e activation_tokens.
-- Diferente de qtde_cnpjs/qtde_devices (metadado interno), tipo_licenca também
-- passa a fazer parte do payload assinado do token (gerar_licenca), então esta
-- coluna é apenas um espelho para consulta/filtro no painel administrativo.
--
-- DEFAULT 'Lite' aplica-se também às linhas já existentes (comportamento padrão
-- do Postgres para ADD COLUMN ... DEFAULT), atendendo ao requisito de que
-- licenças/tokens antigos sejam tratados como Lite.
BEGIN;

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS tipo_licenca VARCHAR(10) NOT NULL DEFAULT 'Lite';
ALTER TABLE clientes
    ADD CONSTRAINT chk_clientes_tipo_licenca CHECK (tipo_licenca IN ('Lite', 'Pro'));

ALTER TABLE activation_tokens
    ADD COLUMN IF NOT EXISTS tipo_licenca VARCHAR(10) NOT NULL DEFAULT 'Lite';
ALTER TABLE activation_tokens
    ADD CONSTRAINT chk_activation_tokens_tipo_licenca CHECK (tipo_licenca IN ('Lite', 'Pro'));

COMMENT ON COLUMN clientes.tipo_licenca IS 'Tipo/plano da licença: Lite ou Pro. Faz parte do payload assinado do token (gerar_licenca), não apenas metadado.';
COMMENT ON COLUMN activation_tokens.tipo_licenca IS 'Tipo/plano da licença associada ao token de ativação: Lite ou Pro.';

COMMIT;

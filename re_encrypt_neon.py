"""
re_encrypt_neon.py — Migração R6: re-criptografar campos AES no banco Neon.

CONTEXTO:
  A derivação da chave AES foi alterada de SHA-256 direto → PBKDF2-HMAC-SHA256
  (100 000 iterações, salt 'cscollect_aes_salt_v2').
  Os campos `api_authorization` e `api_database_url` na tabela `clientes`
  foram criptografados com a chave antiga (SHA-256). Este script lê cada
  registro, descriptografa com a chave ANTIGA e re-criptografa com a NOVA.

PRÉ-REQUISITOS:
  pip install cryptography sqlalchemy psycopg2-binary python-dotenv

USO:
  1. Certifique-se de que MASTER_KEY está definida (variável de ambiente ou .env).
  2. Execute: python re_encrypt_neon.py
  3. Execute apenas UMA vez após o deploy do R6.
"""

import os
import base64
import hashlib
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    print("ERRO: instale 'cryptography': pip install cryptography>=41.0.0")
    sys.exit(1)

try:
    import sqlalchemy as sa
except ImportError:
    print("ERRO: instale 'sqlalchemy': pip install sqlalchemy psycopg2-binary")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

MASTER_KEY = os.environ.get("MASTER_KEY", "").strip().strip("'\"")
if not MASTER_KEY:
    print("ERRO: MASTER_KEY não definida. Defina via variável de ambiente ou .env")
    sys.exit(1)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    print("ERRO: DATABASE_URL não definida. Defina via variável de ambiente ou .env")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Derivação de chave — versão ANTIGA (SHA-256 direto)
# ---------------------------------------------------------------------------

def _chave_antiga() -> bytes:
    return hashlib.sha256(MASTER_KEY.encode("utf-8")).digest()

# ---------------------------------------------------------------------------
# Derivação de chave — versão NOVA (PBKDF2-HMAC-SHA256, R6)
# ---------------------------------------------------------------------------

def _chave_nova() -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        MASTER_KEY.encode("utf-8"),
        b"cscollect_aes_salt_v2",
        100_000,
        dklen=32,
    )

# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------

def _decrypt(ciphertext_b64: str, key: bytes) -> str:
    """Descriptografa campo AES-256-GCM com a chave fornecida."""
    if not ciphertext_b64:
        return ""
    raw = base64.b64decode(ciphertext_b64.encode("ascii"))
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")


def _encrypt(plaintext: str, key: bytes) -> str:
    """Criptografa campo AES-256-GCM com a chave fornecida."""
    if not plaintext:
        return ""
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")

# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrar():
    engine = sa.create_engine(DATABASE_URL, pool_pre_ping=True)
    chave_v1 = _chave_antiga()
    chave_v2 = _chave_nova()

    print(f"Conectando ao banco...")
    with engine.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT id, cnpj, api_authorization, api_database_url FROM clientes"
        )).fetchall()

    print(f"{len(rows)} registro(s) encontrado(s) na tabela clientes.")

    atualizados = 0
    erros = 0

    with engine.connect() as conn:
        for row in rows:
            row_id   = row[0]
            cnpj     = row[1]
            enc_auth = row[2] or ""
            enc_db   = row[3] or ""

            # Pular registros sem campos criptografados
            if not enc_auth and not enc_db:
                print(f"  [{cnpj}] sem campos criptografados — pulando.")
                continue

            # Tentar descriptografar com chave antiga
            try:
                plain_auth = _decrypt(enc_auth, chave_v1) if enc_auth else ""
                plain_db   = _decrypt(enc_db,   chave_v1) if enc_db   else ""
            except Exception as e:
                # Talvez já esteja com chave nova (re-execução) — tentar com nova
                try:
                    plain_auth = _decrypt(enc_auth, chave_v2) if enc_auth else ""
                    plain_db   = _decrypt(enc_db,   chave_v2) if enc_db   else ""
                    print(f"  [{cnpj}] já usa chave nova — pulando re-criptografia.")
                    continue
                except Exception as e2:
                    print(f"  [{cnpj}] ERRO ao descriptografar: {e} / {e2}")
                    erros += 1
                    continue

            # Re-criptografar com chave nova
            try:
                novo_auth = _encrypt(plain_auth, chave_v2) if plain_auth else ""
                novo_db   = _encrypt(plain_db,   chave_v2) if plain_db   else ""
            except Exception as e:
                print(f"  [{cnpj}] ERRO ao re-criptografar: {e}")
                erros += 1
                continue

            # Atualizar no banco
            with engine.connect() as conn:
                conn.execute(sa.text("""
                    UPDATE clientes
                    SET api_authorization = :auth, api_database_url = :dburl
                    WHERE id = :id
                """), {"auth": novo_auth, "dburl": novo_db, "id": row_id})
                conn.commit()

            print(f"  [{cnpj}] ✓ re-criptografado com chave PBKDF2.")
            atualizados += 1

    print(f"\nConcluído: {atualizados} atualizado(s), {erros} erro(s).")
    if erros:
        print("Verifique os registros com erro manualmente.")


if __name__ == "__main__":
    confirmar = input(
        "Este script vai re-criptografar api_authorization e api_database_url na tabela clientes.\n"
        "Execute apenas UMA vez após o deploy do R6.\n"
        "Continuar? (s/n): "
    ).strip().lower()
    if confirmar != "s":
        print("Cancelado.")
        sys.exit(0)
    migrar()

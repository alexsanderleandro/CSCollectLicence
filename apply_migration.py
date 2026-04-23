"""Script opcional para aplicar migration.sql usando DATABASE_URL.

Uso:
  - Defina a variável de ambiente `DATABASE_URL` ou passe a dsn como argumento:
    python apply_migration.py "postgresql://user:pass@host/db?sslmode=require"

O script tenta usar `psycopg` (v3) ou `psycopg2`. Se falhar, imprime instrução para usar `psql`.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
# permite passar um arquivo SQL alternativo como segundo argumento
default_sql = 'migration.sql'
SQL_FILE = ROOT / (sys.argv[2] if len(sys.argv) > 2 else os.environ.get('MIGRATION_FILE', default_sql))

if not SQL_FILE.exists():
    print('migration.sql não encontrado ao lado do script.')
    sys.exit(1)

dsn = os.environ.get('DATABASE_URL') or (sys.argv[1] if len(sys.argv) > 1 else None)
if not dsn:
    print('Forneça DATABASE_URL via variável de ambiente ou como argumento.')
    print('Exemplo:')
    print('  $env:DATABASE_URL="postgresql://user:pass@host/db?sslmode=require"')
    print('  python apply_migration.py')
    sys.exit(1)

sql = SQL_FILE.read_text(encoding='utf-8')

# Tenta psycopg (v3)
try:
    import psycopg
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print('Migração aplicada com sucesso (psycopg).')
        sys.exit(0)
    except Exception as e:
        print('Falha ao aplicar migração com psycopg:', e)
except Exception:
    pass

# Tenta psycopg2
try:
    import psycopg2
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        print('Migração aplicada com sucesso (psycopg2).')
        sys.exit(0)
    except Exception as e:
        print('Falha ao aplicar migração com psycopg2:', e)
except Exception:
    pass

print('\nNão foi possível aplicar via driver Python. Use `psql` para aplicar manualmente:')
print(f'psql "{dsn}" -f {SQL_FILE.name}')
print('\nObservação: defina a variável de ambiente NEON/DB com sua string de conexão, ou passe a dsn como argumento.')
sys.exit(2)

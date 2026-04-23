import os, sys
import psycopg

d = os.environ.get('DATABASE_URL')
if not d:
    print('NO_DSN')
    sys.exit(2)
print('DSN OK')
try:
    conn = psycopg.connect(d)
    conn.close()
    print('CONNECTED')
except Exception as e:
    print('ERROR', repr(e))
    sys.exit(1)

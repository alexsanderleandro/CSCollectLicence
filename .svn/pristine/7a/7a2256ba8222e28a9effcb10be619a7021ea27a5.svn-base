import re
from datetime import datetime
from pathlib import Path

VERSION_FILE = Path(__file__).with_name('version.py')


def read_current_version():
    if not VERSION_FILE.exists():
        return None
    text = VERSION_FILE.read_text(encoding='utf-8')
    m = re.search(r"VERSION\s*=\s*['\"]([^'\"]+)['\"]", text)
    if m:
        return m.group(1).strip()
    return None


def format_version(date_str: str, rev: int) -> str:
    return f"{date_str} rev. {rev}"


def bump_version():
    today = datetime.now().strftime('%y.%m.%d')
    cur = read_current_version()
    if cur:
        # procura pattern YY.MM.DD rev. N
        m = re.match(r"^(\d{2}\.\d{2}\.\d{2})\s+rev\.\s*(\d+)$", cur)
        if m and m.group(1) == today:
            rev = int(m.group(2)) + 1
        else:
            rev = 1
    else:
        rev = 1

    new_ver = format_version(today, rev)
    content = f"\"\"\"Arquivo gerado por update_version.py\n+Conte\u00fado: VERSION = '{new_ver}'\n+\"\"\"\n\nVERSION = '{new_ver}'\n"
    VERSION_FILE.write_text(content, encoding='utf-8')
    return new_ver


if __name__ == '__main__':
    v = bump_version()
    print('Versão atualizada para:', v)

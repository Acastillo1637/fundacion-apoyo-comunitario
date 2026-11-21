"""Check repository-local Markdown links without network access or secret files."""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    failures = []
    documents = [ROOT / 'README.md', *sorted((ROOT / 'docs').rglob('*.md'))]
    for document in documents:
        text = document.read_text(encoding='utf-8')
        for match in re.finditer(r'!?\[[^\]]*\]\(([^\n)]+)\)', text):
            target = match.group(1).strip()
            if target.startswith('<'):
                target = target[1:target.index('>')]
            else:
                target = target.split(' "', 1)[0]
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = (document.parent / unquote(parsed.path)).resolve()
            if not path.is_relative_to(ROOT) or not path.exists():
                failures.append(f'{document.relative_to(ROOT)}: {target}')
    if failures:
        print('\n'.join(failures))
        return 1
    print(f'Documentación comprobada: {len(documents)} Markdown, sin enlaces locales rotos.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

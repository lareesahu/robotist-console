"""Run the catalogue tests under an interpreter that can import them.

Two interpreters live on this machine and only one carries BeautifulSoup, so
`python -m unittest discover` fails with eight import errors that look like test
failures. This entry point picks the interpreter that works, so cron, a git hook
or another agent gets the same answer whichever python it happened to call.

    python catalog/run_tests.py [unittest arguments...]
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ['-m', 'unittest', 'discover', '-s', 'catalog', '-t', '.']
CANDIDATES = [
    'C:/Users/hunin/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe',
    'python3',
    'python',
]


def main(arguments=None):
    arguments = arguments if arguments is not None else sys.argv[1:]
    try:
        import bs4  # noqa: F401
        return subprocess.run([sys.executable] + PACKAGE + arguments, cwd=str(ROOT)).returncode
    except ImportError:
        pass
    tried = []
    for candidate in CANDIDATES:
        if os.path.abspath(candidate) == os.path.abspath(sys.executable):
            continue
        try:
            probe = subprocess.run([candidate, '-c', 'import bs4'], capture_output=True, timeout=120)
        except Exception as error:
            tried.append('%s (%s)' % (candidate, error.__class__.__name__))
            continue
        if probe.returncode == 0:
            return subprocess.run([candidate] + PACKAGE + arguments, cwd=str(ROOT)).returncode
        tried.append(candidate)
    print('The catalogue tests need BeautifulSoup. Tried: %s' % (', '.join(tried) or 'no other interpreter found'))
    return 2


if __name__ == '__main__':
    sys.exit(main())

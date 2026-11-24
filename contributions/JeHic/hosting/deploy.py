#!/usr/bin/env python3
"""Prepare and run the Family Budget Tracker on a local PC."""
import argparse
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUNTIME = HERE / '.runtime'
SITE = RUNTIME / 'website'
ENV = RUNTIME / 'venv'
ARCHIVE = REPO / 'Family_Budget_Tracker_Website (1) 2.zip'
SOURCE = 'Family_Budget_Tracker_Website (1)'
PYTHON = ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def extract_site(archive):
    if SITE.exists():
        if not (SITE / 'app.py').is_file() or not (SITE / 'requirements.txt').is_file():
            raise RuntimeError(f'Incomplete website at {SITE}; inspect it before retrying.')
        print('Existing website and database kept unchanged.', flush=True)
        return
    if not archive.is_file():
        raise RuntimeError(f'Website archive not found: {archive}')
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=RUNTIME) as temp:
        target = Path(temp) / 'website'
        target.mkdir()
        with zipfile.ZipFile(archive) as zf:
            for item in zf.infolist():
                parts = PurePosixPath(item.filename).parts
                if len(parts) < 2 or parts[0] != SOURCE:
                    continue
                relative = parts[1:]
                if any(p in ('.', '..') or '\\' in p or ':' in p for p in relative):
                    raise RuntimeError(f'Unsafe archive entry: {item.filename}')
                dest = target.joinpath(*relative)
                if item.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(item) as src, dest.open('wb') as out:
                        shutil.copyfileobj(src, out)
        for name in ('app.py', 'requirements.txt'):
            if not (target / name).is_file():
                raise RuntimeError(f'Archive is missing {SOURCE}/{name}')
        target.rename(SITE)
    print(f'Website extracted to {SITE}', flush=True)


def setup(archive):
    extract_site(archive)
    if not PYTHON.is_file():
        print('Creating Python virtual environment...', flush=True)
        venv.EnvBuilder(with_pip=True).create(ENV)
    subprocess.run([str(PYTHON), '-m', 'pip', 'install', '-r', str(SITE / 'requirements.txt'),
                    'waitress>=3.0.2,<4'], cwd=SITE, check=True)
    (SITE / 'static' / 'uploads').mkdir(parents=True, exist_ok=True)
    print('Setup complete. Run deploy.py check, then deploy.py start.', flush=True)


def require_setup():
    if not PYTHON.is_file() or not (SITE / 'app.py').is_file():
        raise RuntimeError('Run deploy.py setup first.')


def check():
    require_setup()
    code = ('from app import app; from waitress import serve; '
            'print("Application imported successfully."); print(app.url_map)')
    subprocess.run([str(PYTHON), '-c', code], cwd=SITE, check=True)


def start(lan, port):
    require_setup()
    host = '0.0.0.0' if lan else '127.0.0.1'
    print(f'Local browser: http://127.0.0.1:{port}', flush=True)
    if lan:
        print(f'LAN browser: http://<host-PC-local-IP>:{port}', flush=True)
        print('Use a trusted private network and test data only. HTTP is not encrypted.', flush=True)
    print('Press Ctrl+C to stop the server.', flush=True)
    code = ('import logging, sys; from app import app; from waitress import serve; '
            'logging.basicConfig(level=logging.INFO); app.debug = False; '
            'serve(app, host=sys.argv[1], port=int(sys.argv[2]), threads=4)')
    env = dict(os.environ, PYTHONUNBUFFERED='1', FLASK_DEBUG='0')
    return subprocess.call([str(PYTHON), '-c', code, host, str(port)], cwd=SITE, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('setup', help='Extract site and install dependencies')
    prepare.add_argument('--archive', type=Path, default=ARCHIVE)
    commands.add_parser('check', help='Check application imports and routes')
    run = commands.add_parser('start', help='Run the Waitress WSGI server')
    run.add_argument('--lan', action='store_true', help='Allow connections from other devices')
    run.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    try:
        if args.command == 'setup':
            setup(args.archive.resolve())
        elif args.command == 'check':
            check()
        else:
            if not 1 <= args.port <= 65535:
                parser.error('port must be between 1 and 65535')
            return start(args.lan, args.port)
    except KeyboardInterrupt:
        print('\nServer stopped.')
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(f'Deployment failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

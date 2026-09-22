import argparse
import getpass
import os
from pathlib import Path

from .core import Agency, Problem
from .server import serve


def main():
    parser = argparse.ArgumentParser(description='AgencyOS control plane')
    parser.add_argument('command', choices=['setup', 'serve'])
    parser.add_argument('--db', default=os.getenv('AGENCYOS_DB', 'data/agencyos.sqlite3'))
    parser.add_argument('--host', default=os.getenv('AGENCYOS_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.getenv('AGENCYOS_PORT', '8000')))
    parser.add_argument('--username', default='owner')
    args = parser.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.command == 'serve':
            serve(args.db, args.host, args.port, os.getenv('AGENCYOS_SECURE_COOKIE') == '1')
        else:
            password = getpass.getpass('Senha do proprietário (mínimo 12 caracteres): ')
            agency = Agency(args.db)
            try:
                agency.bootstrap(args.username, password)
                print('Proprietário configurado.')
            finally:
                agency.close()
    except Problem as error:
        parser.exit(1, f'Erro: {error}\n')


if __name__ == '__main__':
    main()

"""Prepare and send reviewed campaign emails and assets to the configured recipient."""
import argparse
import json
from pathlib import Path

from email_delivery import ROOT, OutlookClient, prepare_delivery, prepare_generation, send_delivery, status_rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check', help='Verifica il mittente Outlook, senza inviare')
    prepare = commands.add_parser('prepare', help='Prepara una campagna archiviata e revisionata')
    prepare.add_argument('--campaign', type=Path, required=True)
    prepare.add_argument('--review', type=Path, required=True)
    prepare.add_argument('--output', type=Path, required=True)
    deliver = commands.add_parser('deliver', help='Dopo la revisione, prepara e invia una generazione del database')
    deliver.add_argument('--database', type=Path, default=ROOT/'data/catalog.sqlite')
    deliver.add_argument('--generation', required=True)
    deliver.add_argument('--output', type=Path, required=True)
    deliver.add_argument('--state', type=Path, default=ROOT/'data/email-delivery.sqlite')
    send = commands.add_parser('send', help='Invia una consegna già preparata, senza nuova domanda SÌ/NO')
    send.add_argument('--manifest', type=Path, required=True)
    send.add_argument('--state', type=Path, default=ROOT/'data/email-delivery.sqlite')
    status = commands.add_parser('status', help='Legge il registro locale senza inviare')
    status.add_argument('--state', type=Path, default=ROOT/'data/email-delivery.sqlite')
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            result = {'status': 'prepared_not_sent', 'manifest': str(prepare_delivery(
                args.campaign, json.loads(args.review.read_text()), args.output))}
        elif args.command == 'deliver':
            path = prepare_generation(args.database, args.generation, args.output)
            result = send_delivery(path, args.state)
        elif args.command == 'send':
            result = send_delivery(args.manifest, args.state)
        elif args.command == 'check':
            result = OutlookClient.from_environment().profile()
        else:
            result = status_rows(args.state)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        parser.exit(1, f'Email: {error}\n')


if __name__ == '__main__':
    main()

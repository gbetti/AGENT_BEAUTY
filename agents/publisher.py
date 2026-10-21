"""Prepara, verifica e pubblica un singolo feed Instagram già revisionato."""
import argparse
import json
from pathlib import Path
import sys

from instagram import InstagramClient, load_post, prepare_post, verify_public_image
from instagram_approval import offer_post, reply_to_offer

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    connect = commands.add_parser('connect', help='Verifica token e profilo, senza pubblicare')
    connect.add_argument('--username', required=True)
    prepare = commands.add_parser('prepare', help='Esporta JPEG e manifest da una campagna revisionata')
    prepare.add_argument('--database', type=Path, default=ROOT/'data/catalog.sqlite')
    prepare.add_argument('--generation', required=True)
    prepare.add_argument('--language', choices=('fr', 'it'), required=True)
    prepare.add_argument('--username', required=True)
    prepare.add_argument('--output', type=Path, required=True)
    for name, help_text in [('check', 'Controlla post, profilo e URL senza pubblicare'),
                            ('offer', 'Mostra il post e salva la domanda SÌ/NO'),
                            ('publish', 'Mostra il post e pubblica soltanto dopo la risposta SÌ')]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument('--post', type=Path, required=True)
        command.add_argument('--image-url', required=True, help='URL HTTPS pubblico del feed.jpg preparato')
        if name != 'check':
            command.add_argument('--state', type=Path, default=ROOT/'data/instagram.sqlite',
                                 help='Registro persistente: riusare lo stesso per tutti gli invii')
    respond = commands.add_parser('respond', help='Applica la risposta dell’utente a una domanda salvata')
    respond.add_argument('--request', required=True, help='ID della domanda restituito da offer')
    respond.add_argument('--answer', required=True, help='Risposta esplicita dell’utente: SÌ oppure NO')
    respond.add_argument('--state', type=Path, default=ROOT/'data/instagram.sqlite')
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            path = prepare_post(args.database, args.generation, args.language, args.username, args.output)
            print(f'Preparato, non pubblicato: {path}')
        elif args.command == 'connect':
            client = InstagramClient.from_environment()
            result = client.profile(args.username)
            limit = client.request('GET', f"{result['id']}/content_publishing_limit")
            print(json.dumps({'status': 'connected', **result, 'publishing_limit': limit.get('data')},
                             ensure_ascii=False, indent=2))
        elif args.command == 'respond':
            result = reply_to_offer(args.request, args.answer, args.state)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            post = load_post(args.post)
            client = InstagramClient.from_environment()
            if args.command == 'check':
                profile = client.profile(post['username'])
                verify_public_image(args.image_url, post['image_sha256'])
                print(json.dumps({'status': 'checked_not_published', 'profile': profile,
                                  'language': post['language'], 'caption': post['caption']},
                                 ensure_ascii=False, indent=2))
            else:
                result = offer_post(args.post, args.image_url, args.state, client)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                if args.command == 'publish' and sys.stdin.isatty():
                    if result['status'] in ('approved', 'published'):
                        result = reply_to_offer(result['request_id'], 'SI', args.state, client=client)
                        print(json.dumps(result, ensure_ascii=False, indent=2))
                        return
                    try:
                        answer = input(result['question'] + ' ')
                    except (EOFError, KeyboardInterrupt):
                        print('\nNessuna risposta: richiesta conservata, nessun invio avviato.')
                    else:
                        result = reply_to_offer(result['request_id'], answer, args.state, client=client)
                        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        # Local files contain public campaign data only; the client sanitizes API failures.
        parser.exit(1, f'Instagram: {error}\n')


if __name__ == '__main__':
    main()

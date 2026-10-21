"""Prepara, verifica e pubblica un singolo feed Instagram già revisionato."""
import argparse
import json
from pathlib import Path

from instagram import InstagramClient, load_post, prepare_post, publish_post, verify_public_image

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
                            ('publish', 'Pubblica il feed e registra l’esito')]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument('--post', type=Path, required=True)
        command.add_argument('--image-url', required=True, help='URL HTTPS pubblico del feed.jpg preparato')
        if name == 'publish':
            command.add_argument('--state', type=Path, default=ROOT/'data/instagram.sqlite',
                                 help='Registro persistente: riusare lo stesso per tutti gli invii')
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            path = prepare_post(args.database, args.generation, args.language, args.username, args.output)
            print(f'Preparato, non pubblicato: {path}')
        elif args.command == 'connect':
            result = InstagramClient.from_environment().profile(args.username)
            print(json.dumps({'status': 'connected', **result}, ensure_ascii=False, indent=2))
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
                result = publish_post(post, args.image_url, args.state, client)
                print(json.dumps({k: result[k] for k in ('status', 'media_id', 'permalink', 'container_id')},
                                 ensure_ascii=False, indent=2))
    except Exception as error:
        # Local files contain public campaign data only; the client sanitizes API failures.
        parser.exit(1, f'Instagram: {error}\n')


if __name__ == '__main__':
    main()

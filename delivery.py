"""Required creative bundle and durable handoff to Codex's connected Gmail tool.

The Python renderer cannot call a Codex connector. It records pending delivery;
the Codex workflow sends the prepared request and records Gmail's actual receipt.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from html import escape
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
from urllib.request import urlopen

from PIL import Image

ROOT = Path(__file__).resolve().parent
POLICY = ROOT / 'delivery-policy.json'
FILES = ('feed.png', 'caption.txt', 'story.png', 'email.html', 'email.eml', 'email-logo.png')
SIZES = {'feed.png': (1080, 1350), 'story.png': (1080, 1920)}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_policy():
    config = json.loads(POLICY.read_text(encoding='utf-8'))
    email = config['email']
    if (config['languages'] != ['fr', 'it'] or email['provider'] != 'gmail'
            or email['language'] not in config['languages'] or email['required'] is not True
            or '@' not in email['to'] or any(c.isspace() for c in email['to'])):
        raise ValueError('Configurazione di consegna Gmail non valida.')
    return config


def bundle_files(directory):
    """Reject incomplete/incorrect exports before any email can be sent."""
    directory = Path(directory)
    hashes = {}
    for language in read_policy()['languages']:
        folder = directory / language
        for name in FILES:
            path = folder / name
            if path.is_symlink() or not path.is_file() or not path.stat().st_size:
                raise ValueError(f'Pacchetto incompleto: manca {language}/{name}.')
            hashes[f'{language}/{name}'] = sha256(path.read_bytes())
        for name, size in SIZES.items():
            with Image.open(folder / name) as image:
                if image.format != 'PNG' or image.size != size:
                    raise ValueError(f'Formato non valido: {language}/{name}, richiesto PNG {size}.')
                image.verify()
        if not (folder / 'caption.txt').read_text(encoding='utf-8').strip():
            raise ValueError(f'Caption vuota: {language}.')
        message = BytesParser(policy=policy.default).parsebytes((folder / 'email.eml').read_bytes())
        images = {str(part['Content-ID']): part.get_payload(decode=True)
                  for part in message.walk() if part.get_content_maintype() == 'image'}
        if images.get('<campaign-feed>') != (folder / 'feed.png').read_bytes():
            raise ValueError(f'L’email {language} non incorpora il PNG originale del post.')
        if images.get('<ioma-logo>') != (folder / 'email-logo.png').read_bytes():
            raise ValueError(f'Il logo incorporato nell’email {language} non corrisponde.')
        if not message['Subject'] or message.get_body(preferencelist=('html',)) is None:
            raise ValueError(f'Email {language} priva di oggetto o HTML.')
    return hashes


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def create_manifest(directory, generation_id):
    directory = Path(directory)
    path = directory / 'delivery.json'
    if path.exists():
        raise FileExistsError('Il registro di consegna esiste già; non azzerare lo stato dell’invio.')
    manifest = {'schema_version': 1, 'generation_id': generation_id, 'created_at': now(),
                'required_outputs': ['post', 'email', 'story'],
                'status': 'pending_email', 'files': bundle_files(directory),
                'email': {**read_policy()['email'], 'status': 'pending', 'sent': False}}
    write_json(path, manifest)
    return manifest


@contextmanager
def locked_manifest(directory):
    directory = Path(directory)
    lock = directory / '.delivery.lock'
    try:
        handle = lock.open('x')
    except FileExistsError:
        raise RuntimeError('Un’altra operazione di consegna è in corso.') from None
    try:
        handle.close()
        path = directory / 'delivery.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        yield manifest
        write_json(path, manifest)
    finally:
        lock.unlink()


def verify_manifest(directory, manifest):
    if bundle_files(directory) != manifest['files']:
        raise ValueError('Gli asset sono cambiati dopo la preparazione: rivalidare la campagna.')
    configured = read_policy()['email']
    if any(manifest['email'].get(k) != v for k, v in configured.items()):
        raise ValueError('Destinatario, lingua o provider non corrispondono alla configurazione corrente.')


def prepare_gmail_request(directory, assets_url):
    directory = Path(directory)
    parsed = urlsplit(assets_url)
    if (parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password
            or parsed.query or parsed.fragment or any(c.isspace() for c in assets_url)):
        raise ValueError('Serve una base HTTPS pubblica senza credenziali, query o frammenti.')
    with locked_manifest(directory) as manifest:
        if manifest['email']['status'] not in ('pending', 'ready'):
            raise ValueError('Invio già iniziato o concluso: non preparare una seconda email.')
        verify_manifest(directory, manifest)
        language = manifest['email']['language']
        folder = directory / language
        base = assets_url.rstrip('/') + '/' + language
        # Gmail will load these exact public PNG bytes; no generated replacement.
        for name in ('feed.png', 'email-logo.png'):
            with urlopen(base + '/' + name, timeout=30) as response:
                remote = response.read()
            if sha256(remote) != manifest['files'][language + '/' + name]:
                raise ValueError(f'L’asset pubblico {name} non corrisponde al file verificato.')
        message = BytesParser(policy=policy.default).parsebytes((folder / 'email.eml').read_bytes())
        html = message.get_body(preferencelist=('html',)).get_content()
        html = html.replace('cid:campaign-feed', escape(base + '/feed.png', quote=True))
        html = html.replace('cid:ioma-logo', escape(base + '/email-logo.png', quote=True))
        if 'cid:' in html or '{% unsubscribe_link %}' in html:
            raise ValueError('L’email contiene ancora immagini o tag non risolti.')
        request = {'to': manifest['email']['to'], 'subject': str(message['Subject']),
                   'payload': {'mime_type': 'text/html', 'body': {'content': html}},
                   'response_fields': ['id', 'thread_id', 'label_ids']}
        # Omit from_address: send using the authenticated Gmail account, never spoof IOMA.
        write_json(directory / 'gmail-request.json', request)
        manifest['email'].update(status='ready', assets_url=assets_url,
                                 request_sha256=sha256((directory / 'gmail-request.json').read_bytes()))
    return request


def begin_send(directory):
    directory = Path(directory)
    with locked_manifest(directory) as manifest:
        if manifest['email']['status'] != 'ready':
            raise ValueError('Email non pronta o invio già tentato: verificare Gmail prima di riprovare.')
        verify_manifest(directory, manifest)
        request = (directory / 'gmail-request.json').read_bytes()
        if sha256(request) != manifest['email']['request_sha256']:
            raise ValueError('La richiesta Gmail è stata modificata dopo la verifica.')
        manifest['email'].update(status='sending', attempt_started_at=now())
        manifest['status'] = 'pending_email'
    return json.loads(request)


def record_sent(directory, receipt, database=None):
    directory = Path(directory)
    if not receipt.get('id') or 'SENT' not in receipt.get('label_ids', []):
        raise ValueError('Serve la ricevuta reale di Gmail con id e label SENT.')
    with locked_manifest(directory) as manifest:
        email = manifest['email']
        if email['status'] == 'sent' and email.get('message_id') == receipt['id']:
            pass  # Reconcile SQLite safely after a prior database failure.
        elif email['status'] != 'sending':
            raise ValueError('Nessun tentativo di invio corrispondente alla ricevuta.')
        else:
            email.update(status='sent', sent=True, message_id=receipt['id'],
                         thread_id=receipt.get('thread_id'), sent_at=now())
            manifest['status'] = 'complete'
    if database is not None:
        with sqlite3.connect(database) as db:
            row = db.execute('SELECT research_json FROM generations WHERE id=?',
                             (manifest['generation_id'],)).fetchone()
            if row:
                report = json.loads(row[0])
                report['delivery'] = manifest
                language = manifest['email']['language']
                email_report = report.get('localizations', {}).get(language, {}).get('email')
                if email_report is not None:
                    email_report.update(sent=True, gmail_message_id=receipt['id'])
                db.execute('UPDATE generations SET research_json=? WHERE id=?',
                           (json.dumps(report, ensure_ascii=False), manifest['generation_id']))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'begin-send', 'record-sent', 'status'))
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--assets-url')
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--database', type=Path, default=ROOT / 'data/catalog.sqlite')
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            if not args.assets_url:
                parser.error('prepare richiede --assets-url')
            prepare_gmail_request(args.campaign, args.assets_url)
            print(args.campaign / 'gmail-request.json')
        elif args.action == 'begin-send':
            print(json.dumps(begin_send(args.campaign), ensure_ascii=False))
        elif args.action == 'record-sent':
            if not args.receipt:
                parser.error('record-sent richiede --receipt')
            receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
            result = record_sent(args.campaign, receipt, args.database)
            print(json.dumps({'status': result['status'], 'email': result['email']}, ensure_ascii=False))
        else:
            print((args.campaign / 'delivery.json').read_text(encoding='utf-8'))
    except Exception as error:
        parser.exit(1, f'Errore consegna: {error}\n')


if __name__ == '__main__':
    main()

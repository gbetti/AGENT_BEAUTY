"""Deliver reviewed campaign emails and original assets to the authorized recipient."""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
POLICY = ROOT/'assets/email/delivery.json'
LOCAL_POLICY = ROOT/'data/email-settings.json'
FILES = ('feed.png', 'story.png', 'banner.png', 'presentazione.pptx',
         'email.html', 'email.eml', 'email-logo.png')
TYPES = {'png': 'image/png', 'html': 'text/html', 'eml': 'application/octet-stream',
         'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'mp4': 'video/mp4'}


class DeliveryError(RuntimeError):
    """Public diagnostic, excluding credentials and provider response bodies."""


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def address(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', value):
        raise DeliveryError('Serve un solo indirizzo email valido, senza nomi o intestazioni.')
    return value.lower()


def delivery_policy():
    result = json.loads(POLICY.read_text())
    # Private recipient configuration stays out of the public repository.
    if LOCAL_POLICY.is_file() and POLICY == ROOT/'assets/email/delivery.json':
        result.update(json.loads(LOCAL_POLICY.read_text()))
    recipients = result.get('recipients', [result['recipient']])
    if not isinstance(recipients, list) or not recipients or len(recipients) != len(set(recipients)):
        raise DeliveryError('Lista destinatari autorizzati non valida.')
    result['recipients'] = [address(item) for item in recipients]
    result['recipient'] = ', '.join(result['recipients'])
    return result


def delivery_intent():
    config = delivery_policy()
    return {'recipient': 'configured_private_allowlist', 'languages': config['languages'],
            'requires_instagram_link': True,
            'status': 'awaiting_visual_review', 'send_after_visual_review': config['send_after_visual_review']}


def prepare_delivery(campaign, review, output):
    """Package existing reviewed originals. Never renders, sends or changes the campaign."""
    campaign, output = Path(campaign).resolve(), Path(output).resolve()
    quality = review.get('quality', {})
    if quality.get('visual_review') != 'passed' or quality.get('technical_checks') != 'passed':
        raise DeliveryError('Completa la revisione visiva prima di inviare gli asset.')
    config = delivery_policy()
    packets = []
    for language in config['languages']:
        files = []
        names = FILES + (('reel.mp4',) if (campaign/language/'reel.mp4').is_file() else ())
        for name in names:
            path = campaign/language/name
            raw = path.read_bytes()
            sha = digest(raw)
            if quality.get('reviewed_sha256', {}).get(f'{language}/{name}') != sha:
                raise DeliveryError(f'File non revisionato o cambiato: {language}/{name}.')
            files.append({'name': name, 'path': os.path.relpath(path, output),
                          'sha256': sha, 'bytes': len(raw),
                          'content_type': TYPES[name.rsplit('.', 1)[-1]]})
        source = BytesParser(policy=policy.default).parsebytes((campaign/language/'email.eml').read_bytes())
        if not source.get_body(preferencelist=('html',)) or not source['Subject']:
            raise DeliveryError('Email della campagna priva di oggetto o corpo HTML.')
        inline = {str(p['Content-ID']): p.get_payload(decode=True) for p in source.walk() if p['Content-ID']}
        if (inline.get('<campaign-feed>') != (campaign/language/'feed.png').read_bytes()
                or inline.get('<ioma-logo>') != (campaign/language/'email-logo.png').read_bytes()):
            raise DeliveryError('Le immagini incorporate non corrispondono agli originali revisionati.')
        packet = {'generation_id': review['generation_id'], 'language': language,
                  'recipient': config['recipient'], 'subject': str(source['Subject']), 'files': files}
        identity = {**packet, 'files': [{k: v for k, v in f.items() if k != 'path'} for f in files]}
        packet['id'] = digest(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode())
        packets.append(packet)
    manifest = {'schema_version': 1, 'status': 'prepared_not_sent',
                'generation_id': review['generation_id'], 'packets': packets}
    output.mkdir(parents=True, exist_ok=True)
    path = output/'delivery.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise DeliveryError('La cartella contiene già una consegna diversa; scegli una nuova cartella.')
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    return path


def prepare_generation(database, generation, output):
    with sqlite3.connect(f'{Path(database).resolve().as_uri()}?mode=ro', uri=True) as db:
        row = db.execute('SELECT research_json FROM generations WHERE id=?', (generation,)).fetchone()
    if not row:
        raise DeliveryError('Generazione non trovata.')
    report = json.loads(row[0])
    if report.get('email_delivery', {}).get('requires_instagram_link'):
        receipt = report.get('instagram_publication', {})
        if receipt.get('status') != 'published' or not receipt.get('permalink') or any(
                item.get('email', {}).get('instagram_url') != receipt['permalink']
                for item in report['localizations'].values()):
            raise DeliveryError('Pubblica il post e finalizza le email con il permalink Instagram prima dell’invio.')
    campaign = Path(report['localizations']['fr']['graphics']['feed']['path']).parent.parent
    return prepare_delivery(campaign, {'generation_id': generation, 'quality': report['quality']}, output)


def load_delivery(path):
    path = Path(path).resolve()
    manifest = json.loads(path.read_text())
    config = delivery_policy()
    if [p['language'] for p in manifest['packets']] != config['languages']:
        raise DeliveryError('La consegna deve contenere francese e italiano.')
    for packet in manifest['packets']:
        if packet['recipient'] != config['recipient']:
            raise DeliveryError('Destinatario diverso da quello autorizzato.')
        if [f['name'] for f in packet['files']] not in (list(FILES), list(FILES)+['reel.mp4']):
            raise DeliveryError('Consegna incompleta.')
        identity = {k: v for k, v in packet.items() if k != 'id'}
        identity['files'] = [{k: v for k, v in f.items() if k != 'path'} for f in packet['files']]
        if digest(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()) != packet['id']:
            raise DeliveryError('Manifest della consegna modificato.')
        for item in packet['files']:
            raw = (path.parent/item['path']).read_bytes()
            if digest(raw) != item['sha256'] or len(raw) != item['bytes']:
                raise DeliveryError('Un asset è cambiato dopo la preparazione.')
    return manifest


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OutlookClient:
    """Delegated Microsoft Graph. Uses the authenticated mailbox, never the draft's From."""
    def __init__(self, token, sender, opener=None):
        if not token or any(c.isspace() for c in token):
            raise DeliveryError('Mittente non collegato: configura OUTLOOK_ACCESS_TOKEN nei segreti, non in chat.')
        self._token, self.sender = token, address(sender)
        self.opener = opener or build_opener(NoRedirect())

    @classmethod
    def from_environment(cls):
        return cls(os.environ.get('OUTLOOK_ACCESS_TOKEN', ''), os.environ.get('BEAUTY_EMAIL_SENDER', ''))

    def request(self, method, path, body=None):
        if not path.startswith('/me') or '\n' in path or '\r' in path:
            raise DeliveryError('Endpoint email non valido.')
        request = Request('https://graph.microsoft.com/v1.0'+path, method=method,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={'Authorization': 'Bearer '+self._token, 'Content-Type': 'application/json',
                                   'Prefer': 'IdType="ImmutableId"'})
        try:
            with self.opener.open(request, timeout=45) as response:
                raw = response.read(16_000_000)
                if not raw:
                    if response.status != 202:
                        raise DeliveryError('Risposta email inattesa; verificare lo stato prima di riprovare.')
                    return {'accepted': True}
                return json.loads(raw)
        except HTTPError as error:
            raise DeliveryError(f'Outlook HTTP {error.code}; controlla account e permessi. Nessun reinvio automatico.') from None
        except (URLError, OSError, ValueError):
            raise DeliveryError('Risposta Outlook incerta. Verificare lo stato, senza reinviare automaticamente.') from None

    def profile(self):
        result = self.request('GET', '/me?$select=id,mail,userPrincipalName')
        actual = address(result.get('mail') or result.get('userPrincipalName') or '')
        if actual != self.sender or not result.get('id'):
            raise DeliveryError('Il mittente autenticato non corrisponde a BEAUTY_EMAIL_SENDER.')
        return {'id': result['id'], 'email': actual}


@contextmanager
def delivery_register(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path)+'.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with sqlite3.connect(path) as db:
            db.row_factory = sqlite3.Row
            db.execute('CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY, account_id TEXT NOT NULL, '
                       'recipient TEXT NOT NULL, language TEXT NOT NULL, status TEXT NOT NULL, '
                       'message_id TEXT, updated_at TEXT NOT NULL)')
            db.commit()
            yield db


def status_rows(state):
    with delivery_register(state) as db:
        return [dict(row) for row in db.execute('SELECT * FROM deliveries ORDER BY updated_at')]


def update(db, packet, status, message_id=None):
    db.execute('UPDATE deliveries SET status=?, message_id=COALESCE(?, message_id), updated_at=? WHERE id=?',
               (status, message_id, datetime.now(timezone.utc).isoformat(), packet['id']))
    db.commit()


def send_delivery(manifest_path, state, client=None):
    """Send once per reviewed packet. An uncertain write is reconciled, never replayed."""
    manifest_path = Path(manifest_path).resolve()
    manifest = load_delivery(manifest_path)  # Validate both languages before remote mutations.
    if any(f['bytes'] >= 3_000_000 for p in manifest['packets'] for f in p['files']):
        raise DeliveryError('Allegato oltre il limite Outlook di 3 MB; nessun invio avviato.')
    frozen = {}
    for packet in manifest['packets']:
        originals = {f['name']: (manifest_path.parent/f['path']).read_bytes() for f in packet['files']}
        if any(digest(originals[f['name']]) != f['sha256'] for f in packet['files']):
            raise DeliveryError('Un asset è cambiato durante la preparazione dell’invio.')
        frozen[packet['id']] = originals
    client = client or OutlookClient.from_environment()
    profile = client.profile()
    results = []
    with delivery_register(state) as db:
        for packet in manifest['packets']:
            row = db.execute('SELECT * FROM deliveries WHERE id=?', (packet['id'],)).fetchone()
            if row:
                if row['account_id'] != profile['id']:
                    raise DeliveryError('Consegna già associata a un altro account mittente.')
                if row['status'] == 'sent':
                    results.append(dict(row))
                    continue
                if row['status'] in ('sending', 'accepted', 'uncertain') and row['message_id']:
                    remote = client.request('GET', '/me/messages/'+quote(row['message_id'], safe='')
                                            +'?$select=id,isDraft,sentDateTime')
                    if remote.get('isDraft') is False and remote.get('sentDateTime'):
                        update(db, packet, 'sent')
                        results.append(dict(db.execute('SELECT * FROM deliveries WHERE id=?', (packet['id'],)).fetchone()))
                        continue
                    if row['status'] == 'accepted':
                        results.append(dict(row))
                        continue
                raise DeliveryError('Consegna già iniziata con esito da verificare: nessun reinvio. Conserva il registro.')
            db.execute('INSERT INTO deliveries VALUES(?,?,?,?,?,?,?)',
                       (packet['id'], profile['id'], packet['recipient'], packet['language'],
                        'preparing', None, datetime.now(timezone.utc).isoformat()))
            db.commit()
            try:
                originals = frozen[packet['id']]
                source = BytesParser(policy=policy.default).parsebytes(originals['email.eml'])
                draft = client.request('POST', '/me/messages', {
                    'subject': packet['subject'],
                    'body': {'contentType': 'HTML', 'content': source.get_body(preferencelist=('html',)).get_content()},
                    'toRecipients': [{'emailAddress': {'address': address(item.strip())}} for item in packet['recipient'].split(',')],
                    'internetMessageHeaders': [{'name': 'x-beauty-delivery-id', 'value': packet['id']}],
                })
                message_id = draft.get('id')
                if not isinstance(message_id, str) or not message_id:
                    raise DeliveryError('Outlook non ha restituito l’ID della bozza.')
                update(db, packet, 'attaching', message_id)
                endpoint = '/me/messages/'+quote(message_id, safe='')
                for item in packet['files']:
                    attachment = {'@odata.type': '#microsoft.graph.fileAttachment', 'name': item['name'],
                                  'contentType': item['content_type'],
                                  'contentBytes': base64.b64encode(originals[item['name']]).decode()}
                    if item['name'] in ('feed.png', 'email-logo.png'):
                        attachment.update(isInline=True, contentId='campaign-feed' if item['name'] == 'feed.png' else 'ioma-logo')
                    client.request('POST', endpoint+'/attachments', attachment)
                update(db, packet, 'sending')  # Commit before the irreversible send request.
                result = client.request('POST', endpoint+'/send')
                if result.get('accepted') is not True:
                    raise DeliveryError('Invio senza conferma del servizio; verificare lo stato.')
                update(db, packet, 'accepted')
                results.append(dict(db.execute('SELECT * FROM deliveries WHERE id=?', (packet['id'],)).fetchone()))
            except Exception:
                current = db.execute('SELECT status FROM deliveries WHERE id=?', (packet['id'],)).fetchone()[0]
                update(db, packet, 'uncertain' if current == 'sending' else 'incomplete_draft')
                raise
    return {'recipient': delivery_policy()['recipient'], 'messages': results,
            'note': 'accepted = accettato da Outlook; sent = presente tra gli inviati. Nessuna prova di recapito in inbox.'}

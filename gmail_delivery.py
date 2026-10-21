"""Prepare exact MIME trees for the connected Gmail tool, with durable send receipts."""
import base64
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
import json
import os
from pathlib import Path

from email_delivery import (DeliveryError, address, delivery_policy, delivery_register,
                            digest, load_delivery, update)


def build_requests(manifest_path, sender):
    manifest_path = Path(manifest_path).resolve()
    sender = address(sender)
    if sender != delivery_policy().get('sender'):
        raise DeliveryError('Il profilo Gmail non corrisponde al mittente configurato.')
    manifest = load_delivery(manifest_path)
    requests = []
    for packet in manifest['packets']:
        originals = {f['name']: (manifest_path.parent/f['path']).read_bytes() for f in packet['files']}
        if any(digest(originals[f['name']]) != f['sha256'] for f in packet['files']):
            raise DeliveryError('Asset cambiato durante la preparazione Gmail.')
        source = BytesParser(policy=policy.default).parsebytes(originals['email.eml'])
        related = {'mime_type': 'multipart/related', 'parts': [
            {'mime_type': 'text/html', 'charset': 'UTF-8',
             'body': {'content': source.get_body(preferencelist=('html',)).get_content()}}]}
        attachments = []
        for item in packet['files']:
            part = {'mime_type': item['content_type'], 'filename': item['name'],
                    'content_disposition': 'attachment',
                    'body': {'base64_url_content': base64.urlsafe_b64encode(originals[item['name']]).decode()}}
            if item['name'] in ('feed.png', 'email-logo.png'):
                part.update(content_disposition='inline',
                            content_id='campaign-feed' if item['name'] == 'feed.png' else 'ioma-logo')
                related['parts'].append(part)
            else:
                attachments.append(part)
        request = {'from_address': sender, 'to': packet['recipient'], 'subject': packet['subject'],
                   'payload': {'mime_type': 'multipart/mixed', 'parts': [related]+attachments},
                   'response_fields': ['id', 'thread_id', 'label_ids']}
        if len(json.dumps(request).encode()) > 25_000_000:
            raise DeliveryError('Il messaggio supera il limite conservativo di 25 MB codificati.')
        requests.append({'packet_id': packet['id'], 'language': packet['language'], 'request': request})
    return requests


def export_requests(manifest_path, sender):
    manifest_path = Path(manifest_path).resolve()
    requests = build_requests(manifest_path, sender)
    path = manifest_path.parent/'gmail-requests.json'
    value = {'manifest': os.path.relpath(manifest_path, path.parent), 'sender': address(sender), 'requests': requests}
    path.write_text(json.dumps(value, ensure_ascii=False)+'\n')
    # Per-language files make tool transfers independent and avoid exposing binary data in chat.
    summaries = []
    for entry in requests:
        request_path = path.parent/(entry['language']+'-gmail-request.json')
        raw = (json.dumps(entry['request'], ensure_ascii=False)+'\n').encode()
        request_path.write_bytes(raw)
        summaries.append({'language': entry['language'], 'packet_id': entry['packet_id'],
                          'request_path': str(request_path), 'bytes': len(raw), 'sha256': digest(raw)})
    return {'status': 'prepared_for_gmail_not_sent', 'requests_path': str(path),
            'sender': address(sender), 'messages': summaries}


def reserve_request(requests_path, language, state):
    """Commit before calling gmail.send_email. Any existing attempt blocks a second send."""
    requests_path = Path(requests_path).resolve()
    prepared = json.loads(requests_path.read_text())
    expected = build_requests(requests_path.parent/prepared['manifest'], prepared['sender'])
    if prepared['requests'] != expected:
        raise DeliveryError('La richiesta Gmail è cambiata rispetto alla consegna revisionata.')
    entry = next((p for p in expected if p['language'] == language), None)
    if entry is None:
        raise DeliveryError('Lingua Gmail non presente.')
    raw = (json.dumps(entry['request'], ensure_ascii=False)+'\n').encode()
    request_path = requests_path.parent/(language+'-gmail-request.json')
    if request_path.read_bytes() != raw:
        raise DeliveryError('Il file destinato al connettore Gmail è stato modificato.')
    with delivery_register(state) as db:
        row = db.execute('SELECT * FROM deliveries WHERE id=?', (entry['packet_id'],)).fetchone()
        if row:
            raise DeliveryError('Consegna già registrata: verificare il messaggio Gmail, senza reinviare.')
        db.execute('INSERT INTO deliveries VALUES(?,?,?,?,?,?,?)', (
            entry['packet_id'], 'gmail:'+prepared['sender'], entry['request']['to'], language,
            'connector_sending', None, datetime.now(timezone.utc).isoformat()))
        db.commit()
    return {'packet_id': entry['packet_id'], 'language': language, 'request_path': str(request_path),
            'bytes': len(raw), 'sha256': digest(raw), 'status': 'connector_sending'}


def record_result(packet_id, response, state):
    """Only a real Gmail result with an immutable message ID and SENT label is success."""
    message_id = response.get('id')
    if not isinstance(message_id, str) or not message_id or 'SENT' not in response.get('label_ids', []):
        raise DeliveryError('Risposta Gmail non confermata: conservare lo stato e riconciliare, senza reinvio.')
    with delivery_register(state) as db:
        row = db.execute('SELECT * FROM deliveries WHERE id=?', (packet_id,)).fetchone()
        if not row or not row['account_id'].startswith('gmail:'):
            raise DeliveryError('Tentativo Gmail non registrato.')
        if row['status'] == 'sent' and row['message_id'] != message_id:
            raise DeliveryError('La consegna ha già un diverso ID Gmail.')
        update(db, {'id': packet_id}, 'sent', message_id)
        result = dict(db.execute('SELECT * FROM deliveries WHERE id=?', (packet_id,)).fetchone())
    return {**result, 'thread_id': response.get('thread_id'),
            'note': 'Invio Gmail confermato, non prova di recapito nella casella del destinatario.'}

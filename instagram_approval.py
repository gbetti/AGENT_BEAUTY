"""Persist a question about one exact post, then act on the user's SI/NO reply."""
from datetime import datetime, timezone
import json
from pathlib import Path
import unicodedata
import uuid

from instagram import (InstagramClient, InstagramError, digest, load_post,
                       publication_store, publish_post, username, verify_public_image, verify_public_video)


def publication_question(target, language):
    label = {'fr': 'francese', 'it': 'italiano'}[language]
    return f'Vuoi pubblicare questo feed in {label} su Instagram @{username(target)}? [SÌ/NO]'


def fingerprint(post):
    return digest(json.dumps(post, sort_keys=True, ensure_ascii=False).encode('utf-8'))


def parse_answer(answer):
    normalized = ''.join(c for c in unicodedata.normalize('NFD', answer.strip().upper())
                         if not unicodedata.combining(c))
    if normalized not in ('SI', 'NO'):
        raise InstagramError('Rispondi SÌ oppure NO al singolo post; nessuna pubblicazione avviata.')
    return normalized


def approval_table(db):
    db.execute('''CREATE TABLE IF NOT EXISTS instagram_approvals (
        id TEXT PRIMARY KEY, account_id TEXT NOT NULL, post_path TEXT NOT NULL,
        fingerprint TEXT NOT NULL, image_url TEXT NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, answered_at TEXT)''')
    db.commit()


def offer_post(post_path, image_url, state_path, client, *, check_image=verify_public_image, check_video=verify_public_video):
    """Only read Meta and the public image; never create a media container."""
    post_path = Path(post_path).resolve()
    post = load_post(post_path)
    account = client.profile(post['username'])
    if post.get('kind') == 'reel':
        check_video(image_url, post['video_sha256'])
    else:
        check_image(image_url, post['image_sha256'])
    content_hash = fingerprint(post)
    with publication_store(state_path) as db:
        approval_table(db)
        row = db.execute('SELECT * FROM instagram_approvals WHERE account_id=? '
                         'AND fingerprint=? AND image_url=? AND status != ? '
                         'ORDER BY created_at DESC LIMIT 1',
                         (account['id'], content_hash, image_url, 'declined')).fetchone()
        if row is None:
            request_id = uuid.uuid4().hex
            db.execute('INSERT INTO instagram_approvals VALUES (?,?,?,?,?,?,?,?)',
                       (request_id, account['id'], str(post_path), content_hash, image_url,
                        'pending', datetime.now(timezone.utc).isoformat(), None))
            db.commit()
            row = db.execute('SELECT * FROM instagram_approvals WHERE id=?', (request_id,)).fetchone()
        elif row['post_path'] != str(post_path):
            # A moved checkout may reuse the durable register. Only relocate an
            # identical validated post; the consent fingerprint stays unchanged.
            db.execute('UPDATE instagram_approvals SET post_path=? WHERE id=?', (str(post_path), row['id']))
            db.commit()
        return {'request_id': row['id'], 'status': row['status'],
                'question': publication_question(post['username'], post['language']).replace('questo feed', 'questo Reel' if post.get('kind') == 'reel' else 'questo feed'),
                'username': post['username'], 'language': post['language'],
                'image_url': row['image_url'], 'caption': post['caption']}


def reply_to_offer(request_id, answer, state_path, *, client=None):
    """A yes is scoped to the saved account, image and caption, never future posts."""
    answer = parse_answer(answer)
    with publication_store(state_path) as db:
        approval_table(db)
        row = db.execute('SELECT * FROM instagram_approvals WHERE id=?', (request_id,)).fetchone()
        if row is None:
            raise InstagramError('Richiesta di pubblicazione non trovata: mostra prima il post con offer.')
        row = dict(row)
        if answer == 'NO':
            if row['status'] not in ('pending', 'declined'):
                raise InstagramError('Il SÌ è già stato registrato: verifica l’esito, non è possibile annullare l’invio qui.')
            db.execute('UPDATE instagram_approvals SET status=?, answered_at=? WHERE id=?',
                       ('declined', datetime.now(timezone.utc).isoformat(), request_id))
            db.commit()
            return {'request_id': request_id, 'status': 'declined_not_published'}
        if row['status'] == 'declined':
            raise InstagramError('Questo post è stato rifiutato. Crea una nuova domanda con offer prima di confermarlo.')
        post = load_post(row['post_path'])
        if fingerprint(post) != row['fingerprint']:
            raise InstagramError('Il post è cambiato dopo la domanda: mostra una nuova anteprima e chiedi di nuovo conferma.')
        client = client if client is not None else InstagramClient.from_environment()
        if client.profile(post['username'])['id'] != row['account_id']:
            raise InstagramError('Il profilo non corrisponde a quello mostrato nella domanda.')
        if row['status'] == 'pending':
            db.execute('UPDATE instagram_approvals SET status=?, answered_at=? WHERE id=?',
                       ('approved', datetime.now(timezone.utc).isoformat(), request_id))
            db.commit()
    # The existing publisher takes the same lock and commits before the remote write.
    # An approved request survives errors/crashes and resumes without a second consent.
    result = publish_post(post, row['image_url'], state_path, client)
    with publication_store(state_path) as db:
        db.execute('UPDATE instagram_approvals SET status=? WHERE id=?', ('published', request_id))
        db.commit()
    return {'request_id': request_id,
            **{key: result[key] for key in ('status', 'media_id', 'permalink', 'container_id')}}

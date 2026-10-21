"""Bounded, durable permission for a user-requested batch; normal offers stay unchanged."""
from datetime import datetime, timezone
import json
from pathlib import Path

from instagram import InstagramError, digest, load_post, publication_store, publish_post


def publish_authorized(grant_path, slot, post_path, media_url, state, client, **kwargs):
    grant = json.loads(Path(grant_path).read_text())
    now = datetime.now(timezone.utc)
    if (grant.get('schema_version') != 1 or grant.get('authorization') != 'explicit_user_batch'
            or not grant.get('instruction') or not 1 <= grant.get('limit', 0) <= 5
            or not 1 <= slot <= grant['limit'] or not grant.get('id')
            or now > datetime.fromisoformat(grant['expires_at'])):
        raise InstagramError('Autorizzazione del lotto assente, scaduta o fuori limite.')
    post = load_post(post_path)
    if post['username'] != grant['username'] or post['language'] != grant['language']:
        raise InstagramError('Profilo o lingua diversi dal lotto autorizzato.')
    fingerprint = digest(json.dumps(post, sort_keys=True, ensure_ascii=False).encode())
    # Persist a slot BEFORE any remote write, including failed or uncertain attempts.
    with publication_store(state) as db:
        db.execute('CREATE TABLE IF NOT EXISTS authorized_batch_slots ('
                   'grant_id TEXT, slot INTEGER, fingerprint TEXT, grant_sha256 TEXT, '
                   'PRIMARY KEY(grant_id,slot), UNIQUE(grant_id,fingerprint))')
        grant_hash = digest(json.dumps(grant, sort_keys=True, ensure_ascii=False).encode())
        row = db.execute('SELECT * FROM authorized_batch_slots WHERE grant_id=? AND slot=?', (grant['id'], slot)).fetchone()
        existing = db.execute('SELECT grant_sha256 FROM authorized_batch_slots WHERE grant_id=?', (grant['id'],)).fetchall()
        if any(item['grant_sha256'] != grant_hash for item in existing):
            raise InstagramError('L’autorizzazione del lotto è cambiata dopo il primo utilizzo.')
        if row and row['fingerprint'] != fingerprint:
            raise InstagramError('Questa posizione è già vincolata a un altro contenuto.')
        if not row:
            db.execute('INSERT INTO authorized_batch_slots VALUES(?,?,?,?)', (grant['id'], slot, fingerprint, grant_hash))
        db.commit()
    return publish_post(post, media_url, state, client, **kwargs)

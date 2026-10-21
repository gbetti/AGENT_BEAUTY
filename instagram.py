"""Instagram Login API: authenticated profile checks and durable feed publishing."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from PIL import Image

MAX_IMAGE_BYTES = 8 * 1024 * 1024
DEFAULT_API_VERSION = 'v26.0'


class InstagramError(RuntimeError):
    """A safe, actionable error; never includes access tokens or raw API bodies."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # In particular, never forward the Bearer header to another host.
        return None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def username(value):
    value = value.removeprefix('@').lower()
    if not re.fullmatch(r'[a-z0-9._]{1,30}', value):
        raise InstagramError('Nome profilo Instagram non valido.')
    return value


def object_id(value):
    value = str(value or '')
    if not re.fullmatch(r'[0-9]+', value):
        raise InstagramError('Instagram non ha restituito un ID valido.')
    return value


def https_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.fragment):
        raise InstagramError('Serve un URL HTTPS pubblico senza credenziali o frammenti.')
    return value


class InstagramClient:
    def __init__(self, token, version=DEFAULT_API_VERSION, *, opener=None):
        if not token or any(c.isspace() for c in token):
            raise InstagramError('Configura il segreto INSTAGRAM_ACCESS_TOKEN; non inserirlo in chat o Git.')
        if not re.fullmatch(r'v[0-9]+\.0', version):
            raise InstagramError('INSTAGRAM_API_VERSION deve avere formato v26.0.')
        self._token = token
        self.base = f'https://graph.instagram.com/{version}'
        self.opener = opener or build_opener(NoRedirect())

    @classmethod
    def from_environment(cls):
        return cls(os.environ.get('INSTAGRAM_ACCESS_TOKEN', ''),
                   os.environ.get('INSTAGRAM_API_VERSION', DEFAULT_API_VERSION))

    def request(self, method, path, **params):
        if not re.fullmatch(r'(me|[0-9]+)(/[a-z_]+)?', path):
            raise InstagramError('Endpoint Instagram non valido.')
        url = f'{self.base}/{path}'
        body = None
        if method == 'GET':
            url += '?' + urlencode(params)
        else:
            body = urlencode(params).encode('utf-8')
        request = Request(url, data=body, method=method, headers={
            'Authorization': f'Bearer {self._token}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'AGENT_BEAUTY/InstagramPublisher',
        })
        try:
            with self.opener.open(request, timeout=30) as response:
                result = json.loads(response.read(1024 * 1024))
        except HTTPError as error:
            # Meta may echo input in its message. Expose only numeric diagnostics.
            try:
                details = json.loads(error.read(65536)).get('error', {})
            except (ValueError, AttributeError):
                details = {}
            code = details.get('code') if isinstance(details, dict) else None
            subcode = details.get('error_subcode') if isinstance(details, dict) else None
            code = code if type(code) is int else None
            subcode = subcode if type(subcode) is int else None
            hints = {190: 'Token scaduto o revocato: autorizza nuovamente il profilo.',
                     10: 'Controlla i permessi e l’accesso dell’account all’app Meta.',
                     200: 'Controlla instagram_business_basic e instagram_business_content_publish.',
                     4: 'Limite API raggiunto; attendi prima di riprovare.',
                     32: 'Limite API raggiunto; attendi prima di riprovare.'}
            numeric = '/'.join(str(n) for n in (code, subcode) if type(n) is int)
            raise InstagramError(f'Instagram HTTP {error.code}, codice {numeric or "non disponibile"}. '
                                 + hints.get(code, 'Controlla configurazione Meta, formato e disponibilità del media.')) from None
        except (URLError, OSError, ValueError):
            raise InstagramError('Instagram non raggiungibile o risposta non valida. Nessun retry automatico delle scritture.') from None
        if not isinstance(result, dict) or 'error' in result:
            raise InstagramError('Instagram ha restituito una risposta non valida.')
        return result

    def profile(self, expected_username):
        result = self.request('GET', 'me', fields='user_id,username,account_type')
        # Meta documents both a direct object and a one-item data wrapper.
        if 'data' in result:
            rows = result['data']
            if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
                raise InstagramError('Risposta del profilo Instagram ambigua.')
            result = rows[0]
        if username(str(result.get('username', ''))) != username(expected_username):
            raise InstagramError('Il token appartiene a un profilo diverso da quello richiesto.')
        if str(result.get('account_type', '')).upper() not in ('BUSINESS', 'MEDIA_CREATOR'):
            raise InstagramError('La pubblicazione richiede un account Instagram Business o Creator.')
        return {'id': object_id(result.get('user_id')), 'username': username(expected_username),
                'account_type': result['account_type']}


def validate_caption(caption):
    if not isinstance(caption, str) or not caption.strip() or len(caption) > 2200:
        raise InstagramError('La caption deve contenere da 1 a 2200 caratteri.')
    if len(re.findall(r'(?<!\w)#\w+', caption)) > 30:
        raise InstagramError('La caption contiene più di 30 hashtag.')


def validate_jpeg(raw):
    if len(raw) > MAX_IMAGE_BYTES:
        raise InstagramError('Il JPEG supera 8 MB.')
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != 'JPEG' or image.size != (1080, 1350) or image.mode != 'RGB':
            raise InstagramError('Il feed deve essere JPEG RGB 1080×1350.')
        image.verify()


def prepare_post(database, generation_id, language, expected_username, output):
    """Export a portable posting manifest from an already reviewed generation."""
    if language not in ('fr', 'it'):
        raise InstagramError('Scegli una sola lingua: fr oppure it.')
    expected_username = username(expected_username)
    with sqlite3.connect(f'{Path(database).resolve().as_uri()}?mode=ro', uri=True) as db:
        row = db.execute('SELECT research_json FROM generations WHERE id=?', (generation_id,)).fetchone()
    if row is None:
        raise InstagramError('Generazione non trovata nel database.')
    report = json.loads(row[0])
    quality = report.get('quality', {})
    if quality.get('technical_checks') != 'passed' or quality.get('visual_review') != 'passed':
        raise InstagramError('Completa e registra la revisione tecnica e visiva prima della pubblicazione.')
    localization = report['localizations'][language]
    source = Path(localization['graphics']['feed']['path']).resolve()
    source_raw = source.read_bytes()
    source_hash = digest(source_raw)
    if quality.get('reviewed_sha256', {}).get(f'{language}/feed.png') != source_hash:
        raise InstagramError('Il feed è cambiato dopo la revisione visiva.')
    caption = localization['caption'].strip()
    validate_caption(caption)
    buffer = io.BytesIO()
    with Image.open(io.BytesIO(source_raw)) as image:
        if image.size != (1080, 1350) or image.mode != 'RGB':
            raise InstagramError('Il feed originale deve essere RGB 1080×1350.')
        image.save(buffer, 'JPEG', quality=95, subsampling=0, optimize=True)
    jpeg = buffer.getvalue()
    validate_jpeg(jpeg)
    output = Path(output).resolve()
    manifest = {
        'schema_version': 1, 'generation_id': generation_id, 'language': language,
        'username': expected_username, 'kind': 'feed', 'caption': caption,
        'caption_sha256': digest(caption.encode('utf-8')),
        'source_image': os.path.relpath(source, output), 'source_sha256': source_hash,
        'image': 'feed.jpg', 'image_sha256': digest(jpeg),
        'review': {'technical_checks': 'passed', 'visual_review': 'passed',
                   'reviewed_source_sha256': source_hash, 'reviewed_at': quality.get('reviewed_at')},
    }
    # A new directory prevents overwriting a manifest already used to publish.
    output.mkdir(parents=True, exist_ok=False)
    (output/'feed.jpg').write_bytes(jpeg)
    path = output/'post.json'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def load_post(path):
    path = Path(path).resolve()
    post = json.loads(path.read_text(encoding='utf-8'))
    if post.get('schema_version') != 1 or post.get('kind') not in ('feed', 'reel') or post.get('language') not in ('fr', 'it'):
        raise InstagramError('Manifest Instagram non supportato.')
    if not isinstance(post.get('generation_id'), str) or not post['generation_id']:
        raise InstagramError('Manca l’identificativo della generazione.')
    username(post['username'])
    validate_caption(post['caption'])
    if digest(post['caption'].encode('utf-8')) != post['caption_sha256']:
        raise InstagramError('La caption è cambiata dopo la preparazione.')
    review = post.get('review', {})
    if (review.get('technical_checks') != 'passed' or review.get('visual_review') != 'passed'
            or review.get('reviewed_source_sha256') != post['source_sha256']):
        raise InstagramError('Manca una revisione valida del feed originale.')
    if digest((path.parent/post['source_image']).read_bytes()) != post['source_sha256']:
        raise InstagramError('Il feed originale non corrisponde alla revisione.')
    raw = (path.parent/post['image']).read_bytes()
    if digest(raw) != post['image_sha256']:
        raise InstagramError('Il JPEG è cambiato dopo la preparazione.')
    validate_jpeg(raw)
    if post['kind'] == 'reel':
        video = (path.parent/post['video']).read_bytes()
        if digest(video) != post['video_sha256'] or post['review'].get('reviewed_video_sha256') != digest(video):
            raise InstagramError('Il Reel è cambiato dopo la revisione.')
        validate_video(path.parent/post['video'])
    return post


def validate_video(path):
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))
    streams = [s for s in info['streams'] if s['codec_type'] == 'video']
    if (len(streams) != 1 or streams[0]['codec_name'] != 'h264' or
            (streams[0]['width'], streams[0]['height']) != (1080, 1920) or
            not 3 <= float(info['format']['duration']) <= 60 or Path(path).stat().st_size > 24_000_000):
        raise InstagramError('Reel non valido: serve MP4 H264 1080×1920, 3–60 secondi, massimo 24 MB.')


def prepare_reel(database, generation_id, language, expected_username, output):
    with sqlite3.connect(database) as db:
        report = json.loads(db.execute('SELECT research_json FROM generations WHERE id=?', (generation_id,)).fetchone()[0])
    source = Path(report['localizations'][language]['graphics']['feed']['path']).parent/'reel.mp4'
    raw = source.read_bytes()
    if report['quality'].get('reviewed_sha256', {}).get(language+'/reel.mp4') != digest(raw):
        raise InstagramError('Completa la revisione dell’animazione prima della preparazione.')
    validate_video(source)
    path = prepare_post(database, generation_id, language, expected_username, output)
    post = json.loads(path.read_text())
    post.update(kind='reel', video='reel.mp4', video_sha256=digest(raw))
    post['review']['reviewed_video_sha256'] = digest(raw)
    (path.parent/'reel.mp4').write_bytes(raw)
    path.write_text(json.dumps(post, ensure_ascii=False, indent=2)+'\n')
    return path


def verify_public_video(url, expected_hash):
    https_url(url)
    with build_opener(NoRedirect()).open(Request(url), timeout=45) as response:
        raw = response.read(24_000_001)
        if response.headers.get_content_type() != 'video/mp4' or digest(raw) != expected_hash:
            raise InstagramError('Il video pubblico non coincide con il Reel revisionato.')
    with tempfile.NamedTemporaryFile(suffix='.mp4') as temporary:
        temporary.write(raw)
        temporary.flush()
        validate_video(temporary.name)


def verify_public_image(url, expected_hash, *, opener=None):
    """Fetch without credentials; reject redirects, HTML and altered image bytes."""
    https_url(url)
    opener = opener or build_opener(NoRedirect())
    try:
        with opener.open(Request(url, headers={'User-Agent': 'AGENT_BEAUTY/MediaCheck'}), timeout=30) as response:
            content_type = response.headers.get_content_type()
            raw = response.read(MAX_IMAGE_BYTES + 1)
    except (URLError, OSError):
        raise InstagramError('JPEG pubblico non raggiungibile: usa il link HTTPS diretto al file.') from None
    if content_type != 'image/jpeg':
        raise InstagramError('Il link pubblico non restituisce Content-Type image/jpeg.')
    validate_jpeg(raw)
    if digest(raw) != expected_hash:
        raise InstagramError('Il file pubblico non coincide con il JPEG preparato.')


@contextmanager
def publication_store(path):
    """Serialize processes while committing each irreversible boundary durably."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise InstagramError('Un’altra pubblicazione è in corso con questo registro.') from None
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        try:
            db.execute('''CREATE TABLE IF NOT EXISTS instagram_publications (
                account_id TEXT NOT NULL, generation_id TEXT NOT NULL, language TEXT NOT NULL,
                source_sha256 TEXT NOT NULL, fingerprint TEXT NOT NULL, image_url TEXT NOT NULL,
                status TEXT NOT NULL, container_id TEXT, media_id TEXT, permalink TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(account_id, generation_id, language), UNIQUE(account_id, source_sha256))''')
            db.commit()
            yield db
        finally:
            db.close()
            fcntl.flock(lock, fcntl.LOCK_UN)


def publish_post(post, image_url, state_path, client, *, check_image=verify_public_image,
                 check_video=verify_public_video, sleep=time.sleep, polls=5, poll_interval=10):
    """Publish once. An uncertain publish is reconciled read-only, never retried."""
    https_url(image_url)
    account = client.profile(post['username'])
    account_id = account['id']
    fingerprint = digest(json.dumps(post, sort_keys=True, ensure_ascii=False).encode('utf-8'))
    with publication_store(state_path) as db:
        key = (account_id, post['generation_id'], post['language'])

        def read():
            return db.execute('SELECT * FROM instagram_publications WHERE account_id=? '
                              'AND generation_id=? AND language=?', key).fetchone()

        def save(**values):
            values['updated_at'] = datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE instagram_publications SET ' + ','.join(f'{k}=?' for k in values)
                       + ' WHERE account_id=? AND generation_id=? AND language=?', (*values.values(), *key))
            db.commit()

        row = read()
        if row and row['fingerprint'] != fingerprint:
            raise InstagramError('Questo post è già nel registro con un contenuto diverso: non viene reinviato.')
        if row is None:
            try:
                db.execute('INSERT INTO instagram_publications '
                           '(account_id,generation_id,language,source_sha256,fingerprint,image_url,status,updated_at) '
                           'VALUES (?,?,?,?,?,?,?,?)', (*key, post['source_sha256'], fingerprint, image_url,
                                                     'prepared', datetime.now(timezone.utc).isoformat()))
                db.commit()
            except sqlite3.IntegrityError:
                raise InstagramError('Questa immagine è già nel registro per il profilo: invio duplicato bloccato.') from None
            row = read()

        if row['status'] == 'published':
            return dict(row)
        if row['status'] == 'publishing':
            status = client.request('GET', object_id(row['container_id']), fields='status_code').get('status_code')
            if status == 'PUBLISHED':
                save(status='published')
                return dict(read())
            raise InstagramError('Esito dell’invio precedente incerto. Verifica il post su Instagram; '
                                 'nessun nuovo invio. Mantieni il registro e ripeti solo la verifica.')
        if row['status'] == 'failed':
            raise InstagramError('Il contenitore è fallito o scaduto. Verifica l’errore Meta prima di una nuova preparazione.')
        if row['status'] == 'prepared':
            # Creating a container cannot publish a post; safe to retry after a lost response.
            if post.get('kind') == 'reel':
                check_video(image_url, post['video_sha256'])
                params = {'video_url': image_url, 'media_type': 'REELS', 'share_to_feed': 'true', 'thumb_offset': 0}
            else:
                check_image(image_url, post['image_sha256'])
                params = {'image_url': image_url}
            result = client.request('POST', f'{account_id}/media', caption=post['caption'], **params)
            save(status='container_created', container_id=object_id(result.get('id')), image_url=image_url)
            row = read()
        container_id = object_id(row['container_id'])
        for attempt in range(polls):
            status = client.request('GET', container_id, fields='status_code').get('status_code')
            if status == 'PUBLISHED':
                save(status='published')
                return dict(read())
            if status == 'FINISHED':
                break
            if status in ('ERROR', 'EXPIRED'):
                save(status='failed')
                raise InstagramError('Il contenitore Instagram è fallito o scaduto; nessun invio effettuato.')
            if status != 'IN_PROGRESS':
                raise InstagramError('Stato del contenitore sconosciuto; pubblicazione sospesa.')
            if attempt < polls - 1:
                sleep(poll_interval)
        else:
            raise InstagramError('Instagram sta ancora elaborando il contenitore. Ripeti il comando per riprenderlo.')
        # Persist BEFORE the request. A crash/timeout must not cause a duplicate post.
        save(status='publishing')
        try:
            result = client.request('POST', f'{account_id}/media_publish', creation_id=container_id)
            media_id = object_id(result.get('id'))
        except InstagramError as error:
            raise InstagramError(f'{error} Esito da verificare: ripeti il comando senza cambiare registro.') from None
        save(status='published', media_id=media_id)
        try:
            result = client.request('GET', media_id, fields='permalink')
            link = result.get('permalink', '')
            if urlsplit(link).scheme == 'https' and urlsplit(link).hostname in ('www.instagram.com', 'instagram.com'):
                save(permalink=link)
        except InstagramError:
            pass  # The post is already published; permalink failure must never trigger a retry.
        return dict(read())

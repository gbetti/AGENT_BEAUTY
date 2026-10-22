"""Publish one reviewed Italian story per campaign, with durable duplicate guards."""
import argparse
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image
from delivery import (ROOT, locked_manifest, now, read_policy, refresh_status,
                      sha256, sync_database, verify_manifest, write_json)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Unexpected API redirect; request stopped.')


def api(path, params=None, method='GET'):
    secret = os.environ['INSTAGRAM_ACCESS_TOKEN']
    url = 'https://graph.instagram.com/v25.0/' + path
    body = None
    if method == 'GET' and params:
        url += '?' + urllib.parse.urlencode(params)
    elif method == 'POST':
        body = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=body, method=method, headers={
        'Authorization': 'Bearer ' + secret,
        'Content-Type': 'application/x-www-form-urlencoded',
    })
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            error = json.loads(exc.read().decode()).get('error', {})
        except (ValueError, UnicodeDecodeError):
            error = {'message': 'Non-JSON API response'}
        safe = {key: error.get(key) for key in ('code', 'error_subcode', 'type', 'message', 'error_user_title', 'error_user_msg')}
        safe['http_status'] = exc.code
        raise RuntimeError(json.dumps(safe, ensure_ascii=False).replace(secret, '[REDACTED]')) from None


def story_state(directory, manifest):
    verify_manifest(directory, manifest)
    refresh_status(manifest)
    story = manifest['instagram_story']
    if any(story.get(k) != v for k, v in read_policy()['instagram_story'].items()):
        raise ValueError('Account o lingua della story diversi dalla configurazione autorizzata.')
    return story


def export_jpeg(directory):
    directory = Path(directory)
    with locked_manifest(directory) as manifest:
        story = story_state(directory, manifest)
        if story['status'] not in ('pending', 'ready'):
            raise ValueError('Pubblicazione già iniziata: non sostituire la story.')
        source = directory / story['language'] / 'story.png'
        destination = source.with_name('story-instagram.jpg')
        with Image.open(source) as image:
            rgba = image.convert('RGBA')
            canvas = Image.new('RGB', rgba.size, 'white')
            canvas.paste(rgba, mask=rgba.getchannel('A'))
            canvas.save(destination, 'JPEG', quality=96, subsampling=0)
        story.update(status='ready', image_sha256=sha256(destination.read_bytes()),
                     source_sha256=sha256(source.read_bytes()))
    return destination


def publish(directory, image_url=None, database=None):
    directory = Path(directory)
    with locked_manifest(directory) as manifest:
        story = story_state(directory, manifest)
        if story['status'] != 'published':
            # Every external mutation has a checkpoint on disk before the request.
            # If its response is lost, a subsequent run never blindly repeats it.
            def checkpoint():
                refresh_status(manifest)
                write_json(directory / 'delivery.json', manifest)

            account = api('me', {'fields': 'user_id,username'})
            if (str(account.get('user_id')) != story['account_id']
                    or account.get('username') != story['username']):
                raise ValueError('Il token Instagram appartiene a un account diverso da quello autorizzato.')
            if image_url and story.get('image_url') and image_url != story['image_url']:
                raise ValueError('La URL della story è cambiata dopo il primo tentativo.')
            if story['status'] == 'ready':
                parsed = urllib.parse.urlsplit(image_url or '')
                if (parsed.scheme != 'https' or not parsed.netloc or parsed.username
                        or parsed.password or parsed.fragment):
                    raise ValueError('Serve la URL HTTPS pubblica del JPEG verificato.')
                source = directory / story['language'] / 'story.png'
                jpeg = source.with_name('story-instagram.jpg')
                if (sha256(source.read_bytes()) != story['source_sha256']
                        or sha256(jpeg.read_bytes()) != story['image_sha256']):
                    raise ValueError('La story è cambiata dopo la verifica.')
                with urllib.request.urlopen(image_url, timeout=30) as response:
                    if (response.headers.get_content_type() != 'image/jpeg'
                            or sha256(response.read()) != story['image_sha256']):
                        raise ValueError('Il JPEG pubblico non corrisponde alla story verificata.')
                story.update(status='creating', image_url=image_url, create_attempted_at=now())
                checkpoint()
                created = api(story['account_id'] + '/media',
                              {'media_type': 'STORIES', 'image_url': image_url}, 'POST')
                story.update(status='created', container_id=created['id'])
                checkpoint()
            if story['status'] == 'created':
                result = api(story['container_id'], {'fields': 'status_code,status'})
                if result.get('status_code') != 'FINISHED':
                    raise RuntimeError('Container non pronto: ' + str(result.get('status_code'))
                                       + '. Riprendere lo stesso registro dopo la verifica.')
                story.update(status='publishing', publish_attempted_at=now())
                checkpoint()
                published = api(story['account_id'] + '/media_publish',
                                {'creation_id': story['container_id']}, 'POST')
                story.update(status='verifying', media_id=published['id'])
                checkpoint()
            if story['status'] == 'verifying':
                result = api(story['media_id'],
                             {'fields': 'id,permalink,media_type,media_product_type,timestamp,username'})
                if (str(result.get('id')) != str(story['media_id'])
                        or result.get('username') != story['username']
                        or result.get('media_product_type') != 'STORY'):
                    raise ValueError('Instagram non conferma la story sull’account previsto.')
                story.update(status='published', published=True, verified_at=now(),
                             published_media=result, permalink=result.get('permalink'),
                             published_at=result.get('timestamp'))
                checkpoint()
            if story['status'] != 'published':
                raise RuntimeError('Story non pronta o tentativo senza ricevuta. '
                                   'Verificare il registro e Instagram; non ripubblicare alla cieca.')
        refresh_status(manifest)
    sync_database(manifest, database)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'publish', 'status'))
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--image-url')
    parser.add_argument('--database', type=Path, default=ROOT / 'data/catalog.sqlite')
    args = parser.parse_args()
    try:
        if args.action == 'export':
            print(export_jpeg(args.campaign))
        elif args.action == 'publish':
            result = publish(args.campaign, args.image_url, args.database)
            print(json.dumps({'status': result['status'], 'instagram_story': result['instagram_story']},
                             ensure_ascii=False))
        else:
            print((args.campaign / 'delivery.json').read_text(encoding='utf-8'))
    except Exception as error:
        message = str(error)
        token = os.environ.get('INSTAGRAM_ACCESS_TOKEN')
        if token:
            message = message.replace(token, '[REDACTED]')
        parser.exit(1, f'Errore story Instagram: {message}\n')


if __name__ == '__main__':
    main()


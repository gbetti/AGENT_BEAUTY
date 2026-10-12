"""Export a concise IOMA email with the campaign's unmodified feed image."""
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime
from html import escape
import hashlib
import json
from pathlib import Path
import shutil
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from PIL import Image
from editorial import BRIEFS

ROOT = Path(__file__).resolve().parent
COPY_PATH = ROOT / 'assets/email/product-copy.json'
LOGO_PATH = ROOT / 'assets/brand/ioma-logo.png'
SENDER = 'IOMA Paris <contact@ioma-paris.com>'
UNSUBSCRIBE_MAILTO = 'mailto:contact@ioma-paris.com?subject=D%C3%A9sinscription'
LABELS = {
    'fr': {'expertise': 'L’EXPERTISE DU SOIN', 'unsubscribe': 'Se désabonner',
           'brand': 'IOMA Paris, une marque de IEVA Group.'},
    'it': {'expertise': 'LA COMPETENZA NELLA CURA', 'unsubscribe': 'Disiscriviti',
           'brand': 'IOMA Paris, un marchio di IEVA Group.'},
}


def https_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.netloc or parsed.username or
            parsed.password or any(ch.isspace() for ch in value)):
        raise ValueError('I link email e la base URL degli asset devono essere HTTPS validi.')
    return value


def campaign_email_copy(product, report, language='fr', history=(), subject=None):
    if language not in LABELS:
        raise ValueError('Lingua email supportata: fr oppure it.')
    entries = json.loads(COPY_PATH.read_text(encoding='utf-8'))
    key = product['id'].rsplit(':', 1)[-1]
    entry = entries.get(key)
    if not entry:
        raise ValueError('Testi email documentati mancanti per questo prodotto: nessun beneficio inventato.')
    if product['data']['editorial']['claim_it'] != BRIEFS[key]['claim_it']:
        raise ValueError('Il claim del catalogo è cambiato: aggiornare prima i testi email.')
    content = dict(entry[language])
    subjects = content.pop('subjects')
    previous = None
    for row in history:
        if row.get('product_id') != product['id']:
            continue
        prior = row.get('localizations', {}).get(language, {}).get('email', row.get('email', {}))
        if prior.get('language') == language:
            previous = prior.get('subject')
            break
    content['subject'] = subject if subject is not None else subjects[
        (subjects.index(previous) + 1) % len(subjects) if previous in subjects else 0]
    content['language'] = language
    for field, maximum in [('subject', 55), ('preheader', 100)]:
        value = content[field]
        if not value.strip() or len(value) > maximum or '\r' in value or '\n' in value:
            raise ValueError(f'{field} email: testo non vuoto, una riga, massimo {maximum} caratteri.')
    if len(' '.join(content[k] for k in ('lead', 'body', 'closing')).split()) > 70:
        raise ValueError('Email troppo lunga: massimo 70 parole nel testo commerciale.')
    base = https_url(entry['product_url'])
    parsed = urlsplit(base)
    campaign = report['created_at'].replace(':', '').replace('+', '').replace('.', '')
    query = dict(parse_qsl(parsed.query))
    query.update(utm_source='beauty_agent', utm_medium='email',
                 utm_campaign=key+'-'+campaign)
    content['product_url'] = urlunsplit(parsed._replace(query=urlencode(query)))
    return content


def email_html(content, image_source, logo_source, width, height, unsubscribe):
    """Email-client layout: tables, inline styles, fluid images and Outlook CTA."""
    e = lambda value: escape(str(value), quote=True)
    labels = LABELS[content['language']]
    # Klaviyo evaluates the tag before delivery; keep its quotes and spaces intact.
    unsub = unsubscribe if unsubscribe == '{% unsubscribe_link %}' else e(unsubscribe)
    benefits = '\n'.join(
        f'<p style="margin:0 0 12px;font:16px/1.6 Arial,Helvetica,sans-serif;">{e(line)}</p>'
        for line in content['body'].splitlines() if line.strip())
    return f'''<!doctype html>
<html lang="{e(content['language'])}" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="x-apple-disable-message-reformatting"><title>{e(content['subject'])}</title>
<style>body{{margin:0;padding:0;-webkit-text-size-adjust:100%;}}table{{border-collapse:collapse;}}img{{border:0;outline:none;display:block;}}
@media only screen and (max-width:620px){{.shell{{width:100%!important;}}.copy{{padding:28px 22px!important;}}.product-title{{font-size:27px!important;}}}}</style></head>
<body style="margin:0;padding:0;background-color:#F4F1EC;color:#191919;">
<div style="display:none!important;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">{e(content['preheader'])}{'&#8203;&nbsp;' * 80}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="width:100%;background-color:#F4F1EC;">
<tr><td align="center" style="padding:20px 0;">
<!--[if mso]><table role="presentation" width="600"><tr><td><![endif]-->
<table role="presentation" class="shell" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background-color:#FFFFFF;">
<tr><td align="center" style="padding:28px 24px 20px;">
<a href="{e(content['product_url'])}" style="text-decoration:none;"><img src="{e(logo_source)}" width="164" alt="IOMA Paris" style="width:164px;max-width:100%;height:auto;"></a>
<p style="margin:12px 0 0;font:10px Arial,Helvetica,sans-serif;letter-spacing:2.5px;color:#645D54;">{e(labels['expertise'])}</p></td></tr>
<tr><td style="padding:0;"><a href="{e(content['product_url'])}" style="text-decoration:none;">
<img src="{e(image_source)}" width="600" height="{round(600*height/width)}" alt="{e(content['title'])} — {e(content['campaign_headline'])}" style="width:100%;max-width:600px;height:auto;"></a></td></tr>
<tr><td class="copy" align="center" style="padding:34px 44px 38px;background-color:#FCFAF6;">
<h1 class="product-title" style="margin:0 0 20px;font:normal 30px/1.2 Georgia,'Times New Roman',serif;color:#191919;">{e(content['title'])}</h1>
<p style="margin:0 0 12px;font:600 16px/1.6 Arial,Helvetica,sans-serif;">{e(content['lead'])}</p>
{benefits}
<p style="margin:0 0 26px;font:16px/1.6 Arial,Helvetica,sans-serif;">{e(content['closing'])}</p>
<!--[if mso]><v:roundrect href="{e(content['product_url'])}" style="height:48px;v-text-anchor:middle;width:270px;" arcsize="0%" strokecolor="#191919" fillcolor="#191919"><w:anchorlock/><center style="color:#FFFFFF;font-family:Arial,sans-serif;font-size:13px;font-weight:bold;">{e(content['cta'].upper())}</center></v:roundrect><![endif]-->
<!--[if !mso]><!--><a href="{e(content['product_url'])}" style="display:inline-block;background-color:#191919;color:#FFFFFF;padding:16px 28px;font:600 13px/16px Arial,Helvetica,sans-serif;letter-spacing:1px;text-decoration:none;text-align:center;">{e(content['cta'].upper())}</a><!--<![endif]-->
</td></tr>
<tr><td align="center" style="padding:24px 24px 28px;border-top:1px solid #EAE4DC;">
<p style="margin:0 0 7px;font:600 11px/1.5 Arial,Helvetica,sans-serif;letter-spacing:1.5px;">IOMA PARIS</p>
<p style="margin:0 0 7px;font:11px/1.6 Arial,Helvetica,sans-serif;color:#706B64;">87 Rue Réaumur · 75002 Paris</p>
<p style="margin:0 0 12px;font:11px/1.6 Arial,Helvetica,sans-serif;color:#706B64;">{e(labels['brand'])}</p>
<a href="{unsub}" style="font:11px/1.5 Arial,Helvetica,sans-serif;color:#706B64;text-decoration:underline;">{e(labels['unsubscribe'])}</a>
</td></tr></table><!--[if mso]></td></tr></table><![endif]-->
</td></tr></table></body></html>'''


def create_email(product, report, feed, directory, *, language='fr', history=(),
                 subject=None, assets_url=None, unsubscribe_url=None):
    directory = Path(directory)
    feed = Path(feed)
    if feed.resolve() != (directory/'feed.png').resolve():
        raise ValueError('L’email deve usare il feed della stessa campagna e della stessa cartella.')
    content = campaign_email_copy(product, report, language, history, subject)
    content['campaign_headline'] = report['headline']
    with Image.open(feed) as image:
        if image.format != 'PNG':
            raise ValueError('L’immagine email deve essere il PNG del feed esportato.')
        width, height = image.size
    image_bytes, logo_bytes = feed.read_bytes(), LOGO_PATH.read_bytes()
    shutil.copyfile(LOGO_PATH, directory/'email-logo.png')
    if assets_url:
        base = https_url(assets_url).rstrip('/')+'/'
        if urlsplit(base).query or urlsplit(base).fragment:
            raise ValueError('La base URL degli asset non deve contenere query o frammenti.')
        image_source, logo_source = base+'feed.png', base+'email-logo.png'
    else:
        image_source, logo_source = 'feed.png', 'email-logo.png'
    if unsubscribe_url:
        https_url(unsubscribe_url)
    web_unsubscribe = unsubscribe_url or '{% unsubscribe_link %}'
    draft_unsubscribe = unsubscribe_url or UNSUBSCRIBE_MAILTO
    html_path, eml_path = directory/'email.html', directory/'email.eml'
    html_path.write_text(email_html(content,image_source,logo_source,width,height,web_unsubscribe),encoding='utf-8')
    # A MIME draft opens offline: CID attachments preserve the very same PNG bytes.
    message=EmailMessage(policy=policy.SMTP)
    message['Subject']=content['subject']
    message['From']=SENDER
    message['Reply-To']='contact@ioma-paris.com'
    message['Date']=format_datetime(datetime.fromisoformat(report['created_at']))
    message['X-Unsent']='1'
    message['X-Beauty-Agent-Preheader']=content['preheader']
    message['List-Unsubscribe']='<'+draft_unsubscribe+'>'
    plain='\n\n'.join(content[k] for k in ('title','lead','body','closing'))
    plain+='\n\n'+content['cta']+' : '+content['product_url']
    plain+='\n\nIOMA PARIS · 87 Rue Réaumur · 75002 Paris\n'+LABELS[language]['unsubscribe']+' : '+draft_unsubscribe
    message.set_content(plain)
    message.add_alternative(email_html(content,'cid:campaign-feed','cid:ioma-logo',width,height,draft_unsubscribe),subtype='html')
    related=message.get_payload()[-1]
    related.add_related(image_bytes,maintype='image',subtype='png',cid='<campaign-feed>',filename='feed.png',disposition='inline')
    related.add_related(logo_bytes,maintype='image',subtype='png',cid='<ioma-logo>',filename='email-logo.png',disposition='inline')
    eml_path.write_bytes(message.as_bytes())
    return {**content, 'html_path':html_path, 'eml_path':eml_path,
            'logo_path':directory/'email-logo.png', 'image_path':feed,
            'image_sha256':hashlib.sha256(image_bytes).hexdigest(),
            'image_size':[width,height], 'html_images':'hosted' if assets_url else 'local',
            'html_unsubscribe':'custom' if unsubscribe_url else 'Klaviyo unsubscribe_link',
            'draft_unsubscribe':'custom' if unsubscribe_url else 'mailto contact@ioma-paris.com',
            'body_word_count':len(' '.join(content[k] for k in ('lead','body','closing')).split()),
            'sent':False}

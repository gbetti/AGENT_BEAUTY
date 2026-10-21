"""Rotate content types and build reproducible, non-repeating studio designs."""
import hashlib
import json
from pathlib import Path
import random
import secrets
import uuid

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
MODES = ('product', 'model', 'pack')
PALETTES = {
    'sage': ((239, 244, 231), (189, 207, 180)),
    'rose': ((251, 237, 233), (226, 192, 190)),
    'sky': ((237, 244, 249), (183, 205, 220)),
    'honey': ((251, 242, 222), (222, 196, 142)),
    'lilac': ((245, 239, 249), (205, 188, 221)),
    'sand': ((248, 243, 234), (212, 193, 168)),
}
MOTIFS = ('arch', 'halo', 'diagonal', 'panels')


def family(product):
    return 'hair' if product['data'].get('editorial', {}).get('theme') == 'hair' else 'skin'


def pack_product(product):
    if not product['images']:
        raise ValueError('Manca la fotografia originale per '+product['name'])
    image = product['images'][0]
    path = Path(image['path']).resolve()
    portable = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return {'id': product['id'], 'name': product['name'], 'image': {**image, 'path': portable},
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def plan_direction(product, history, *, mode='auto', products=(), pack_keys=()):
    previous = next((r['creative'] for r in history if r.get('creative')), {})
    last_mode = previous.get('content_mode')
    if mode == 'auto':
        mode = MODES[(MODES.index(last_mode)+1) % len(MODES)] if last_mode in MODES else 'product'
    if mode not in MODES:
        raise ValueError('Direzione creativa non supportata.')
    if pack_keys and mode != 'pack':
        raise ValueError('--pack-products richiede --creative-mode pack.')
    recent = [r.get('creative', {}).get('scene', {}).get('design', {}) for r in history[:3]]
    available = [name for name in PALETTES if name not in {d.get('palette') for d in recent}]
    palette = secrets.choice(available or list(PALETTES))
    motif = secrets.choice([m for m in MOTIFS if not recent or m != recent[0].get('motif')])
    design_id = 'studio-' + uuid.uuid4().hex
    while any(r.get('creative', {}).get('design_id') == design_id for r in history):
        design_id = 'studio-' + uuid.uuid4().hex
    chosen = [product]
    if mode == 'pack':
        candidates = [p for p in products if p['id'] != product['id']
                      and p['data'].get('editorial') and family(p) == family(product) and p['images']]
        if pack_keys:
            keys = set(pack_keys)
            selected = [p for p in candidates if p['id'].rsplit(':', 1)[-1] in keys]
            if {p['id'].rsplit(':', 1)[-1] for p in selected} != keys:
                raise ValueError('Pack: prodotti mancanti, non revisionati, duplicati o incompatibili.')
            chosen.extend(selected)
        elif candidates:
            chosen.append(secrets.choice(candidates))
        if not 2 <= len(chosen) <= 3:
            raise ValueError('Il pack richiede due o tre prodotti originali dello stesso ambito.')
    direction = {'id': design_id, 'mode': mode, 'renderer_version': 'variety-studio-v1',
                 'family': family(product), 'palette': palette,
                 'motif': motif, 'seed': secrets.randbits(48),
                 'products': [pack_product(p) for p in chosen]}
    used = {r.get('creative', {}).get('scene', {}).get('design', {}).get('background_sha256') for r in history}
    checksum = hashlib.sha256(draw_background(direction, (200, 250)).tobytes()).hexdigest()
    while checksum in used:
        direction['seed'] = secrets.randbits(48)
        checksum = hashlib.sha256(draw_background(direction, (200, 250)).tobytes()).hexdigest()
    direction['background_sha256'] = checksum
    if mode == 'model':
        manifest = json.loads((ROOT/'assets/models/manifest.json').read_text())
        direction['model'] = secrets.choice(manifest)
    return direction


def draw_background(design, size):
    """Seeded light, architectural shape and palette; quiet areas protect copy."""
    rng = random.Random(design['seed'])
    paper, accent = PALETTES[design['palette']]
    w, h = 200, 250
    image = Image.new('RGB', (w, h))
    pixels = []
    cx, cy = rng.uniform(.15, .85), rng.uniform(.6, .85)
    for y in range(h):
        for x in range(w):
            weight = max(0, 1-((x/w-cx)**2+(y/h-cy)**2)**.5)*.32
            pixels.append(tuple(round(p*(1-weight)+a*weight) for p, a in zip(paper, accent)))
    image.putdata(pixels)
    image = image.resize(size, Image.Resampling.LANCZOS).convert('RGBA')
    shape = Image.new('RGBA', size)
    draw = ImageDraw.Draw(shape)
    def box(values):
        return tuple(v*size[i % 2]/(w if i % 2 == 0 else h) for i, v in enumerate(values))
    x = rng.randint(75, 130)
    top = rng.randint(92, 119)
    if design['motif'] == 'arch':
        draw.rounded_rectangle(box((x, top, x+85, 272)), radius=43*size[0]/w, fill=accent+(95,))
    elif design['motif'] == 'halo':
        draw.ellipse(box((x-85, top, x+85, top+160)), fill=accent+(105,))
    elif design['motif'] == 'diagonal':
        coords=box((0, top+50, 200, top-25, 200, 250, 0, 250))
        draw.polygon(list(zip(coords[::2],coords[1::2])), fill=accent+(75,))
    else:
        draw.rectangle(box((x-55, top, x-4, 250)), fill=accent+(80,))
        draw.rectangle(box((x+12, top+20, x+65, 250)), fill=accent+(115,))
    image.alpha_composite(shape.filter(ImageFilter.GaussianBlur(1)))
    # A continuous light floor supports every bottle; no ingredient props.
    floor = Image.new('RGBA', image.size)
    ImageDraw.Draw(floor).rectangle(box((0, 170, w, h)), fill=paper+(120,))
    image.alpha_composite(floor.filter(ImageFilter.GaussianBlur(size[1]*.04)))
    return image

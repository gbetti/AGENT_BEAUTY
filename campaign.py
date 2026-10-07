"""Three coordinated campaign formats using local, original brand/product assets."""
from pathlib import Path
import json
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
BACKGROUND_PATH = ROOT / 'assets/backgrounds/ioma-campaign.png'
LOGO_PATH = ROOT / 'assets/brand/ioma-logo.png'
COPY_PATH = ROOT / 'assets/campaign-copy.json'
FORMATS = {'feed': (1080, 1350), 'story': (1080, 1920), 'banner': (300, 250)}
PORTRAIT_SIZE = (1024, 1536)
LANDSCAPE_SIZE = (1536, 1024)
FEED_CROP = (0, 128, 1024, 1408)
BANNER_CROP = (154, 0, 1383, 1024)


def campaign_copy(product, headline=None, cta=None):
    defaults = json.loads(COPY_PATH.read_text(encoding='utf-8'))
    editorial = product['data'].get('editorial', {})
    if headline is None:
        headline = editorial.get('headline_it') or defaults['headlines'].get(product['id'])
    if cta is None:
        cta = editorial.get('cta_it') or defaults['cta']
    if not isinstance(headline, str) or not headline.strip():
        raise ValueError('Manca la headline italiana: usa --headline con un massimo di 4 parole.')
    if len(headline.split()) > 4:
        raise ValueError('La stessa headline deve funzionare nel banner: massimo 4 parole. Il testo non viene abbreviato automaticamente.')
    if not isinstance(cta, str) or not cta.strip() or '\n' in cta or '\r' in cta:
        raise ValueError('La CTA deve essere un testo italiano non vuoto su una sola riga.')
    # Preserve all supplied letters, accents, punctuation and case.
    return headline, cta


def packshot_layer(photo_path):
    """Keep original asset bytes; remove the connected exterior white in composition."""
    with Image.open(photo_path) as source:
        photo = source.convert('RGB')
    minimum = ImageChops.darker(photo.getchannel('R'),
                               ImageChops.darker(photo.getchannel('G'), photo.getchannel('B')))
    # JPEG compression makes exterior white vary slightly around the silhouette.
    exterior = minimum.point(lambda value: 255 if value >= 245 else 0)
    for corner in [(0, 0), (photo.width-1, 0), (0, photo.height-1),
                   (photo.width-1, photo.height-1)]:
        if exterior.getpixel(corner) == 255:
            ImageDraw.floodfill(exterior, corner, 128)
    alpha = exterior.point(lambda value: 0 if value == 128 else 255)
    # Trim the contaminated white rim instead of regrowing it with MaxFilter.
    # This is a two-pixel correction on the high-resolution source only.
    alpha = alpha.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.MinFilter(5))
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.0))
    result = photo.convert('RGBA')
    result.putalpha(alpha)
    bounds = alpha.getbbox()
    if bounds is None:
        raise RuntimeError('La foto non contiene un packshot visibile.')
    return result.crop(bounds)


def face(size, bold=False, font_path=None):
    try:
        return ImageFont.truetype(font_path or ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'), size)
    except OSError as error:
        raise RuntimeError('Font non disponibile: usa --font /percorso/font.ttf') from error


def editorial_font(text):
    name = 'NotoSerifCJKsc-Regular.otf' if any('\u3400' <= c <= '\u9fff' for c in text) else 'DejaVuSerif.ttf'
    return str(ROOT/'assets/fonts'/name)


def wrap(text, font, width):
    lines = []
    for paragraph in text.splitlines():
        current = ''
        chinese = any('\u3400' <= c <= '\u9fff' for c in paragraph)
        for word in (list(paragraph) if chinese else paragraph.split()):
            trial = (current + ('' if chinese else ' ') + word).strip()
            if font.getlength(trial) > width and current:
                lines.append(current)
                current = word
            else:
                current = trial
        if current:
            lines.append(current)
    return lines


def fit_text(text, box, maximum, minimum, bold, font_path=None, single_line=False):
    width, height = box[2]-box[0], box[3]-box[1]
    for size in range(maximum, minimum-1, -2):
        font = face(size, bold, font_path)
        lines = [text] if single_line else wrap(text, font, width)
        step = math.ceil(size * 1.18)
        if lines and len(lines)*step <= height and all(font.getlength(line) <= width for line in lines):
            return font, lines, step, size
    raise ValueError('Il testo non entra in modo leggibile: fornisci una headline/CTA più corta. Nessuna lettera è stata cambiata.')


def rectangle_union_area(boxes):
    """Bounding-box union, conservatively counting logo and the entire CTA button."""
    xs = sorted({x for b in boxes for x in (b[0], b[2])})
    area = 0
    for left, right in zip(xs, xs[1:]):
        spans = sorted((b[1], b[3]) for b in boxes if b[0] < right and b[2] > left)
        covered = 0
        start = end = None
        for bottom, top in spans:
            if start is None:
                start, end = bottom, top
            elif bottom > end:
                covered += end-start
                start, end = bottom, top
            else:
                end = max(end, top)
        if start is not None:
            covered += end-start
        area += (right-left)*covered
    return area


def luminance(color):
    values = [channel/255 for channel in color[:3]]
    linear = [value/12.92 if value <= .04045 else ((value+.055)/1.055)**2.4 for value in values]
    return .2126*linear[0]+.7152*linear[1]+.0722*linear[2]


def contrast(first, second):
    low, high = sorted((luminance(first), luminance(second)))
    return (high+.05)/(low+.05)


def text_contrast(image, box, ink):
    region = image.crop(box).convert('RGB')
    extrema = [region.getchannel(channel).getextrema() for channel in ('R','G','B')]
    darkest = tuple(e[0] for e in extrema)
    lightest = tuple(e[1] for e in extrema)
    ratio = min(contrast(ink, darkest), contrast(ink, lightest))
    if ratio < 4.5:
        raise ValueError('Contrasto headline/sfondo insufficiente: la grafica non viene esportata.')
    return ratio


def draw_headline(image, text, box, ink, font_path, maximum, minimum):
    font, lines, step, size = fit_text(text, box, maximum, minimum, False, font_path or editorial_font(text))
    draw = ImageDraw.Draw(image)
    left, top = box[:2]
    ratio = text_contrast(image, box, ink)
    for line in lines:
        draw.text((left, top), line, font=font, fill=ink, anchor='lt')
        top += step
    actual = (left, box[1], left+max(math.ceil(font.getlength(line)) for line in lines), box[1]+len(lines)*step)
    return {'kind': 'headline', 'text': text, 'lines': lines, 'box': actual,
            'font_size': size, 'weight': 'regular', 'contrast_ratio': ratio}


def draw_cta(image, text, box, ink, fill, font_path, maximum, minimum, padding):
    inner = (box[0]+padding, box[1], box[2]-padding, box[3])
    font, lines, _, size = fit_text(text, inner, maximum, minimum, False, font_path or editorial_font(text), single_line=True)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(box, radius=math.ceil((box[3]-box[1])*0.16), fill=fill)
    draw.text(((box[0]+box[2])/2, (box[1]+box[3])/2), text, font=font, fill=ink, anchor='mm')
    return {'kind': 'cta', 'text': text, 'lines': lines, 'box': box,
            'font_size': size, 'weight': 'regular', 'contrast_ratio': contrast(ink, fill)}


def background(size, scene=None):
    path = ROOT/scene['path'] if scene else BACKGROUND_PATH
    with Image.open(path) as original:
        original=original.convert('RGB')
        if scene:
            # Align each photographed support plane with the product's baseline.
            original=ImageOps.fit(original,PORTRAIT_SIZE,method=Image.Resampling.LANCZOS)
            centering=(.5,.5)
            if size == LANDSCAPE_SIZE:
                anchor_y=scene.get('portrait_anchor',[700,1140])[1]
                centering=(.5,max(0,min(1,(anchor_y*1.5-930)/(1536*1.5-1024))))
            image=ImageOps.fit(original,size,method=Image.Resampling.LANCZOS,centering=centering).convert('RGBA')
        else:
            image = ImageOps.fit(original, size).convert('RGBA')
    corners = [image.getpixel(p)[:3] for p in [(0, 0), (size[0]-1, 0), (0, size[1]-1), (size[0]-1, size[1]-1)]]
    white = all(min(color) >= 248 for color in corners)
    if scene:
        return image, bool(scene['light'])
    if not white:
        # At most ~100 RGB even over a white highlight: readable warm-white text.
        image.alpha_composite(Image.new('RGBA', size, (18, 12, 8, 164)))
    return image, white


def protect_text_field(image, box, ink, light):
    """Preserve the setting; soften only the area that needs readable typography."""
    try:
        text_contrast(image, box, ink)
        return
    except ValueError:
        pass
    tint = (255,249,240) if light else (18,12,8)
    for opacity in (155,205,240):
        mask = Image.new('L',image.size)
        left,top,right,bottom = box
        ImageDraw.Draw(mask).rectangle((left-120,top-120,right+120,bottom+120),fill=opacity)
        mask = mask.filter(ImageFilter.GaussianBlur(36))
        overlay = Image.new('RGBA',image.size,tint+(0,));overlay.putalpha(mask)
        image.alpha_composite(overlay)
        try:
            text_contrast(image,box,ink)
            return
        except ValueError:
            continue
    raise ValueError('Il testo non è leggibile sull’ambientazione selezionata.')


def logo_layer(width, white):
    with Image.open(LOGO_PATH) as original:
        original = original.convert('RGBA')
        alpha = ImageChops.multiply(original.getchannel('A'), ImageOps.invert(original.convert('L')))
    color = (255, 249, 240) if white else (24, 18, 14)
    logo = Image.new('RGBA', original.size, color+(0,))
    logo.putalpha(alpha)
    logo = logo.resize((width, round(width*original.height/original.width)), Image.Resampling.LANCZOS)
    return logo


def composite_product(image, photo, box):
    """Sample the original cutout once, directly to final export dimensions."""
    left, top, right, bottom = [round(value) for value in box]
    resized = photo.resize((right-left, bottom-top), Image.Resampling.LANCZOS)
    center_x = (left+right)/2
    shadow = Image.new('RGBA', image.size)
    ImageDraw.Draw(shadow).ellipse((center_x-resized.width*.4, bottom-5,
                                  center_x+resized.width*.4, bottom+12), fill=(20,12,5,95))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)))
    image.alpha_composite(resized, (left,top))


def master(product_photo, headline, cta, landscape=False, font_path=None, include_product=True, scene=None):
    size = LANDSCAPE_SIZE if landscape else PORTRAIT_SIZE
    image, white_background = background(size,scene)
    ink = (24, 18, 14) if white_background else (255, 249, 240)
    button_fill = ink
    button_ink = (255, 249, 240) if white_background else (24, 18, 14)
    elements = []
    if landscape:
        logo_xy, logo_width = (639, 70), 260
        headline_box = (225, 315, 890, 625)
        cta_box = (225, 785, 850, 940)
        photo_limit, center_x, bottom = (330, 600), 1140, 930
        headline_sizes, cta_sizes, padding = (104, 76), (68, 58), 28
    else:
        logo_xy, logo_width = (437, 196), 150
        headline_box = (64, 310, 960, 500)
        cta_box = (292, 1250, 732, 1335)
        photo_limit, center_x, bottom = (480, 600), 700, 1140
        headline_sizes, cta_sizes, padding = (84, 54), (36, 28), 26
    if scene:
        anchor_x,anchor_y=scene.get('portrait_anchor',[700,1140])
        if landscape:
            center_x=round(anchor_x*1.5)
        else:
            center_x,bottom=anchor_x,anchor_y
            photo_limit=(480,min(600,bottom-520))
    # The product and the background are the SAME source assets in all formats.
    photo = product_photo.copy()
    photo.thumbnail(photo_limit, Image.Resampling.LANCZOS)
    xy = (center_x-photo.width//2, bottom-photo.height)
    if include_product:
        shadow = Image.new('RGBA', image.size)
        ImageDraw.Draw(shadow).ellipse((center_x-photo.width*0.4, bottom-5,
                                      center_x+photo.width*0.4, bottom+12), fill=(20, 12, 5, 95))
        image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)))
        image.alpha_composite(photo, xy)
    elements.append({'kind': 'product', 'box': (xy[0], xy[1], xy[0]+photo.width, xy[1]+photo.height)})
    logo = logo_layer(logo_width, not white_background)
    protect_text_field(image, (*logo_xy,logo_xy[0]+logo.width,logo_xy[1]+logo.height), ink,white_background)
    protect_text_field(image,headline_box,ink,white_background)
    image.alpha_composite(logo, logo_xy)
    elements.append({'kind': 'logo', 'box': (*logo_xy, logo_xy[0]+logo.width, logo_xy[1]+logo.height)})
    elements.append(draw_headline(image, headline, headline_box, ink, font_path, *headline_sizes))
    elements.append(draw_cta(image, cta, cta_box, button_ink, button_fill, font_path, *cta_sizes, padding))
    return image, elements, white_background


def transform(elements, sx, sy, ox=0, oy=0):
    result = []
    for element in elements:
        value = dict(element)
        left, top, right, bottom = element['box']
        value['box'] = [left*sx+ox, top*sy+oy, right*sx+ox, bottom*sy+oy]
        if 'font_size' in value:
            value['font_size'] *= min(sx, sy)
        result.append(value)
    return result


def check_layout(kind, elements):
    width, height = FORMATS[kind]
    top = height*0.13 if kind == 'story' else height*0.05
    bottom = height*(1-0.18) if kind == 'story' else height*0.95
    for element in elements:
        left, upper, right, lower = element['box']
        if left < width*0.05-0.01 or right > width*0.95+0.01 or upper < top-0.01 or lower > bottom+0.01:
            raise ValueError(f'{kind}: {element["kind"]} supera i margini o la safe zone.')
    if kind == 'story':
        headline = next(e for e in elements if e['kind'] == 'headline')
        if headline['box'][3] > top+(bottom-top)/3:
            raise ValueError('Story: headline fuori dal terzo superiore utile.')
    text_elements = [e['box'] for e in elements if e['kind'] != 'product']
    ratio = rectangle_union_area(text_elements)/(width*height)
    if kind == 'feed' and ratio > 0.20:
        raise ValueError('Feed: il testo occupa oltre il 20% della superficie.')
    return ratio


def render_campaign(product, headline, cta, directory, font_path=None, scene=None):
    if not product.get('images'):
        raise RuntimeError('Nessuna foto collegata al prodotto nel database: '+product['name'])
    photo_path = Path(product['images'][0]['path'])
    if not photo_path.is_file():
        raise RuntimeError('Foto prodotto non trovata: '+str(photo_path))
    for asset in (ROOT/scene['path'] if scene else BACKGROUND_PATH, LOGO_PATH):
        if not asset.is_file():
            raise RuntimeError('Asset grafico non trovato: '+str(asset))
    if not headline.strip() or len(headline.split()) > 4:
        raise ValueError('Headline richiesta: massimo 4 parole, identiche in tutte le grafiche.')
    photo = packshot_layer(photo_path)
    # Keep the packshot as a separate original layer while adapting the masters.
    portrait, portrait_elements, _ = master(photo, headline, cta, font_path=font_path, include_product=False, scene=scene)
    # Nothing important in the first/last 6%, and protect the actual 8.33% crop too.
    for element in portrait_elements:
        if element['box'][1] < PORTRAIT_SIZE[1]*0.06 or element['box'][3] > PORTRAIT_SIZE[1]*0.94:
            raise ValueError('Contenuto importante nel 6% alto/basso del master verticale.')
    feed = portrait.crop(FEED_CROP).resize(FORMATS['feed'], Image.Resampling.LANCZOS)
    feed_elements = transform(portrait_elements, 1080/1024, 1350/1280, oy=-128*1350/1280)
    resized = portrait.resize((1080, 1620), Image.Resampling.LANCZOS)
    story = Image.new('RGBA', FORMATS['story'])
    # Extend photographic edges; do not stretch or crop the product/text.
    story.paste(resized.crop((0, 0, 1080, 150)).transpose(Image.Transpose.FLIP_TOP_BOTTOM), (0, 0))
    story.paste(resized, (0, 150))
    story.paste(resized.crop((0, 1470, 1080, 1620)).transpose(Image.Transpose.FLIP_TOP_BOTTOM), (0, 1770))
    story_elements = transform(portrait_elements, 1080/1024, 1620/1536, oy=150)
    landscape, landscape_elements, white = master(photo, headline, cta, landscape=True,
                                                 font_path=font_path, include_product=False, scene=scene)
    banner = landscape.crop(BANNER_CROP).resize(FORMATS['banner'], Image.Resampling.LANCZOS)
    banner_elements = transform(landscape_elements, 300/1229, 250/1024, ox=-154*300/1229)
    for image, elements in [(feed, feed_elements), (story, story_elements), (banner, banner_elements)]:
        product_box = next(element['box'] for element in elements if element['kind']=='product')
        composite_product(image, photo, product_box)
    if white:
        ImageDraw.Draw(banner).rectangle((0, 0, 299, 249), outline=(70, 70, 70), width=1)
    output = {}
    for kind, image, elements, source in [('feed', feed, feed_elements, PORTRAIT_SIZE),
                                         ('story', story, story_elements, PORTRAIT_SIZE),
                                         ('banner', banner, banner_elements, LANDSCAPE_SIZE)]:
        ratio = check_layout(kind, elements)
        output[kind] = {'path': directory/(kind+'.png'), 'size': FORMATS[kind], 'source_size': source,
                        'elements': elements, 'text_area_ratio': ratio}
    # Check ALL formats before writing any of them.
    for kind, image in [('feed', feed), ('story', story), ('banner', banner)]:
        image.convert('RGB').save(output[kind]['path'], format='PNG')
    return output

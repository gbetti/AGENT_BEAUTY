"""Native portrait and product-pack layouts using unmodified original assets."""
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from art_direction import ROOT, PALETTES, draw_background
from campaign import FORMATS, logo_layer, packshot_layer
from studio import check_copy_space, draw_text, shadow_and_product, validate


def checked_image(asset, path_key='path'):
    path = ROOT/asset[path_key]
    if hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
        raise ValueError('Asset creativo modificato: rivedere il manifest.')
    return path


def render_variety(product, copy, directory, scene):
    direction = scene['design']
    photos = []
    for item in direction['products']:
        path = ROOT/item['image']['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Il packshot del pack è cambiato.')
        photos.append(packshot_layer(path))
    portrait = None
    if direction['mode'] == 'model':
        with Image.open(checked_image(direction['model'])) as source:
            portrait = source.convert('RGBA')
    result = {}
    for kind, size in FORMATS.items():
        width, height = size
        image = draw_background(direction, size)
        plate = image.copy()
        elements = []
        if kind == 'feed':
            logo_top, logo_width = 75, 146
            category_top, headline_top, headline_size = 208, 260, 92
            baseline, name_top = 1090, 1180
            model_box = (475, 490, 995, 1090)
            single_x, single_limits = 285, (300, 510)
            centers = (345, 735) if len(photos) == 2 else (235, 540, 845)
            limits = (330, 570) if len(photos) == 2 else (255, 520)
        elif kind == 'story':
            logo_top, logo_width = 278, 156
            category_top, headline_top, headline_size = 421, 478, 102
            baseline, name_top = 1405, 1480
            model_box = (475, 750, 1000, 1405)
            single_x, single_limits = 285, (320, 590)
            centers = (340, 740) if len(photos) == 2 else (235, 540, 845)
            limits = (340, 600) if len(photos) == 2 else (255, 570)
        else:
            logo_top, logo_width = 16, 65
            headline_top, headline_size = 64, 25
            baseline = 209
            model_box = (195, 85, 285, 209)
            single_x, single_limits = 163, (50, 85)
            centers = (182, 253) if len(photos) == 2 else (158, 211, 264)
            limits = (62, 110) if len(photos) == 2 else (43, 98)
        logo = logo_layer(logo_width, False)
        lx = round((width-logo.width)/2)
        image.alpha_composite(logo, (lx, logo_top))
        elements.append({'kind': 'logo', 'box': [lx, logo_top, lx+logo.width, logo_top+logo.height]})
        if kind != 'banner':
            elements.append(draw_text(image, copy['category'], width/2, category_top, width*.86, 24, 'category'))
        elements.append(draw_text(image, copy['headline'], width/2 if kind != 'banner' else 17,
                                  headline_top, width*.86 if kind != 'banner' else 135,
                                  headline_size, 'headline', serif=True,
                                  align='center' if kind != 'banner' else 'left'))
        if portrait is not None:
            left, top, right, bottom = model_box
            paper, accent = PALETTES[direction['palette']]
            panel = Image.new('RGBA', (right-left, bottom-top), tuple(round((p+a)/2) for p,a in zip(paper,accent))+(255,))
            fitted = ImageOps.contain(portrait, (right-left, bottom-top), Image.Resampling.LANCZOS)
            x, y = left+(right-left-fitted.width)//2, bottom-fitted.height
            panel.alpha_composite(fitted, (x-left, y-top))
            mask = Image.new('L', panel.size)
            ImageDraw.Draw(mask).rounded_rectangle((0,0,panel.width-1,panel.height-1), radius=max(4,width*.018), fill=255)
            panel.putalpha(mask)
            image.alpha_composite(panel, (left,top))
            elements.append({'kind': 'model', 'box': list(model_box),
                             'origin': direction['model']['origin']})
            centers, limits = (single_x,), single_limits
        for index, (photo, center) in enumerate(zip(photos, centers)):
            item = shadow_and_product(image, photo, center, baseline, limits, scene.get('lighting'))
            item.update(product_id=direction['products'][index]['id'])
            elements.append(item)
        if kind != 'banner':
            elements.append(draw_text(image, copy['product_name'], width/2, name_top, width*.86, 26, 'product_name'))
        else:
            elements.append(draw_text(image, copy['cta'], 17, 214, 125, 13, 'cta', align='left'))
        ratio = validate(kind, elements)
        detail = check_copy_space(plate, elements, 3)
        result[kind] = {'path': directory/(kind+'.png'), 'size': size, 'elements': elements,
                        'text_area_ratio': ratio, 'copy_space_detail': detail,
                        'layout': 'native-'+direction['mode']+'-v1',
                        'background_placement': {'design_id': direction['id'], 'floor_start_y': round(height*.68)},
                        'product_source': product['images'][0]['source_url'], '_image': image.convert('RGB')}
    for info in result.values():
        info.pop('_image').save(info['path'], format='PNG')
    return result

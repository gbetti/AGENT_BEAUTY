"""Logo-free review posters and genuinely animated ingredient/skin patterns."""
import math
import subprocess
from PIL import Image, ImageDraw

from art_direction import PALETTES, draw_background
from campaign import FORMATS, packshot_layer
from studio import draw_text, font, shadow_and_product, validate


def lines(text, width, size, serif=True):
    result = []
    for paragraph in text.splitlines():
        line = ''
        for word in paragraph.split():
            candidate = (line+' '+word).strip()
            if font(size, serif).getlength(candidate) > width and line:
                result.append(line)
                line = word
            else:
                line = candidate
        result.append(line)
    return '\n'.join(result)


def pattern(plate, direction, phase):
    """A periodic six-second loop, below the protected headline area."""
    layer = Image.new('RGBA', plate.size)
    draw = ImageDraw.Draw(layer)
    w, h = plate.size
    accent = PALETTES[direction['palette']][1]
    step = w*.23
    for row in range(3):
        for col in range(-1, 6):
            x = col*step + (phase/(2*math.pi))*step + (row % 2)*step*.5
            y = h*(.46+.105*row)
            radius = w*(.055+.008*math.sin(phase+row))
            draw.ellipse((x-radius, y-radius*.55, x+radius, y+radius*.55), outline=accent+(150,), width=max(1, round(w*.003)))
            if direction['motif'] in ('halo', 'arch'):
                draw.ellipse((x-radius*.45,y-radius*.25,x+radius*.45,y+radius*.25), outline=accent+(100,), width=max(1,round(w*.002)))
    return Image.alpha_composite(plate, layer)


def render_editorial(product, copy, directory, scene):
    direction = scene['design']
    photo = packshot_layer(product['images'][0]['path'])
    result = {}
    for kind, size in FORMATS.items():
        w,h = size
        base = draw_background(direction, size)
        moving = copy['editorial_mode'] == 'inspiration'
        plate = pattern(base, direction, 0) if moving else base
        layer = Image.new('RGBA', size)
        # Validate contrast against the actual plate; keep a separate exact foreground for animation.
        image = plate.copy()
        elements = []
        if kind == 'feed':
            category_y, title_y, title_size, baseline, name_y = 110, 185, 87, 1045, 1120
            limits, comment_y = (470, 490), 1250
        elif kind == 'story':
            category_y, title_y, title_size, baseline, name_y = 305, 390, 94, 1310, 1390
            limits, comment_y = (500, 555), 1530
        else:
            category_y, title_y, title_size, baseline, name_y = 18, 48, 23, 217, 0
            limits, comment_y = (90, 112), 0
        def text(value, center, top, width, size, name, serif=False, align='center'):
            item = draw_text(image,value,center,top,width,size,name,serif,align)
            f = font(size,serif)
            pen = ImageDraw.Draw(layer)
            for index,line in enumerate(value.splitlines()):
                x = center-f.getlength(line)/2 if align=='center' else center
                pen.text((x,top+index*round(size*(1.12 if serif else 1.4))),line,
                         font=f,fill=(40,35,31,255),anchor='lt')
            elements.append(item)
        text(copy['category'], w/2, category_y, w*.89, 23 if kind!='banner' else 11,'category')
        title = copy.get('banner_headline',copy['headline']) if kind=='banner' else copy['headline']
        text(lines(title,w*.86 if kind!='banner' else 155,title_size), w/2 if kind!='banner' else 17,
             title_y,w*.86 if kind!='banner' else 155,title_size,'headline',True,'center' if kind!='banner' else 'left')
        center = w/2 if kind!='banner' else 236
        item = shadow_and_product(image,photo,center,baseline,limits,scene.get('lighting'))
        shadow_and_product(layer,photo,center,baseline,limits,scene.get('lighting'))
        elements.append(item)
        if kind!='banner':
            text(lines(copy['product_name'], w*.85, 29, False), w/2,name_y,w*.85,29,'product_name')
            text(copy['comment'],w/2,comment_y,w*.88,25,'comment')
            if copy.get('review_source'):
                text(copy['review_source'],w/2,title_y+len(elements[1]['text'].splitlines())*round(title_size*1.12)+36,w*.88,20,'source')
        else:
            text(copy['cta'],17,217,150,12,'cta',align='left')
        ratio=validate(kind,elements)
        path=directory/(kind+'.png')
        image.convert('RGB').save(path)
        result[kind]={'path':path,'size':size,'elements':elements,'text_area_ratio':ratio,
                      'layout':'editorial-'+copy['editorial_mode']+'-v1','product_source':product['images'][0]['source_url']}
        if kind=='story' and moving:
            render_loop(base,layer,direction,directory/'reel.mp4')
    return result


def render_loop(base, foreground, direction, output):
    command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24',
        '-s',f'{base.width}x{base.height}','-r','24','-i','pipe:0','-f','lavfi','-i',
        'anullsrc=channel_layout=stereo:sample_rate=48000','-t','6','-c:v','libx264','-preset','fast',
        '-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(output)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for frame in range(144):
            image=Image.alpha_composite(pattern(base,direction,2*math.pi*frame/144),foreground).convert('RGB')
            process.stdin.write(image.tobytes())
    finally:
        process.stdin.close()
    if process.wait()!=0:
        raise RuntimeError('Esportazione Reel fallita.')

"""Native format art direction. Original packshots and logo, no generated labels."""
from pathlib import Path
import hashlib
import math
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat
from campaign import ROOT, FORMATS, logo_layer, packshot_layer, text_contrast, rectangle_union_area

INK = (40, 35, 31)
SERIF = ROOT/'assets/fonts/CormorantGaramond.ttf'
SANS = ROOT/'assets/fonts/DejaVuSans.ttf'


def font(size, serif=False):
    f = ImageFont.truetype(str(SERIF if serif else SANS), size)
    if serif:
        f.set_variation_by_axes([500])
    return f


def draw_text(image, value, center, top, width, size, kind, serif=False, align='center'):
    # Deliberate line breaks, no automatic abbreviation or silently tiny type.
    lines = value.splitlines()
    f = font(size, serif)
    if any(f.getlength(line) > width for line in lines):
        raise ValueError(f'{kind}: testo troppo largo; rivedere il copy per questo formato.')
    draw = ImageDraw.Draw(image)
    boxes, ratios = [], []
    step = round(size*1.12 if serif else size*1.4)
    for i, line in enumerate(lines):
        x = center-f.getlength(line)/2 if align=='center' else center
        y = top+i*step
        box = draw.textbbox((x,y),line,font=f,anchor='lt')
        ratio = text_contrast(image,box,INK)
        ratios.append(ratio)
        draw.text((x,y),line,font=f,fill=INK,anchor='lt')
        boxes.append(box)
    return {'kind':kind,'text':value,'font_size':size,
            'contrast_ratio':min(ratios), 'box':[min(b[0] for b in boxes),min(b[1] for b in boxes),
                                          max(b[2] for b in boxes),max(b[3] for b in boxes)]}


def background_plate(background, scene, kind, size):
    """Crop the empty plate per format, keeping a real floor below the product."""
    if scene.get('design'):
        from art_direction import draw_background
        return draw_background(scene['design'], size), {
            'floor_start_y': round(size[1]*.68), 'light_direction': scene['lighting']['cast_direction'],
            'design_id': scene['design']['id']}
    crop = scene.get('format_crops', {}).get(kind)
    if crop:
        left, top, right, bottom = [round(v*d) for v,d in
            zip(crop, (background.width, background.height)*2)]
        plate = background.crop((left, top, right, bottom))
        scale = max(size[0]/plate.width, size[1]/plate.height)
        # Bottom alignment retains the support plane, including in a 9:16 story.
        ground = ((scene['floor_start']*background.height-top)*scale
                  - (plate.height*scale-size[1]))
        image = ImageOps.fit(plate,size,method=Image.Resampling.LANCZOS,
                             centering=(.5,1)).convert('RGBA')
        return image, {'crop':crop, 'floor_start_y':round(ground),
                       'light_direction':scene['lighting']['cast_direction']}
    # Historical scenes remain reproducible; new campaigns select studio plates.
    plate = background.crop((0,0,background.width,round(background.height*.45))) if kind=='banner' else background
    return ImageOps.fit(plate,size,method=Image.Resampling.LANCZOS).convert('RGBA'), {}


def check_copy_space(plate, elements, maximum):
    """Reject local texture behind actual lettering; contrast alone misses clutter."""
    scores = []
    for element in elements:
        if element['kind'] not in ('logo','category','headline','ingredient','product_name','cta'):
            continue
        region = plate.crop(element['box']).convert('L')
        detail = ImageChops.difference(region,region.filter(ImageFilter.GaussianBlur(2)))
        value = ImageStat.Stat(detail).mean[0]
        if value > maximum:
            raise ValueError('Fondale troppo dettagliato dietro '+element['kind'])
        scores.append(value)
    return round(max(scores,default=0),3)


def shadow_and_product(image, photo, center, baseline, limits, lighting=None):
    lighting = lighting or {'cast_direction':[.22,.07], 'color':[57,53,48]}
    # Transparent padding must never lift the bottle away from its contact shadow.
    bounds = photo.getchannel('A').point(lambda v:255 if v>=128 else 0).getbbox()
    if bounds is None:
        raise ValueError('Packshot senza sagoma opaca.')
    photo = photo.crop(bounds)
    scale=min(limits[0]/photo.width,limits[1]/photo.height)
    width,height=round(photo.width*scale),round(photo.height*scale)
    x,y=round(center-width/2),round(baseline-height)
    resized = photo.resize((width,height),Image.Resampling.LANCZOS)
    alpha = resized.getchannel('A')
    color = tuple(lighting['color'])
    dx,dy = [height*v for v in lighting['cast_direction']]
    if dy <= 0:
        raise ValueError('La luce deve proiettare l’ombra sul piano inferiore.')
    # Project the actual silhouette onto the floor, anchored at its bottom edge.
    projected = alpha.transform(image.size,Image.Transform.AFFINE,
        (1,-dx/dy,-x+dx*baseline/dy,0,-height/dy,height+height*baseline/dy),
        resample=Image.Resampling.BICUBIC)
    near = projected.filter(ImageFilter.GaussianBlur(max(.6,width*.012)))
    far = projected.filter(ImageFilter.GaussianBlur(max(1.2,width*.065)))
    # Penumbra widens and density falls with distance from the point of contact.
    gradient = Image.new('L',(1,image.height))
    gradient.putdata([round(255*max(0,min(1,(row-baseline)/dy)))
                      for row in range(image.height)])
    gradient = gradient.resize(image.size)
    cast = Image.composite(far,near,gradient)
    density = gradient.point(lambda value:round(44-29*value/255))
    cast = ImageChops.multiply(cast,density)
    layer = Image.new('RGBA',image.size,color+(0,));layer.putalpha(cast)
    image.alpha_composite(layer)
    # Derive the footprint from the bottle base, not from cap width or canvas.
    base = alpha.crop((0,round(height*.94),width,height))
    footprint = base.point(lambda value:255 if value>=128 else 0).getbbox()
    if footprint is None:
        raise ValueError('Il packshot non ha una base di appoggio verificabile.')
    left,right = x+footprint[0],x+footprint[2]
    span = right-left
    for box,opacity,blur in [
        ((left-span*.10,baseline-span*.035,right+span*.13,baseline+span*.065),26,span*.045),
        ((left+span*.04,baseline-max(.6,span*.009),right-span*.04,baseline+max(1,span*.016)),90,max(.5,span*.008))]:
        layer=Image.new('RGBA',image.size)
        ImageDraw.Draw(layer).ellipse(box,fill=color+(opacity,))
        image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
    image.alpha_composite(resized,(x,y))
    return {'kind':'product','box':[x,y,x+width,y+height],
            'shadow':{'model':'silhouette-floor-v2','baseline':baseline,
                      'footprint':[left,right],'cast_vector':[round(dx,2),round(dy,2)],
                      'color':list(color)}}


def validate(kind,elements):
    width,height=FORMATS[kind]
    y0,y1=(height*.13,height*.82) if kind=='story' else (height*.045,height*.96)
    for e in elements:
        l,t,r,b=e['box']
        if l<width*.045 or r>width*.955 or t<y0 or b>y1:
            raise ValueError(f'{kind}: {e["kind"]} fuori dalla zona utile.')
    logo=next(e for e in elements if e['kind']=='logo')
    if abs((logo['box'][0]+logo['box'][2])/2-width/2)>.5:
        raise ValueError('Logo non centrato.')
    for i,a in enumerate(elements):
        for b in elements[i+1:]:
            x1,y1,x2,y2=a['box'];u1,v1,u2,v2=b['box']
            if min(x2,u2)>max(x1,u1) and min(y2,v2)>max(y1,v1):
                raise ValueError(f'{kind}: sovrapposizione tra {a["kind"]} e {b["kind"]}.')
    if kind!='banner' and any(e['kind']=='cta' for e in elements):
        raise ValueError('Feed e story non devono contenere pulsanti o CTA.')
    return rectangle_union_area([e['box'] for e in elements if e['kind'] not in ('product', 'model')])/(width*height)


def ingredient_callouts(image, ingredients, language, kind, product_box):
    """Label the formula without drawing over the original packaging pixels."""
    if len(ingredients)!=2:
        raise ValueError('Servono esattamente due ingredienti verificati.')
    l,t,r,b=product_box
    draw=ImageDraw.Draw(image)
    elements=[]
    for index,ingredient in enumerate(ingredients):
        if kind=='banner':
            label=draw_text(image,ingredient['short'][language],17,146+index*28,130,12,'ingredient',align='left')
            y=(label['box'][1]+label['box'][3])/2
            start=(label['box'][2]+8,y);end=(l-5,y-9)
            if start[0]+10>=end[0]: raise ValueError('Richiamo ingrediente troppo largo nel banner.')
            thickness,head=1,4
        else:
            left=index==0
            y=t+(b-t)*(.35 if left else .73)
            center=164 if left else 916
            label=draw_text(image,ingredient['label'][language],center,y-68,220,28,'ingredient')
            start=(label['box'][2]+10,y-15) if left else (label['box'][0]-10,y-15)
            end=(l-7,y+15) if left else (r+7,y+15)
            if (left and start[0]>=end[0]) or (not left and start[0]<=end[0]):
                raise ValueError('Spazio insufficiente per la freccia ingrediente.')
            thickness,head=2,9
        draw.line((start,end),fill=INK,width=thickness)
        angle=math.atan2(end[1]-start[1],end[0]-start[0])
        wings=[(end[0]-head*math.cos(angle+a),end[1]-head*math.sin(angle+a)) for a in (-.48,.48)]
        draw.line((wings[0],end,wings[1]),fill=INK,width=thickness)
        points=[start,end]+wings
        elements.append({**label,'ingredient_id':ingredient['id']})
        elements.append({'kind':'arrow','ingredient_id':ingredient['id'],'start':start,'end':end,
                         'box':[min(p[0] for p in points),min(p[1] for p in points),
                                max(p[0] for p in points),max(p[1] for p in points)]})
    return elements


def render_campaign(product, copy, directory, scene):
    if scene.get('design', {}).get('mode') in ('model', 'pack'):
        from variety_studio import render_variety
        return render_variety(product, copy, directory, scene)
    path=ROOT/scene['path']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=scene['sha256']:
        raise ValueError('Il fondale è cambiato: verificare e aggiornare il manifest.')
    photo=packshot_layer(product['images'][0]['path'])
    with Image.open(path) as original:
        background=original.convert('RGB')
    result={}
    for kind,size in FORMATS.items():
        width,height=size
        image, placement = background_plate(background,scene,kind,size)
        plate = image.copy()
        if kind=='feed':
            logo_top,logo_width=75,146
            category_top,headline_top,headline_size=208,260,100
            product_x,baseline,limits=540,1057,(490,530)
            name_top,name_size=1165,28
            if photo.width/photo.height < .55:
                baseline,limits=1100,(400,610)
        elif kind=='story':
            logo_top,logo_width=278,156
            category_top,headline_top,headline_size=421,478,108
            product_x,baseline,limits=540,1380,(520,600)
            name_top,name_size=1480,28
            if photo.width/photo.height < .55:
                baseline,limits=1430,(450,700)
        else:
            logo_top,logo_width=16,65
            headline_top,headline_size=(59,26) if copy.get('ingredients') else (81,26)
            product_x,baseline,limits=222,207,(122,130)
        elements=[]
        logo=logo_layer(logo_width,False)
        image.alpha_composite(logo,(round((width-logo.width)/2),logo_top))
        elements.append({'kind':'logo','box':[(width-logo.width)/2,logo_top,(width+logo.width)/2,logo_top+logo.height]})
        if kind!='banner':
            elements.append(draw_text(image,copy['category'],width/2,category_top,width*.85,26,'category'))
        elements.append(draw_text(image,copy['headline'],width/2 if kind!='banner' else 17,
                                  headline_top,width*.86 if kind!='banner' else 143,
                                  headline_size,'headline',serif=True,align='center' if kind!='banner' else 'left'))
        if placement and baseline < placement['floor_start_y']+height*.025:
            raise ValueError('Il prodotto non appoggia sul piano del fondale.')
        product_element=shadow_and_product(image,photo,product_x,baseline,limits,scene.get('lighting'))
        elements.append(product_element)
        if copy.get('ingredients'):
            elements.extend(ingredient_callouts(image,copy['ingredients'],copy['language'],kind,product_element['box']))
        if kind!='banner':
            elements.append(draw_text(image,copy['product_name'],width/2,name_top,width*.86,name_size,'product_name'))
        else:
            elements.append(draw_text(image,copy['cta'],17,211,135,14,'cta',align='left'))
            box=elements[-1]['box'];ImageDraw.Draw(image).line((box[0],box[3]+4,box[2],box[3]+4),fill=INK,width=1)
        ratio=validate(kind,elements)
        detail = check_copy_space(plate,elements,scene.get('max_copy_detail',255))
        target=directory/(kind+'.png')
        result[kind]={'path':target,'size':size,'elements':elements,'text_area_ratio':ratio,
                      'layout':'native-editorial-v2','background_placement':placement,
                      'copy_space_detail':detail,'product_source':product['images'][0]['source_url']}
        # Persist only after all three have passed validation.
        result[kind]['_image']=image.convert('RGB')
    for info in result.values():
        info.pop('_image').save(info['path'],format='PNG')
    return result

"""Native format art direction. Original packshots and logo, no generated labels."""
from pathlib import Path
import hashlib
import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
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
    boxes = []
    step = round(size*1.02 if serif else size*1.4)
    for i, line in enumerate(lines):
        x = center-f.getlength(line)/2 if align=='center' else center
        y = top+i*step
        box = draw.textbbox((x,y),line,font=f,anchor='lt')
        ratio = text_contrast(image,box,INK)
        draw.text((x,y),line,font=f,fill=INK,anchor='lt')
        boxes.append(box)
    return {'kind':kind,'text':value,'font_size':size,
            'contrast_ratio':ratio, 'box':[min(b[0] for b in boxes),min(b[1] for b in boxes),
                                          max(b[2] for b in boxes),max(b[3] for b in boxes)]}


def shadow_and_product(image, photo, center, baseline, limits):
    scale=min(limits[0]/photo.width,limits[1]/photo.height)
    width,height=round(photo.width*scale),round(photo.height*scale)
    x,y=round(center-width/2),round(baseline-height)
    # Two physically distinct layers: contact occlusion and diffuse cast shadow.
    for box, opacity, blur in [((x+width*.06,baseline-height*.025,x+width*1.06,baseline+height*.075),38,width*.055),
                               ((x+width*.1,baseline-height*.014,x+width*.9,baseline+height*.019),100,width*.012)]:
        layer=Image.new('RGBA',image.size)
        ImageDraw.Draw(layer).ellipse(box,fill=(67,56,44,opacity))
        image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
    image.alpha_composite(photo.resize((width,height),Image.Resampling.LANCZOS),(x,y))
    return {'kind':'product','box':[x,y,x+width,y+height]}


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
    return rectangle_union_area([e['box'] for e in elements if e['kind']!='product'])/(width*height)


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
    path=ROOT/scene['path']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=scene['sha256']:
        raise ValueError('Il fondale è cambiato: verificare e aggiornare il manifest.')
    photo=packshot_layer(product['images'][0]['path'])
    with Image.open(path) as original:
        background=original.convert('RGB')
    result={}
    for kind,size in FORMATS.items():
        width,height=size
        plate = background.crop((0,0,background.width,round(background.height*.45))) if kind=='banner' else background
        image=ImageOps.fit(plate,size,method=Image.Resampling.LANCZOS,centering=(.5,.5)).convert('RGBA')
        if kind=='feed':
            logo_top,logo_width=75,146
            category_top,headline_top,headline_size=208,260,100
            product_x,baseline,limits=540,1057,(490,530)
            name_top,name_size=1165,28
        elif kind=='story':
            logo_top,logo_width=278,156
            category_top,headline_top,headline_size=421,478,108
            product_x,baseline,limits=540,1380,(520,600)
            name_top,name_size=1480,28
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
        product_element=shadow_and_product(image,photo,product_x,baseline,limits)
        elements.append(product_element)
        if copy.get('ingredients'):
            elements.extend(ingredient_callouts(image,copy['ingredients'],copy['language'],kind,product_element['box']))
        if kind!='banner':
            elements.append(draw_text(image,copy['product_name'],width/2,name_top,width*.86,name_size,'product_name'))
        else:
            elements.append(draw_text(image,copy['cta'],17,211,135,14,'cta',align='left'))
            box=elements[-1]['box'];ImageDraw.Draw(image).line((box[0],box[3]+4,box[2],box[3]+4),fill=INK,width=1)
        ratio=validate(kind,elements)
        target=directory/(kind+'.png')
        result[kind]={'path':target,'size':size,'elements':elements,'text_area_ratio':ratio,
                      'layout':'native-editorial-v1','product_source':product['images'][0]['source_url']}
        # Persist only after all three have passed validation.
        result[kind]['_image']=image.convert('RGB')
    for info in result.values():
        info.pop('_image').save(info['path'],format='PNG')
    return result

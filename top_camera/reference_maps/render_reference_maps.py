"""Render editable vector reference diagrams and PNG previews (design only)."""
from pathlib import Path
from html import escape
import json
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = 'C:/Windows/Fonts/msyh.ttc'
BOLD = 'C:/Windows/Fonts/msyhbd.ttc'
INK, MUTED, GREEN, BLUE = '#193847', '#607583', '#16846b', '#2876bd'


def render(mode):
    image = Image.new('RGB', (900, 1160), '#f4f7fa')
    draw = ImageDraw.Draw(image)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1160" viewBox="0 0 900 1160">',
           '<rect width="900" height="1160" fill="#f4f7fa"/>']

    def rect(box, fill, outline=None, radius=0):
        draw.rounded_rectangle(box, radius, fill, outline, width=2)
        x, y, r, b = box
        svg.append(f'<rect x="{x}" y="{y}" width="{r-x}" height="{b-y}" rx="{radius}" fill="{fill}" stroke="{outline or "none"}" stroke-width="2"/>')

    def line(points, color, width):
        draw.line(points, fill=color, width=width, joint='curve')
        for x, y in points:
            draw.ellipse((x-width/2,y-width/2,x+width/2,y+width/2),fill=color)
        svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')

    def ellipse(box, fill, outline=None):
        draw.ellipse(box,fill,outline,width=2)
        x,y,r,b=box
        svg.append(f'<ellipse cx="{(x+r)/2}" cy="{(y+b)/2}" rx="{(r-x)/2}" ry="{(b-y)/2}" fill="{fill}" stroke="{outline or "none"}" stroke-width="2"/>')

    def polygon(points, fill):
        draw.polygon(points,fill)
        svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in points)}" fill="{fill}"/>')

    def text(x,y,value,size=21,color=INK,bold=False):
        font=ImageFont.truetype(BOLD if bold else FONT,size)
        draw.text((x,y),value,font=font,fill=color)
        svg.append(f'<text x="{x}" y="{y}" dominant-baseline="text-before-edge" font-family="Microsoft YaHei,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(value)}</text>')

    sides = mode == 'arms_at_sides'
    title = '01  Arms at sides' if sides else '02  Arms overhead'
    subtitle = 'Common positioning for routine head CT' if sides else 'Common positioning for routine chest / abdomen / pelvis CT'
    text(42,30,'TOP CAMERA  /  REFERENCE MAP DESIGN v1',18,MUTED,True)
    text(42,66,title,34,INK,True)
    text(42,118,subtitle,19,MUTED)
    rect((30,167,870,1030),'#ffffff',radius=22)
    rect((68,190,386,1006),'#eaf0f5','#bccbd5',28)
    text(174,169,'HEAD ↑',17,MUTED)
    for y in range(238,982,18):
        line([(227,y),(227,y+7)],'#b9c9d4',2)
    # Head support is an aid, not a required exact contour match.
    rect((167,288,287,411),'#d8e3ed',radius=24)
    if sides:
        arms=[[(160,430),(140,539),(148,655)],[(294,430),(314,539),(306,655)]]
        for pts in arms: line(pts,'#d7f1e7',70)
    else:
        arms=[[(160,430),(134,299),(173,236)],[(294,430),(320,299),(281,236)]]
        for pts in arms: line(pts,'#d7f1e7',72)
    # Neutral supine silhouette with schematic, non-patient-specific anatomy.
    ellipse((185,304,269,397),'#c7d7e5')
    line([(227,391),(227,431)],'#c7d7e5',34)
    polygon([(162,424),(292,424),(284,520),(269,592),(281,670),
             (173,670),(185,592),(170,520)],'#c7d7e5')
    legs=[[(200,654),(197,793),(193,942)],[(254,654),(257,793),(261,942)]]
    for pts in legs: line(pts,'#c7d7e5',47)
    for x in (190,264): ellipse((x-22,927,x+22,974),'#c7d7e5')
    for pts in arms: line(pts,'#a8c4db',29)
    for pts in arms+legs:
        line(pts,BLUE,4)
        for x,y in pts: ellipse((x-6,y-6,x+6,y+6),'#ffffff',BLUE)
    line([(160,430),(294,430)],BLUE,3)
    line([(200,654),(254,654)],BLUE,3)
    ellipse((220,348,234,362),'#ffffff',BLUE)
    text(166,976,'FEET ↓',17,MUTED)

    x=422
    def block(y,title,lines):
        text(x,y,title,23,INK,True)
        for i,t in enumerate(lines): text(x,y+40+i*31,t,18,MUTED)
    if sides:
        block(207,'Target position',['Lie supine with the head supported.','Rest both arms alongside the torso.','Hands beside the same-side hip or thigh.'])
        block(370,'Overhead camera checks',['Align head, shoulders and pelvis to bed.','Keep each elbow and wrist on its side.','No arms across torso or above the head.'])
        block(533,'Allow natural variation',['Allow relaxed elbows and a small gap.','Rest legs naturally; supports are allowed.','Do not require a silhouette match.'])
        block(696,'Technologist confirmation',['Head / neck angle and head support.','Vertical centering and lens avoidance.','Supports, comfort and exam protocol.'])
        block(859,'Patient instruction',['Lie on your back with both arms','at your sides. Keep your head still.'])
    else:
        block(207,'Target position',['Lie supine; raise both arms headward.','Place both hands beyond the head.','Use suitable arm supports.'])
        block(370,'Overhead camera checks',['Elbows headward; arms clear of torso.','Both wrists headward of the shoulders.','No lowered arms over chest or abdomen.'])
        block(533,'Allow natural variation',['Bent elbows are allowed.','Hands need not touch or grip a fixture.','Allow comfortable minor asymmetry.'])
        block(696,'Technologist confirmation',['Arm mobility and shoulder / arm injury.','Arm support, lines and gantry clearance.','Position before body scout per protocol.'])
        block(859,'Patient instruction',['If comfortable, raise both arms above','your head. Rest them and keep still.'])
    rect((42,1050,60,1068),'#d7f1e7',GREEN,4)
    text(71,1047,'Green: illustrative target zones. Blue: landmarks and skeleton.',17,MUTED)
    text(42,1081,'Supine top view, head at top. Not scan coverage or a pixel-matching template.',17,MUTED)
    text(42,1114,'Research design. Zone widths are not clinical thresholds; follow the exam protocol.',17,MUTED)
    svg.append('</svg>')
    image.save(ROOT/f'{mode}.png')
    (ROOT/f'{mode}.svg').write_text('\n'.join(svg),encoding='utf-8')
    return image, arms


if __name__ == '__main__':
    results=[render(m) for m in ['arms_at_sides','arms_overhead']]
    combined=Image.new('RGB',(1800,1160))
    for i,(im,_) in enumerate(results):combined.paste(im,(i*900,0))
    combined.save(ROOT/'reference_maps_comparison.png')
    # Illustration coordinates only. Never load these as acceptance thresholds.
    data={'version':1,'status':'design_only_not_connected_to_detector',
          'coordinate_system':'illustration_pixels_900x1160_head_at_top',
          'clinical_thresholds':None,
          'presets':{mode:{'required_arm_mode':mode,'illustrative_arm_polylines':arms}
                     for mode,(_,arms) in zip(['arms_at_sides','arms_overhead'],results)}}
    (ROOT/'reference_maps.design.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

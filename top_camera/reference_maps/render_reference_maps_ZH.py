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
    title = '01  双臂置于身体两侧' if sides else '02  双臂举过头顶'
    subtitle = '头部 CT 常用摆位 / ARMS AT SIDES' if sides else '常规胸腹盆 CT 常用摆位 / ARMS OVERHEAD'
    text(42,30,'TOP CAMERA  /  参考图设计 v1',18,MUTED,True)
    text(42,66,title,34,INK,True)
    text(42,118,subtitle,20,MUTED)
    rect((30,167,870,1030),'#ffffff',radius=22)
    rect((68,190,386,1006),'#eaf0f5','#bccbd5',28)
    text(174,169,'床头 ↑',17,MUTED)
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
    text(166,976,'床尾方向 ↓',17,MUTED)

    x=422
    def block(y,title,lines):
        text(x,y,title,23,INK,True)
        for i,t in enumerate(lines): text(x,y+40+i*31,t,20,MUTED)
    if sides:
        block(207,'目标姿势',['仰卧，头部置于头托内。','双臂自然放在躯干两侧，','双手位于同侧髋部或大腿旁。'])
        block(370,'顶置相机关注',['头、肩和骨盆沿床长轴排列。','双肘及双腕保持在同侧。','手臂不跨胸腹、不举过头部。'])
        block(533,'允许自然差异',['手臂可舒适微屈，无需贴紧。','双腿自然放置，可使用支撑。','不要求身体与示意轮廓重合。'])
        block(696,'仍需技师确认',['头颈角度及头托是否合适。','扫描中心高度与眼晶状体避让。','支撑、舒适度和具体检查方案。'])
        block(859,'患者提示语',['请平躺，双手自然放在身体','两侧，头部保持不动。'])
    else:
        block(207,'目标姿势',['仰卧，两臂同时向头端抬起。','双手位于头顶以远的头端区域。','使用合适的手臂支撑。'])
        block(370,'顶置相机关注',['双肘向头端，手臂离开躯干。','双腕位于各自肩部的头端侧。','胸腹部不被放下的手臂覆盖。'])
        block(533,'允许自然差异',['肘部可弯曲，不要求完全伸直。','不要求双手相碰或抓住固定点。','左右可有舒适的小幅差异。'])
        block(696,'仍需技师确认',['患者能否举臂及有无肩臂损伤。','手臂支撑、管路及机架间隙。','按方案在躯干定位像前摆好。'])
        block(859,'患者提示语',['请在能够舒适完成时，将双臂','举过头顶，放好后保持不动。'])
    rect((42,1050,60,1068),'#d7f1e7',GREEN,4)
    text(71,1047,'绿色：目标区域示意；蓝色：关键点与骨架',18,MUTED)
    text(42,1081,'仰卧顶视图，头端向上；不是扫描范围或像素重合模板。',18,MUTED)
    text(42,1114,'研究设计图；区域宽度非临床阈值，具体摆位由检查方案确定。',18,MUTED)
    svg.append('</svg>')
    image.save(ROOT/f'{mode}_ZH.png')
    (ROOT/f'{mode}_ZH.svg').write_text('\n'.join(svg),encoding='utf-8')
    return image, arms


if __name__ == '__main__':
    results=[render(m) for m in ['arms_at_sides','arms_overhead']]
    combined=Image.new('RGB',(1800,1160))
    for i,(im,_) in enumerate(results):combined.paste(im,(i*900,0))
    combined.save(ROOT/'reference_maps_comparison_ZH.png')
    # Illustration coordinates only. Never load these as acceptance thresholds.
    data={'version':1,'status':'design_only_not_connected_to_detector',
          'coordinate_system':'illustration_pixels_900x1160_head_at_top',
          'clinical_thresholds':None,
          'presets':{mode:{'required_arm_mode':mode,'illustrative_arm_polylines':arms}
                     for mode,(_,arms) in zip(['arms_at_sides','arms_overhead'],results)}}
    (ROOT/'reference_maps.design_ZH.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

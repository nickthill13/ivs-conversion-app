"""Run once to generate icon.png and icon.ico"""
from PIL import Image, ImageDraw

SIZE = 512

def rounded_rect(draw, xy, r, fill):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0+r, y0, x1-r, y1], fill=fill)
    draw.rectangle([x0, y0+r, x1, y1-r], fill=fill)
    for cx, cy in [(x0,y0),(x1-2*r,y0),(x0,y1-2*r),(x1-2*r,y1-2*r)]:
        draw.ellipse([cx, cy, cx+2*r, cy+2*r], fill=fill)

img = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
draw = ImageDraw.Draw(img)

# Background
rounded_rect(draw, [0,0,SIZE,SIZE], 80, "#1E293B")

# Grid lines
for x in range(0, SIZE, 40):
    draw.line([(x,0),(x,SIZE)], fill=(255,255,255,18), width=1)
for y in range(0, SIZE, 40):
    draw.line([(0,y),(SIZE,y)], fill=(255,255,255,18), width=1)

# Clip to rounded rect
mask = Image.new("L", (SIZE,SIZE), 0)
rounded_rect(ImageDraw.Draw(mask), [0,0,SIZE,SIZE], 80, 255)
img.putalpha(mask)
draw = ImageDraw.Draw(img)

# Document
dx0,dy0,dx1,dy1 = 96, 72, 336, 408
rounded_rect(draw, [dx0,dy0,dx1,dy1], 20, "#263347")
draw.rounded_rectangle([dx0,dy0,dx1,dy1], radius=20, outline="#334155", width=2)

# Folded corner
fold = 52
draw.polygon([(dx1-fold,dy0),(dx1,dy0+fold),(dx1-fold,dy0+fold)], fill="#1E293B")
draw.line([(dx1-fold,dy0),(dx1-fold,dy0+fold),(dx1,dy0+fold)], fill="#334155", width=2)

# Blueprint lines
for i, y in enumerate(range(dy0+70, dy1-30, 36)):
    w = (dx1-dx0-48) if i % 3 != 1 else (dx1-dx0-80)
    draw.line([(dx0+24, y),(dx0+24+w, y)], fill=(37,99,235,200), width=4)

# Arrow circle
cx, cy, cr = 368, 368, 88
draw.ellipse([cx-cr+5,cy-cr+5,cx+cr+5,cy+cr+5], fill=(0,0,0,60))
draw.ellipse([cx-cr,cy-cr,cx+cr,cy+cr], fill="#2563EB")
draw.line([(cx-28,cy+28),(cx+22,cy-22)], fill="white", width=14)
draw.polygon([(cx+28,cy-28),(cx+2,cy-28),(cx+28,cy-2)], fill="white")

img.save("icon.png")
sizes = [16,32,48,64,128,256]
imgs = [img.resize((s,s), Image.LANCZOS) for s in sizes]
imgs[0].save("icon.ico", format="ICO", append_images=imgs[1:],
             sizes=[(s,s) for s in sizes])
print("icon.png and icon.ico saved.")

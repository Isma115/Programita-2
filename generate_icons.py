import os
import math
from PIL import Image, ImageDraw

ICON_SIZE = (64, 64) 
COLOR = (255, 255, 255, 255) # White
TRANSPARENT = (0, 0, 0, 0)
icons_dir = "assets/icons"
os.makedirs(icons_dir, exist_ok=True)

def create_icon(name, draw_func):
    img = Image.new("RGBA", ICON_SIZE, TRANSPARENT)
    draw = ImageDraw.Draw(img)
    try:
        draw_func(draw)
        img.save(os.path.join(icons_dir, f"{name}.png"))
        print(f"Generated {name}.png")
    except Exception as e:
        print(f"Error generating {name}: {e}")

def draw_folder(d):
    d.polygon([(4, 10), (24, 10), (28, 16), (60, 16), (60, 54), (4, 54)], fill=COLOR)
    d.line([(4, 24), (60, 24)], fill=TRANSPARENT, width=4)

def draw_file_plus(d):
    d.polygon([(12, 4), (40, 4), (52, 16), (52, 60), (12, 60)], fill=COLOR)
    cx, cy = 32, 34
    S = 18 
    W = 6 
    d.rectangle([cx - S//2, cy - W//2, cx + S//2, cy + W//2], fill=TRANSPARENT)
    d.rectangle([cx - W//2, cy - S//2, cx + W//2, cy + S//2], fill=TRANSPARENT)

def draw_save(d):
    # Improved Floppy Disk
    # Main Body with cut corner
    # Top-Right corner cut: from (56,8) to (56,16) is straight, but cut is (48,8) to (56,16)
    d.polygon([(8, 8), (48, 8), (56, 16), (56, 56), (8, 56)], fill=COLOR)
    
    # Top Shutter (Metal part)
    # Usually a rectangle near the top
    d.rectangle([20, 8, 44, 22], fill=TRANSPARENT)
    # Detail inside shutter (the slider slot)
    # d.rectangle([28, 8, 32, 18], fill=COLOR) # Would need to be color to show in transparency? No.
    # If the shutter is transparent (hole), we can't draw inside it with COLOR (it would just fill it back).
    # So we leave the shutter as a clean hole.

    # Bottom Label Area
    # Large rectangle at the bottom
    d.rectangle([16, 34, 48, 56], fill=TRANSPARENT)
    
    # To make it look more like the icon, maybe leave a bar at the bottom?
    # No, typically the label sits on the bottom edge.
    # But wait, if I cut to 56, and body ends at 56, it's open at the bottom.
    # Let's check Material Design "save" again. 
    # It has a solid bottom edge. The label box is *inside*.
    
    # Let's adjust measurements so there is a white border at the bottom.
    # Body goes to 56.
    # Label cutout goes to 52?
    
    # Retrying:
    # Body
    d.polygon([(6, 6), (46, 6), (58, 18), (58, 58), (6, 58)], fill=COLOR)
    
    # Top Shutter (Hole)
    d.rectangle([18, 6, 46, 22], fill=TRANSPARENT)
    
    # Bottom Label (Hole)
    d.rectangle([14, 34, 50, 50], fill=TRANSPARENT) # Surrounded by white

def draw_delete(d):
    d.rectangle([26, 4, 38, 10], fill=COLOR)
    d.rectangle([10, 10, 54, 18], fill=COLOR)
    d.polygon([(14, 20), (50, 20), (46, 60), (18, 60)], fill=COLOR)
    d.line([(24, 28), (22, 52)], fill=TRANSPARENT, width=4)
    d.line([(32, 28), (32, 52)], fill=TRANSPARENT, width=4)
    d.line([(40, 28), (42, 52)], fill=TRANSPARENT, width=4)

def draw_edit(d):
    d.polygon([(46, 6), (58, 18), (20, 56), (8, 44)], fill=COLOR)
    d.polygon([(8, 44), (20, 56), (4, 60)], fill=COLOR)
    d.line([(42, 14), (50, 22)], fill=TRANSPARENT, width=4)

def draw_view_eye(d):
    d.ellipse([4, 16, 60, 48], fill=COLOR)
    d.ellipse([12, 22, 52, 42], fill=TRANSPARENT)
    d.ellipse([26, 26, 38, 38], fill=COLOR)

def draw_theme_dark(d):
    d.ellipse([8, 8, 56, 56], fill=COLOR)
    d.ellipse([20, 4, 68, 52], fill=TRANSPARENT)

def draw_theme_light(d):
    cx, cy = 32, 32
    R_inner = 14
    R_outer = 26
    d.ellipse([cx-R_inner, cy-R_inner, cx+R_inner, cy+R_inner], fill=COLOR)
    for i in range(8):
        angle = i * (360/8)
        rad = math.radians(angle)
        x1 = cx + math.cos(rad) * (R_inner + 4)
        y1 = cy + math.sin(rad) * (R_inner + 4)
        x2 = cx + math.cos(rad) * R_outer
        y2 = cy + math.sin(rad) * R_outer
        d.line([(x1, y1), (x2, y2)], fill=COLOR, width=6)

if __name__ == "__main__":
    create_icon("folder_open", draw_folder)
    create_icon("file_plus", draw_file_plus)
    create_icon("save", draw_save)
    create_icon("delete", draw_delete)
    create_icon("edit", draw_edit)
    create_icon("view", draw_view_eye)
    create_icon("moon", draw_theme_dark)
    create_icon("sun", draw_theme_light)

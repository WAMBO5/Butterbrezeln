"""Generate fake exploded-view drawings (grayscale line art) for the test cases in fake-cases/.

Usage: python testdata/make_exploded_views.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "fake-cases"
W, H = 1800, 1400
DEPTH = (38, -26)  # extrusion vector for the pseudo-3D look
AXIS = (1.0, -0.42)  # direction parts are exploded along


def font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def rounded_rect(w, h, r, n=6):
    """Polygon points of a rounded rectangle centred at the origin."""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0),
                       (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def swoosh(w, h):
    """Headlamp-like swept outline."""
    return [(-w / 2, h / 2), (-w / 2 + 20, -h / 6), (-w / 4, -h / 2), (w / 3, -h / 2 + 10),
            (w / 2, -h / 4), (w / 2 - 10, h / 4), (w / 3, h / 2)]


def ellipse(w, h, n=40):
    return [(w / 2 * math.cos(2 * math.pi * i / n), h / 2 * math.sin(2 * math.pi * i / n)) for i in range(n)]


class Sheet:
    def __init__(self, title, part_no, table_top=False):
        self.img = Image.new("L", (W, H), 255)
        self.d = ImageDraw.Draw(self.img)
        self.title, self.part_no, self.table_top = title, part_no, table_top
        self.parts = []
        self.balloons = []

    def solid(self, cx, cy, profile, depth=DEPTH, width=3):
        """Extruded profile: back face, connecting edges on the silhouette, front face."""
        dx, dy = depth
        front = [(cx + x, cy + y) for x, y in profile]
        back = [(x + dx, y + dy) for x, y in front]
        self.d.polygon(back, fill=255, outline=0)
        self.d.line(back + back[:1], fill=0, width=width - 1)
        # connect the extreme points so the solid reads as 3D
        for key in (lambda p: p[0] + p[1], lambda p: p[0] - p[1], lambda p: -p[0] + p[1], lambda p: -p[0] - p[1]):
            i = max(range(len(front)), key=lambda k: key(front[k]))
            self.d.line([front[i], back[i]], fill=0, width=width - 1)
        self.d.polygon(front, fill=255)
        self.d.line(front + front[:1], fill=0, width=width)
        return front

    def outline(self, cx, cy, profile, width=2):
        pts = [(cx + x, cy + y) for x, y in profile]
        self.d.line(pts + pts[:1], fill=0, width=width)

    def circle(self, cx, cy, r, width=2):
        self.d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=width)

    def hatch(self, x0, y0, x1, y1, step=14):
        for k in range(int(x0) - int(y1 - y0), int(x1), step):
            a, b = (max(k, x0), y1 - (max(k, x0) - k)), (min(k + (y1 - y0), x1), y1 - (min(k + (y1 - y0), x1) - k))
            self.d.line([a, b], fill=0, width=1)

    def dashed(self, p0, p1, dash=(28, 8, 4, 8)):
        """Dash-dot centre line."""
        length = math.dist(p0, p1)
        ux, uy = (p1[0] - p0[0]) / length, (p1[1] - p0[1]) / length
        t, i = 0.0, 0
        while t < length:
            seg = dash[i % len(dash)]
            if i % 2 == 0:
                e = min(t + seg, length)
                self.d.line([(p0[0] + ux * t, p0[1] + uy * t), (p0[0] + ux * e, p0[1] + uy * e)], fill=0, width=1)
            t += seg
            i += 1

    def balloon(self, anchor, label, offset):
        """Queue a numbered balloon; drawn in frame() so later parts cannot cover it."""
        self.parts.append(label)
        self.balloons.append((len(self.parts), anchor, offset))

    def _draw_balloon(self, n, anchor, offset):
        bx, by = anchor[0] + offset[0], anchor[1] + offset[1]
        self.d.line([anchor, (bx, by)], fill=0, width=1)
        self.d.ellipse([anchor[0] - 4, anchor[1] - 4, anchor[0] + 4, anchor[1] + 4], fill=0)
        r = 24
        self.d.ellipse([bx - r, by - r, bx + r, by + r], fill=255, outline=0, width=2)
        self.d.text((bx, by), str(n), fill=0, font=font(24), anchor="mm")

    def frame(self):
        d = self.d
        for b in self.balloons:
            self._draw_balloon(*b)
        d.rectangle([20, 20, W - 20, H - 20], outline=0, width=3)
        # parts list
        f = font(20)
        rh = 30
        x0, y0 = 40, 40 if self.table_top else H - 60 - rh_of(len(self.parts))
        d.rectangle([x0, y0, x0 + 520, y0 + rh * (len(self.parts) + 1)], outline=0, width=2)
        d.text((x0 + 12, y0 + 6), "POS  DESCRIPTION", fill=0, font=f)
        for i, name in enumerate(self.parts, 1):
            y = y0 + rh * i
            d.line([(x0, y), (x0 + 520, y)], fill=0, width=1)
            d.text((x0 + 20, y + 5), str(i), fill=0, font=f)
            d.text((x0 + 80, y + 5), name, fill=0, font=f)
        d.line([(x0 + 64, y0), (x0 + 64, y0 + rh * (len(self.parts) + 1))], fill=0, width=1)
        # title block
        tx, ty = W - 640, H - 170
        d.rectangle([tx, ty, W - 40, H - 40], outline=0, width=2)
        d.line([(tx, ty + 60), (W - 40, ty + 60)], fill=0, width=1)
        d.text((tx + 15, ty + 15), self.title, fill=0, font=font(30))
        d.text((tx + 15, ty + 75), f"DWG NO. {self.part_no}   EXPLODED VIEW", fill=0, font=f)
        d.text((tx + 15, ty + 100), "SCALE NTS   SHEET 1/1   FAKE - FOR TESTING ONLY", fill=0, font=f)

    def save(self, folder):
        self.frame()
        path = OUT / folder / "exploded_view.png"
        self.img.save(path)
        print(path)


def rh_of(n):
    return 30 * (n + 1)


def stations(start, spacing, n):
    return [(start[0] + AXIS[0] * spacing * i, start[1] + AXIS[1] * spacing * i) for i in range(n)]


def headlamp():
    s = Sheet("FRONT HEADLAMP LED", "FK-HL-0001", table_top=True)
    pos = stations((230, 1000), 175, 7)
    s.dashed((120, pos[0][1] - AXIS[1] * 140), (pos[-1][0] + 220, pos[-1][1] + AXIS[1] * 220))

    # 1 heat sink + ECU (rearmost)
    x, y = pos[0]
    f = s.solid(x, y, rounded_rect(150, 190, 8), depth=(30, -20))
    for k in range(-60, 70, 20):
        s.d.line([(x + k, y - 85), (x + k, y + 85)], fill=0, width=2)
    s.balloon((x, y + 95), "Heat sink with LED driver ECU", (-60, 120))
    # 2 housing
    x, y = pos[1]
    s.solid(x + 60, y, swoosh(420, 300), depth=(60, -40), width=4)
    s.circle(x + 20, y + 20, 55)
    s.circle(x + 140, y - 10, 70)
    s.balloon((x - 120, y + 120), "Housing", (-40, 170))
    # 3 levelling actuator
    x, y = pos[1][0] - 40, pos[1][1] - 260
    s.solid(x, y, rounded_rect(90, 60, 10))
    s.d.line([(x + 45, y), (x + 120, y + 40)], fill=0, width=4)
    s.balloon((x - 45, y), "Levelling actuator", (-90, -60))
    # 4 passing beam projector
    x, y = pos[3]
    s.solid(x - 40, y + 20, ellipse(110, 110), depth=(55, -38))
    s.circle(x - 40, y + 20, 38)
    s.circle(x - 40, y + 20, 18)
    s.balloon((x - 40, y + 75), "Passing beam projector module", (-30, 200))
    # 5 driving beam reflector
    s.solid(x + 110, y - 30, rounded_rect(130, 120, 40))
    for r in (50, 35, 20):
        s.outline(x + 110, y - 30, ellipse(r * 2.2, r * 2))
    s.balloon((x + 160, y - 70), "Driving beam reflector module", (60, -150))
    # 6 DRL light guide
    x, y = pos[4]
    guide = [(-200, 120), (-170, 0), (-60, -110), (150, -120), (190, -90), (150, -95), (-50, -85), (-150, 10), (-180, 120)]
    s.solid(x + 40, y, guide, depth=(20, -14))
    s.balloon((x + 190, y - 120), "DRL / position light guide", (-60, -170))
    # 7 bezel
    x, y = pos[5]
    s.solid(x + 60, y, swoosh(400, 280), depth=(12, -8))
    s.outline(x + 20, y + 20, ellipse(130, 130))
    s.outline(x + 140, y - 10, ellipse(150, 140))
    s.balloon((x + 240, y + 60), "Bezel", (110, 80))
    # 8 gasket (thin ring between bezel and lens)
    x, y = pos[6][0] - 30, pos[6][1] + 30
    s.outline(x + 60, y, swoosh(420, 300), width=3)
    s.outline(x + 66, y - 4, swoosh(404, 286), width=1)
    s.balloon((x - 140, y + 140), "Seal / gasket", (-90, 120))
    # 9 outer lens
    x, y = pos[6][0] + 150, pos[6][1] - 70
    s.solid(x + 60, y, swoosh(440, 310), depth=(14, -9), width=4)
    for k in (-120, -40, 60):
        s.d.line([(x + k, y + 120), (x + k + 140, y - 120)], fill=0, width=1)
    s.balloon((x + 200, y - 120), "Outer lens (PC, hard-coated)", (-30, -150))
    s.save("fake-headlamp")


def side_indicator():
    s = Sheet("SIDE DIRECTION INDICATOR", "FK-SI-0002")
    pos = stations((260, 900), 200, 7)
    s.dashed((150, pos[0][1] - AXIS[1] * 150), (pos[-1][0] + 220, pos[-1][1] + AXIS[1] * 220))
    lens = ellipse(240, 110)

    x, y = pos[0]  # connector
    s.solid(x, y, rounded_rect(80, 60, 6))
    for k in (-20, 0, 20):
        s.d.rectangle([x + k - 4, y - 10, x + k + 4, y + 10], outline=0, width=2)
    s.balloon((x, y + 30), "Connector", (-40, 130))
    x, y = pos[1]  # clip
    clip = [(-90, 40), (-90, -40), (90, -40), (90, 40), (70, 40), (70, -20), (-70, -20), (-70, 40)]
    s.solid(x, y, clip, depth=(18, -12))
    s.balloon((x - 90, y + 40), "Retaining clip", (-60, 130))
    x, y = pos[2]  # housing
    s.solid(x, y, ellipse(260, 125), depth=(60, -40), width=4)
    s.outline(x, y, ellipse(220, 95))
    s.balloon((x, y + 62), "Housing (ASA)", (-30, 170))
    x, y = pos[3]  # PCB with LEDs
    s.solid(x, y, rounded_rect(200, 70, 8), depth=(10, -7))
    for k in range(-70, 80, 35):
        s.d.rectangle([x + k - 10, y - 10, x + k + 10, y + 10], outline=0, width=2)
        s.circle(x + k, y, 5)
    s.balloon((x + 100, y), "Amber LEDs on PCB", (60, -170))
    x, y = pos[4]  # reflector
    s.solid(x, y, ellipse(230, 105), depth=(30, -20))
    for k in range(-70, 80, 35):
        s.outline(x + k, y, ellipse(30, 40))
    s.balloon((x, y + 52), "Inner reflector", (-20, 170))
    x, y = pos[5]  # gasket
    s.outline(x, y, lens, width=4)
    s.outline(x, y, ellipse(222, 94), width=1)
    s.balloon((x + 120, y), "Gasket (EPDM)", (70, -170))
    x, y = pos[6]  # lens
    s.solid(x, y, lens, depth=(14, -10), width=4)
    for k in range(-90, 100, 18):
        s.d.line([(x + k, y - 40), (x + k, y + 40)], fill=0, width=1)
    s.outline(x, y, ellipse(200, 80))
    s.balloon((x, y + 55), "Outer lens (amber PMMA)", (40, 150))
    s.save("fake-side-indicator")


def chmsl():
    s = Sheet("CENTRE HIGH-MOUNTED STOP LAMP", "FK-S3-0003")
    bar = rounded_rect(900, 70, 30)
    pos = [(850, 300 + 150 * i) for i in range(6)]
    s.dashed((300, 220), (300, 1080))
    s.dashed((1400, 220), (1400, 1180))

    x, y = pos[0]  # outer lens (top = outermost)
    s.solid(x, y, bar, depth=(40, -25), width=4)
    for k in range(-420, 430, 30):
        s.d.line([(x + k, y - 30), (x + k + 12, y + 30)], fill=0, width=1)
    s.balloon((x - 450, y), "Outer lens (red PMMA)", (-180, -40))
    x, y = pos[1]  # diffuser
    s.solid(x, y, rounded_rect(860, 50, 22), depth=(30, -18))
    s.hatch(x - 400, y - 18, x + 400, y + 18, step=22)
    s.balloon((x + 430, y), "Light guide / diffuser", (170, -20))
    x, y = pos[2]  # flex PCB with LEDs
    s.solid(x, y, rounded_rect(840, 22, 6), depth=(20, -12))
    for k in range(-390, 400, 52):
        s.d.rectangle([x + k - 9, y - 7, x + k + 9, y + 7], fill=255, outline=0, width=2)
    s.d.line([(x + 420, y), (x + 480, y + 60), (x + 560, y + 60)], fill=0, width=3)
    s.balloon((x - 420, y), "Red LEDs on flexible PCB", (-180, 20))
    x, y = pos[3]  # seal
    s.outline(x, y, rounded_rect(910, 78, 32), width=3)
    s.outline(x, y, rounded_rect(890, 62, 26), width=1)
    s.balloon((x + 455, y), "Seal (PU foam tape)", (160, 10))
    x, y = pos[4]  # housing
    s.solid(x, y, bar, depth=(60, -38), width=4)
    s.outline(x, y, rounded_rect(860, 44, 18))
    s.balloon((x - 450, y), "Housing (ABS/PC)", (-170, 30))
    x, y = pos[5]  # bracket + harness
    for k in (-300, 300):
        s.solid(x + k, y, [(-70, 30), (-70, -10), (-30, -30), (30, -30), (70, -10), (70, 30)], depth=(25, -15))
        s.circle(x + k, y, 10)
    s.balloon((x - 370, y + 10), "Mounting bracket", (-180, -70))
    s.d.line([(x + 470, y - 160), (x + 520, y - 40), (x + 470, y + 60)], fill=0, width=4)
    s.solid(x + 470, y + 85, rounded_rect(60, 40, 6))
    s.balloon((x + 500, y + 85), "Wiring harness with connector", (160, 20))
    s.save("fake-chmsl")


if __name__ == "__main__":
    headlamp()
    side_indicator()
    chmsl()

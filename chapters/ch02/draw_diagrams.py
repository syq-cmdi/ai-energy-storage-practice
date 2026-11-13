"""Vector teaching diagrams. Coordinates in a 1440-unit design space.

Each figure uses a subject-specific composition rather than a generic flowchart.
The numeric examples are read from the chapter data, or marked conceptual.
"""

from pathlib import Path
from html import escape
import csv, math

B = Path(__file__).resolve().parents[2]
OUT = B / "assets/figures"
OUT.mkdir(parents=True, exist_ok=True)
TEAL = "#087F8C"
BLUE = "#3466B0"
AMBER = "#C77D18"
PURPLE = "#7954A1"
INK = "#183448"
MUTED = "#526A7A"
GRID = "#D9E4EB"
RED = "#BB4D4D"
PALE = ["#EAF6F5", "#EDF3FC", "#FFF4E3", "#F3EEF8"]
COLORS = [TEAL, BLUE, AMBER, PURPLE]


def text(x, y, s, size=28, color=INK, anchor="start", weight=400):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{escape(str(s))}</text>'


def rect(x, y, w, h, fill="white", stroke=GRID, r=8, sw=1.5):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def path(d, c=MUTED, w=2.2, fill="none", dash="", arrow=False, opacity=1):
    return (
        f'<path d="{d}" fill="{fill}" stroke="{c}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{dash}" opacity="{opacity}"'
        + (' marker-end="url(#arrow)"' if arrow else "")
        + "/>"
    )


def line(x, y, X, Y, **kw):
    return path(f"M{x},{y} L{X},{Y}", **kw)


def circle(x, y, r, fill="white", stroke=GRID, sw=2):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def label(x, y, num, title, c=TEAL):
    return (
        circle(x + 16, y - 10, 17, c, c)
        + text(x + 16, y - 1, num, 22, "white", "middle", 600)
        + text(x + 44, y, title, 31, c, weight=600)
    )


def check(x, y, c=TEAL):
    return path(f"M{x},{y} l7,7 l15,-19", c, 3.3)


def arrow(x, y, X, Y, c=MUTED):
    return line(x, y, X, Y, c=c, w=2.5, arrow=True)


def save(n, h, body):
    defs = f'<defs><marker id="arrow" viewBox="0 0 12 12" markerWidth="8" markerHeight="8" refX="10" refY="6" orient="auto-start-reverse"><path d="M1 1 L11 6 L1 11" fill="none" stroke="{MUTED}" stroke-width="1.5"/></marker></defs>'
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="{h}" viewBox="0 0 1440 {h}">{defs}<rect width="1440" height="{h}" fill="white"/><g font-family="PingFang SC, Heiti SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif">{body}</g></svg>'
    (OUT / f"图{n}.svg").write_text(svg, encoding="utf-8")


def file_icon(x, y, c, kind="CSV", scale=1):
    a = path("M0 0 H52 L70 18 V86 H0 Z", c, 2.5, "white") + path(
        "M52 0 V18 H70", c, 2.5
    )
    a += rect(8, 39, 54, 29, c, c, 3) + text(35, 60, kind, 18, "white", "middle", 600)
    return f'<g transform="translate({x},{y}) scale({scale})">{a}</g>'


def battery(x, y, w, h, c, frac=0.7):
    a = rect(x + w * 0.32, y - 9, w * 0.36, 11, c, c, 2) + rect(
        x, y, w, h, "white", c, 7, 2.2
    )
    a += rect(
        x + 6, y + h * (1 - frac) + 5, w - 12, max(1, h * frac - 11), c, "none", 3
    )
    return a


def poly(points, c=TEAL, w=3.8, dash=""):
    return path("M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points), c, w, dash=dash)


def axis(x, y, w, h, xlim, ylim, xticks, yticks, xlab, ylab):
    xf = lambda a: x + (a - xlim[0]) / (xlim[1] - xlim[0]) * w
    yf = lambda a: y + h - (a - ylim[0]) / (ylim[1] - ylim[0]) * h
    b = ""
    for t in yticks:
        b += line(x, yf(t), x + w, yf(t), c=GRID, w=1.2) + text(
            x - 18, yf(t) + 8, f"{t:g}", 25, MUTED, "end"
        )
    for t in xticks:
        b += line(xf(t), y + h, xf(t), y + h + 7, c=MUTED, w=1.4) + text(
            xf(t), y + h + 36, f"{t:g}", 25, MUTED, "middle"
        )
    b += path(f"M{x} {y} V{y+h} H{x+w}", MUTED, 1.8)
    b += text(x, y - 20, ylab, 27, INK) + text(
        x + w / 2, y + h + 74, xlab, 27, INK, "middle"
    )
    return b, xf, yf


# 2.2: two time axes with an explicit capacity example and an RUL distance.
b = label(32, 45, "A", "一次运行内：SOC随充放电变化")
a, xf, yf = axis(
    100,
    109,
    700,
    204,
    (0, 60),
    (0, 1),
    [0, 15, 30, 45, 60],
    [0, 0.5, 1],
    "运行时间 / min",
    "SOC",
)
b += a
series = [
    (
        0.8 - 0.007 * k
        if k < 30
        else (0.59 + 0.004 * (k - 30) if k < 45 else 0.65 - 0.01 * (k - 45))
    )
    for k in range(61)
]
b += poly([(xf(k), yf(v)) for k, v in enumerate(series)], TEAL)
b += battery(927, 123, 88, 168, TEAL, 0.5) + text(
    1060, 145, "示例：SOC = 50%", 29, TEAL, weight=600
)
b += (
    text(1060, 191, "当前可用容量1.6 A·h", 26)
    + text(1060, 232, "剩余电量0.8 A·h", 26)
    + text(1060, 280, "容量基准需与SOH对应", 25, MUTED)
)
b += line(40, 430, 1395, 430, c=GRID, w=1.5)
b += label(32, 489, "B", "跨多个循环：SOH衰减，RUL量到指定终点", BLUE)
a, xf, yf = axis(
    100,
    552,
    700,
    205,
    (0, 200),
    (0.6, 1.04),
    [0, 50, 100, 150, 200],
    [0.6, 0.8, 1],
    "循环号",
    "容量型SOH",
)
b += a
h = lambda n: 1 - 0.0008 * n - 0.000006 * max(n - 80, 0) ** 2
end = next(n for n in range(201) if h(n) <= 0.8)
current = 120
b += poly([(xf(k), yf(h(k))) for k in range(201)], BLUE) + line(
    xf(0), yf(0.8), xf(200), yf(0.8), c=AMBER, w=2, dash="7 6"
)
b += circle(xf(current), yf(h(current)), 6, "white", BLUE, 3) + circle(
    xf(end), yf(h(end)), 6, AMBER, AMBER
)
b += line(
    xf(current), yf(0.8) + 25, xf(end), yf(0.8) + 25, c=AMBER, w=2.2, arrow=True
) + text((xf(current) + xf(end)) / 2, yf(0.8) + 62, "剩余循环", 25, AMBER, "middle")
b += (
    text(945, 550, "容量型SOH示例", 29, BLUE, weight=600)
    + battery(955, 600, 70, 119, BLUE, 1)
    + battery(1118, 624, 70, 95, TEAL, 1)
)
b += text(990, 760, "参考2 A·h", 26, BLUE, "middle") + text(
    1153, 760, "当前1.6 A·h", 26, TEAL, "middle"
)
b += text(1067, 811, "SOH = 1.6 / 2 = 80%", 28, INK, "middle", 600)
b += text(1380, 868, "概念关系；终点判据需事先定义", 24, MUTED, "end")
save("2.2", 895, b)

# 2.3: true values in a five-cycle input window; withheld target in separate lane.
with (B / "chapters/ch02/reference_results/cycles.csv").open(
    encoding="utf-8", newline=""
) as stream:
    cycles = list(csv.DictReader(stream))
rr = [r for r in cycles if r["cell_id"] == "C09" and 96 <= int(r["cycle"]) <= 100]
b = label(32, 46, "A", "同一电芯C09：历史窗口与预测目标")
cols = [210, 410, 610, 810, 1010]
for j, x in enumerate(cols):
    b += text(
        x + 75, 100, ["n−4", "n−3", "n−2", "n−1", "n"][j], 28, INK, "middle"
    ) + text(x + 75, 137, f"循环{96+j}", 25, MUTED, "middle")
for i, (name, unit, c) in enumerate(
    [("容量比例", "无量纲", TEAL), ("内阻", "mΩ", BLUE), ("温度", "℃", AMBER)]
):
    y = 170 + i * 101
    b += text(28, y + 36, name, 28, c, weight=600) + text(28, y + 71, unit, 24, MUTED)
    for j, r in enumerate(rr):
        value = [
            float(r["capacity_ah"]) / 2,
            float(r["resistance_ohm"]) * 1000,
            float(r["temperature_c"]),
        ][i]
        b += rect(cols[j], y, 150, 78, PALE[i], c, 8, 1.6) + text(
            cols[j] + 75,
            y + 48,
            f"{value:.3f}" if i == 0 else f"{value:.2f}",
            30,
            c,
            "middle",
            600,
        )
b += line(1194, 72, 1194, 477, c=PURPLE, w=2.5, dash="8 7") + text(
    1294, 114, "n+1", 30, PURPLE, "middle", 600
)
b += (
    rect(1225, 218, 174, 118, PALE[3], PURPLE, 10, 1.7)
    + text(1312, 266, "SOH标签", 28, PURPLE, "middle", 600)
    + text(1312, 308, "预测后评分", 25, PURPLE, "middle")
)
b += arrow(1166, 278, 1213, 278)
b += path("M210 490 V505 H1160 V490", MUTED, 2) + text(
    685, 549, "输入5×3 → 按时间顺序展开为15维", 29, INK, "middle", 600
)
b += text(685, 597, "每一列都已完成；目标循环的观测不进入输入", 27, MUTED, "middle")
save("2.3", 630, b)

# 2.4: 12 tangible cells, disjoint assignment, a separate role for calibration.
b = label(32, 45, "A", "12个电芯先分组，各组内部再生成历史窗口")
groups = [
    (55, 535, TEAL, PALE[0], range(1, 7), "训练", "930个窗口", "拟合模型与缩放器"),
    (618, 160, BLUE, PALE[1], [7], "选择", "155个窗口", "选择候选方法"),
    (806, 160, AMBER, PALE[2], [8], "校准", "155个窗口", "确定经验带宽"),
    (996, 390, PURPLE, PALE[3], range(9, 13), "测试", "620个窗口", "评价冻结方法"),
]
for x, w, c, fill, ids, title, count, detail in groups:
    b += rect(x, 88, w, 238, fill, "none", 8) + text(
        x + w / 2, 131, title, 31, c, "middle", 600
    )
    ids = list(ids)
    step = w / (len(ids) + 0.25)
    for j, k in enumerate(ids):
        xx = x + step * (j + 0.6) - 22
        b += battery(xx, 166, 44, 74, c, 0.8) + text(
            xx + 22, 280, f"C{k:02}", 24, c, "middle"
        )
    b += text(x + w / 2, 371, count, 29, c, "middle", 600) + text(
        x + w / 2, 416, detail, 25, INK, "middle"
    )
for x in [599, 787, 975]:
    b += line(x, 75, x, 437, c=GRID, w=1.5, dash="6 7")
b += path("M70 474 H1380", MUTED, 2.2, arrow=True)
for x, c, txt in [
    (310, TEAL, "只在训练组学习参数"),
    (695, BLUE, "由C07选模"),
    (888, AMBER, "C08只定带宽"),
    (1192, PURPLE, "最后报告C09—C12"),
]:
    b += circle(x, 474, 6, c, c) + text(x, 523, txt, 24, c, "middle")
b += text(
    720,
    581,
    "每芯160循环 → 155个目标（6—160）；窗口数不等于独立电芯数",
    27,
    MUTED,
    "middle",
)
save("2.4", 615, b)

# 2.7: sparse drawing of a fully connected network, with a residual addition path.
b = label(32, 45, "A", "固定窗口前馈网络：从历史观测预测下一循环变化量")
b += text(117, 112, "5×3历史窗口", 27, TEAL, "middle", 600)
for i in range(5):
    for j in range(3):
        b += rect(38 + j * 49, 145 + i * 47, 40, 36, PALE[j], COLORS[j], 4, 1.2)
b += text(111, 423, "展开为15维", 26, TEAL, "middle") + arrow(194, 261, 257, 261)
b += rect(273, 157, 202, 210, PALE[1], BLUE, 8, 1.8) + text(
    374, 209, "训练缩放器", 29, BLUE, "middle", 600
)
b += text(374, 263, "(x − μ) / σ", 30, INK, "middle") + text(
    374, 315, "仅训练组拟合", 25, MUTED, "middle"
)
b += arrow(488, 261, 548, 261)
ins = [167, 213, 259, 305, 351]
hidden = [135, 179, 223, 267, 311, 355, 399]
for y in ins:
    for Y in hidden:
        b += line(590, y, 812, Y, c=BLUE, w=1.15, opacity=0.2)
for y in hidden:
    b += line(832, y, 1015, 261, c=PURPLE, w=1.5, opacity=0.42)
for y in ins:
    b += circle(580, y, 10, "white", BLUE, 2)
for y in hidden:
    b += circle(822, y, 13, PALE[3], PURPLE, 2)
b += text(579, 112, "15个输入", 27, BLUE, "middle", 600) + text(
    579, 409, "⋮", 30, BLUE, "middle"
)
b += text(822, 84, "16个隐藏单元", 27, PURPLE, "middle", 600) + text(
    822, 449, "tanh激活", 26, PURPLE, "middle"
)
b += (
    circle(1035, 261, 18, PALE[2], AMBER, 2.5)
    + text(1120, 218, "变化量 f(x)", 29, AMBER, "middle", 600)
    + text(1120, 306, "单位：百分点", 25, MUTED, "middle")
)
b += path("M1062 261 H1130 V464", AMBER, 2.4, arrow=True) + text(
    1191, 391, "÷100", 28, AMBER, "middle"
)
b += path("M113 438 V500 H1093", TEAL, 2.4, arrow=True) + text(
    459, 479, "最近一次已观测SOH", 27, TEAL, "middle"
)
b += circle(1130, 500, 28, "white", TEAL, 2.8) + text(
    1130, 512, "+", 38, TEAL, "middle"
)
b += arrow(1167, 500, 1210, 500) + rect(1223, 450, 184, 103, PALE[0], TEAL, 8, 1.8)
b += text(1315, 493, "下一循环", 27, TEAL, "middle", 600) + text(
    1315, 532, "SOH", 29, TEAL, "middle", 600
)
b += text(720, 588, "预测SOH = 最近SOH + f(x) / 100", 29, TEAL, "middle", 600)
b += text(
    720,
    634,
    "仅示意部分连接；不同窗口复用权重，不传递循环隐藏状态",
    26,
    MUTED,
    "middle",
)
save("2.7", 660, b)
print("4 chapter 2 schematics written")

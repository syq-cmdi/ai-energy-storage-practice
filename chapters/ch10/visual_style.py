"""Chapter 10 CJK typography and restrained scientific plotting style."""

from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

INK = "#183448"
MUTED = "#5C7181"
GRID = "#DCE5EC"


def setup(font_path=None):
    """Use an installed CJK font; fonts are not redistributed with the code."""
    if font_path:
        font_manager.fontManager.addfont(str(font_path))
        family = font_manager.FontProperties(fname=str(font_path)).get_name()
    else:
        local = Path("/System/Library/Fonts/STHeiti Light.ttc")
        local_family = None
        if local.exists():
            font_manager.fontManager.addfont(str(local))
            local_family = font_manager.FontProperties(fname=str(local)).get_name()
        available = {f.name for f in font_manager.fontManager.ttflist}
        family = next(
            (
                n
                for n in [
                    "Noto Sans CJK SC",
                    "Source Han Sans SC",
                    # FreeType exposes the first face of Ubuntu's Noto CJK TTC.
                    "Noto Sans CJK JP",
                    "Microsoft YaHei",
                    "PingFang SC",
                    "Heiti SC",
                    "SimHei",
                ]
                if n in available
            ),
            local_family,
        )
        if family is None:
            raise RuntimeError(
                "需要中文字体。Linux可安装fonts-noto-cjk，或通过--font指定合法取得的中文字体文件。"
            )
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [family, "DejaVu Sans"],
            "font.size": 10.2,
            "axes.titlesize": 11.2,
            "axes.titleweight": "bold",
            "axes.labelsize": 10.2,
            "axes.edgecolor": MUTED,
            "axes.linewidth": 0.7,
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": 9.4,
            "ytick.labelsize": 9.4,
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "legend.fontsize": 9.3,
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def style(ax, grid="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis=grid, color=GRID, lw=0.65)
    ax.set_axisbelow(True)
    ax.tick_params(pad=4)

from pathlib import Path

import matplotlib.pyplot as plt


def slugify_title(title):
    title = title.lower().strip()
    chars = []

    for char in title:
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "_":
            chars.append("_")

    slug = "".join(chars).strip("_")
    return slug[:80] or "plot"


def figure_title(fig):
    if fig._suptitle is not None:
        title = fig._suptitle.get_text()
        if title:
            return title

    for ax in fig.axes:
        title = ax.get_title()
        if title:
            return title

    return "plot"


def save_all_figures(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_png in output_dir.glob("*.png"):
        old_png.unlink()

    saved_paths = []

    for index, fig_num in enumerate(plt.get_fignums(), start=1):
        fig = plt.figure(fig_num)
        title = figure_title(fig)
        file_name = f"{index:02d}_{slugify_title(title)}.png"
        output_path = output_dir / file_name

        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        saved_paths.append(output_path)

    plt.close("all")

    print()
    print(f"Saved {len(saved_paths)} plot PNG files to {output_dir}:")
    for output_path in saved_paths:
        print(f"  {output_path}")

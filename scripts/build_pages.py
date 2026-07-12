"""Build static map pages from the directories selected in pages.toml."""

import html
import json
import shutil
import tomllib
from collections import defaultdict
from pathlib import Path

from branca.element import Element

from src.main import MapMaker

ROOT = Path(__file__).resolve().parents[1]


def load_config():
    with (ROOT / "pages.toml").open("rb") as config_file:
        config = tomllib.load(config_file)["pages"]
    if not config.get("region_directories"):
        raise ValueError("pages.region_directories must contain at least one directory")
    return config


def find_map_items(directory):
    candidates = sorted(directory.glob("*_map_items.json"))
    if len(candidates) != 1:
        raise ValueError(
            f"Expected exactly one *_map_items.json in {directory}, found {len(candidates)}"
        )
    return candidates[0]


def marker_regions(map_maker):
    regions = defaultdict(list)
    for locations in map_maker.mi.d.get("markers", {}).values():
        for marker in locations.values():
            coordinates = marker.get("coordinates")
            if coordinates and len(coordinates) == 2:
                regions["All markers"].append(coordinates)
                if region := marker.get("region"):
                    regions[str(region)].append(coordinates)
    return dict(regions)


def add_region_controls(map_maker, regions):
    if not regions:
        return

    buttons = "".join(
        f'<button type="button" data-region="{html.escape(name, quote=True)}">'
        f"{html.escape(name)}</button>"
        for name in regions
    )
    panel = f"""
    <div class="roadtrip-region-panel" aria-label="Map regions">
      <strong>Focus region</strong><div>{buttons}</div>
    </div>
    """
    styles = """
    <style>
      .roadtrip-region-panel {
        position: fixed; top: 12px; left: 50px; z-index: 1000;
        max-width: calc(100vw - 115px); padding: 8px 10px;
        border-radius: 6px; background: rgba(255,255,255,.94);
        box-shadow: 0 1px 6px rgba(0,0,0,.3); font: 14px/1.4 sans-serif;
      }
      .roadtrip-region-panel strong { display: block; margin-bottom: 5px; }
      .roadtrip-region-panel div { display: flex; flex-wrap: wrap; gap: 5px; }
      .roadtrip-region-panel button {
        border: 1px solid #777; border-radius: 4px; padding: 5px 9px;
        background: white; color: #222; cursor: pointer;
      }
      .roadtrip-region-panel button:hover,
      .roadtrip-region-panel button:focus { background: #e8f1fb; }
      @media (max-width: 600px) {
        .roadtrip-region-panel { top: 8px; left: 46px; font-size: 13px; }
        .roadtrip-region-panel strong { display: none; }
      }
    </style>
    """
    map_name = map_maker.base_map.get_name()
    script = f"""
    const roadtripRegionBounds = {json.dumps(regions)};
    function focusRoadtripRegion(name) {{
      const coordinates = roadtripRegionBounds[name];
      if (!coordinates || coordinates.length === 0) return;
      if (coordinates.length === 1) {{
        {map_name}.setView(coordinates[0], 13);
      }} else {{
        {map_name}.fitBounds(coordinates, {{padding: [30, 30]}});
      }}
    }}
    document.querySelectorAll('.roadtrip-region-panel button').forEach((button) => {{
      button.addEventListener('click', () => focusRoadtripRegion(button.dataset.region));
    }});
    """
    root = map_maker.base_map.get_root()
    root.header.add_child(Element(styles))
    root.html.add_child(Element(panel))
    root.script.add_child(Element(script))


def build_map(directory_name, output_directory):
    source_directory = ROOT / directory_name
    if not source_directory.is_dir():
        raise FileNotFoundError(f"Configured map directory does not exist: {source_directory}")
    map_maker = MapMaker(map_item_filename=str(find_map_items(source_directory)), language="en")
    map_maker.main()
    add_region_controls(map_maker, marker_regions(map_maker))
    filename = f'{directory_name.casefold().replace(" ", "-")}.html'
    map_maker.save_map(str(output_directory / filename))
    return directory_name, filename


def write_index(title, pages, output_directory):
    links = "".join(
        f'<li><a href="{html.escape(filename)}">{html.escape(name)}</a></li>'
        for name, filename in pages
    )
    index = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>body{{max-width:42rem;margin:3rem auto;padding:0 1rem;font-family:sans-serif}}
a{{display:block;padding:.8rem;font-size:1.2rem}}</style></head>
<body><h1>{html.escape(title)}</h1><ul>{links}</ul>
<script>if ({len(pages)} === 1) window.location.replace({json.dumps(pages[0][1])});</script>
</body></html>"""
    (output_directory / "index.html").write_text(index, encoding="utf-8")
    (output_directory / ".nojekyll").touch()


def main():
    config = load_config()
    output_directory = ROOT / config.get("output_directory", "_site")
    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)
    pages = [build_map(name, output_directory) for name in config["region_directories"]]
    write_index(config.get("title", "Roadtrip Planner"), pages, output_directory)
    print(f"Built {len(pages)} map page(s) in {output_directory}")


if __name__ == "__main__":
    main()
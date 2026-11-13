import json

import pytest

from bench.build import build
from bench.degrade import VARIANTS, degrade
from bench.pieces import PIECES, SMOKE_IDS
from sheet_transposer.render import render_png, render_svg_pages


@pytest.fixture(scope="module")
def k545_png(k545_xml):
    return render_png(render_svg_pages(k545_xml)[0], width_px=1240)


def test_degrade_is_deterministic_and_changes_pixels(k545_png):
    a = degrade(k545_png, "phone", seed=1)
    b = degrade(k545_png, "phone", seed=1)
    assert a == b and a != k545_png


def test_scan_differs_from_phone(k545_png):
    assert degrade(k545_png, "scan", seed=1) != degrade(k545_png, "phone", seed=1)


def test_clean_variant_is_unchanged(k545_png):
    assert degrade(k545_png, "clean", seed=1) == k545_png


def test_build_one_piece(tmp_path):
    build(out_dir=tmp_path, only=["mozart_k545"])
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert {e["truth_key"] for e in manifest} == {"C major", "E♭ major", "A major"}
    assert all((tmp_path / e["page_id"] / f"{v}.png").exists() for e in manifest for v in VARIANTS)
    assert all((tmp_path / e["page_id"] / "truth.musicxml").exists() for e in manifest)
    assert "mozart_k545__c-major" in {e["page_id"] for e in manifest}


def test_pieces_cover_kinds_and_smoke_ids_are_pieces():
    assert {p.kind for p in PIECES} == {"piano", "vocal", "organ"}
    piece_ids = {p.id for p in PIECES}
    assert all(page_id.split("__")[0] in piece_ids for page_id in SMOKE_IDS)


def _ink_bbox(png: bytes):
    import io

    import numpy as np
    from PIL import Image

    pixels = np.asarray(Image.open(io.BytesIO(png)).convert("L"))
    ys, xs = np.where(pixels < 100)
    return xs.min(), xs.max(), ys.min(), ys.max(), pixels.shape


@pytest.mark.parametrize("variant", ["scan", "phone"])
def test_degraded_music_stays_inside_the_image(k545_png, variant):
    for seed in range(5):
        x0, x1, y0, y1, (height, width) = _ink_bbox(degrade(k545_png, variant, seed=seed))
        assert x0 > 5 and y0 > 5 and x1 < width - 5 and y1 < height - 5


def test_organ_layout_keeps_key_signature_on_every_staff():
    from bench.build import load_excerpt

    organ = next(p for p in PIECES if p.kind == "organ")
    for part in load_excerpt(organ).parts:
        assert part.recurse().getElementsByClass("KeySignature").first().sharps == 3

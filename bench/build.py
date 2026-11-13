"""Build benchmark pages: truth MusicXML plus clean/scan/phone images.

Usage: python -m bench.build [--only PIECE_ID ...]
"""

import argparse
import copy
import json
import zlib
from pathlib import Path

from music21 import clef, corpus, key, stream

from bench.degrade import VARIANTS, degrade
from bench.pieces import PIECES, Piece
from sheet_transposer.keys import detect_key, key_from_label, key_label
from sheet_transposer.render import render_png, render_svg_pages
from sheet_transposer.scoreio import to_musicxml
from sheet_transposer.transpose import transpose_score

DATA_DIR = Path(__file__).parent / "data"
PAGE_WIDTH_PX = 2480  # A4 at 300 dpi


def key_slug(label: str) -> str:
    """'E♭ major' -> 'e-flat-major' (ASCII, filesystem-safe)."""
    return label.lower().replace("♭", "-flat").replace("♯", "-sharp").replace(" ", "-")


def load_excerpt(piece: Piece) -> stream.Score:
    score = corpus.parse(piece.corpus_path).measures(*piece.bars)
    return _organ_layout(score) if piece.kind == "organ" else score


def _organ_layout(chorale: stream.Score) -> stream.Score:
    """Four-part chorale as three staves: soprano+alto chords, tenor, bass as 'pedal'."""
    soprano, alto, tenor, bass = chorale.parts
    upper = stream.Part(stream.Score([soprano, alto]).chordify().getElementsByClass(stream.Measure))
    first_bar = upper.getElementsByClass(stream.Measure).first()
    first_bar.insert(0, copy.deepcopy(soprano.recurse().getElementsByClass(key.KeySignature).first()))
    tenor.insert(0, clef.BassClef())
    return stream.Score([upper, tenor, bass])


def pages_for(piece: Piece) -> list[tuple[str, stream.Score]]:
    """(truth key label, truth score) for the original key and each extra key."""
    original = load_excerpt(piece)
    detected = detect_key(original).key
    pages = [(key_label(detected), original)]
    for label in piece.extra_keys:
        target = key_from_label(label)
        if target.mode != detected.mode:
            target = key_from_label(f"{label.split()[0]} {detected.mode}")
        pages.append((key_label(target), transpose_score(original, detected, target)))
    return pages


def build(out_dir: Path = DATA_DIR, only: list[str] | None = None) -> list[dict]:
    manifest = []
    for piece in PIECES:
        if only and piece.id not in only:
            continue
        for truth_key, score in pages_for(piece):
            page_id = f"{piece.id}__{key_slug(truth_key)}"
            page_dir = out_dir / page_id
            page_dir.mkdir(parents=True, exist_ok=True)
            xml = to_musicxml(score)
            (page_dir / "truth.musicxml").write_text(xml, encoding="utf-8")
            svgs = render_svg_pages(xml)
            if len(svgs) != 1:
                raise ValueError(f"{page_id} engraves to {len(svgs)} pages; shorten its bars")
            clean = render_png(svgs[0], width_px=PAGE_WIDTH_PX)
            for variant in VARIANTS:
                seed = zlib.crc32(f"{page_id}/{variant}".encode())
                (page_dir / f"{variant}.png").write_bytes(degrade(clean, variant, seed))
            manifest.append(
                {"page_id": page_id, "piece_id": piece.id, "kind": piece.kind,
                 "truth_key": truth_key, "variants": list(VARIANTS)}
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="piece ids to build")
    args = parser.parse_args()
    for entry in build(only=args.only):
        print(entry["page_id"], entry["truth_key"])

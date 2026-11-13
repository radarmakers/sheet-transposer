"""Public-domain pieces from music21's bundled corpus used for the benchmark."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Piece:
    id: str
    corpus_path: str
    bars: tuple[int, int]
    kind: Literal["piano", "vocal", "organ"]
    extra_keys: tuple[str, ...] = ()  # extra transposed pages, e.g. "E♭ major"


PIECES = [
    Piece("mozart_k545", "mozart/k545/movement1_exposition.mxl", (1, 12), "piano", ("E♭ major", "A major")),
    Piece("joplin_maple", "joplin/maple_leaf_rag.mxl", (1, 12), "piano", ("D major",)),
    Piece("clara_pol1", "schumann_clara/polonaise_op1n1.mxl", (1, 12), "piano", ("B major",)),
    Piece("clara_pol2", "schumann_clara/polonaise_op1n2.mxl", (1, 12), "piano", ("F♯ major",)),
    Piece("clara_pol3", "schumann_clara/polonaise_op1n3.mxl", (1, 12), "piano"),
    Piece("clara_pol4", "schumann_clara/polonaise_op1n4.mxl", (1, 12), "piano"),
    Piece("cpebach_h186", "cpebach/h186.mxl", (1, 12), "piano"),
    Piece("schoenberg_19_2", "schoenberg/opus19/movement2.mxl", (1, 9), "piano"),
    Piece("schoenberg_19_6", "schoenberg/opus19/movement6.mxl", (1, 9), "piano"),
    Piece("schubert_linden", "schubert/Lindenbaum.xml", (1, 12), "vocal"),
    Piece("schumann_dl2", "schumann_robert/dichterliebe_no2.xml", (1, 12), "vocal"),
    Piece("bach_organlike", "bach/bwv66.6", (1, 9), "organ"),
]

SMOKE_IDS = ["mozart_k545__c-major", "joplin_maple__d-major", "schubert_linden__e-major"]

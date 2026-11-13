import pytest
from music21 import corpus

from sheet_transposer.scoreio import to_musicxml


@pytest.fixture(scope="session")
def k545_score():
    return corpus.parse("mozart/k545/movement1_exposition.mxl").measures(1, 12)


@pytest.fixture(scope="session")
def k545_xml(k545_score):
    return to_musicxml(k545_score)


def make_score(key_sig_sharps: int | None, notes: list[str]):
    """Single-part 4/4 score of quarter notes; key_sig_sharps=None means no key signature."""
    from music21 import key, meter, note, stream

    part = stream.Part()
    if key_sig_sharps is not None:
        part.append(key.KeySignature(key_sig_sharps))
    part.append(meter.TimeSignature("4/4"))
    for name in notes:
        part.append(note.Note(name, quarterLength=1))
    score = stream.Score([part])
    return score.makeNotation()

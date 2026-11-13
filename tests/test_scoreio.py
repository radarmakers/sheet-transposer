import pytest
from music21 import corpus

from sheet_transposer.scoreio import parse_musicxml, to_musicxml


def test_round_trip_preserves_notes():
    s = corpus.parse("mozart/k545/movement1_exposition.mxl").measures(1, 4)
    again = parse_musicxml(to_musicxml(s))
    assert [p.nameWithOctave for p in again.pitches] == [p.nameWithOctave for p in s.pitches]


def test_garbage_raises_value_error():
    with pytest.raises(ValueError):
        parse_musicxml("not music")

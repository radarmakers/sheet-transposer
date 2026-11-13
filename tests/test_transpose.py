from music21 import corpus, key
from music21.key import Key

from conftest import make_score
from sheet_transposer.transpose import semitone_shift, shift_label, transpose_score


def _signatures(score):
    return [ks.sharps for ks in score.recurse().getElementsByClass(key.KeySignature)]


def test_shift_eflat_to_d_is_down_one():
    assert semitone_shift(Key("E-"), Key("D")) == -1
    assert shift_label(-1) == "down 1 semitone"


def test_shift_labels():
    assert shift_label(0) == "no change"
    assert shift_label(2) == "up 2 semitones"
    assert shift_label(-3) == "down 3 semitones"


def test_tritone_goes_down():
    assert semitone_shift(Key("C"), Key("F#")) == -6


def test_same_key_is_identity():
    s = make_score(0, "C4 E4 G4".split())
    out = transpose_score(s, Key("C"), Key("C"))
    assert [p.nameWithOctave for p in out.pitches] == ["C4", "E4", "G4"]


def test_c_to_dflat_spells_in_flats_and_updates_signature():
    out = transpose_score(make_score(0, "C4 F#4 G4".split()), Key("C"), Key("D-"))
    assert [p.name for p in out.pitches] == ["D-", "G", "A-"]
    assert _signatures(out) == [-5]


def test_all_key_signatures_are_replaced():
    s = make_score(0, "C4 D4 E4 F4 G4 A4 B4 C5 D5 E5 F5 G5".split())
    s.parts[0].getElementsByClass("Measure")[2].insert(0, key.KeySignature(1))
    out = transpose_score(s, Key("C"), Key("E-"))
    assert _signatures(out) == [-3, -3]


def test_minor_to_minor_keeps_correct_double_sharp():
    out = transpose_score(make_score(-3, "C4 F#4 G4".split()), Key("c"), Key("c#"))
    assert [p.name for p in out.pitches] == ["C#", "F##", "G#"]


def test_round_trip_restores_original():
    s = corpus.parse("mozart/k545/movement1_exposition.mxl").measures(1, 12)
    there = transpose_score(s, Key("C"), Key("E-"))
    back = transpose_score(there, Key("E-"), Key("C"))
    assert [p.nameWithOctave for p in back.pitches] == [p.nameWithOctave for p in s.pitches]


def test_input_score_is_not_modified():
    s = make_score(0, "C4 E4 G4".split())
    transpose_score(s, Key("C"), Key("D"))
    assert [p.nameWithOctave for p in s.pitches] == ["C4", "E4", "G4"]

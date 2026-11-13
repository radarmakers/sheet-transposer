from music21 import corpus, key

from conftest import make_score
from sheet_transposer.keys import (
    CONVENTIONAL_MAJORS,
    CONVENTIONAL_MINORS,
    detect_key,
    key_choices,
    key_from_label,
    key_label,
    signature_label,
)


def test_c_major_scale_is_c_major_confident():
    r = detect_key(make_score(0, "C4 D4 E4 F4 G4 A4 B4 C5 G4 E4 C4".split()))
    assert key_label(r.key) == "C major" and r.confident and r.sharps == 0


def test_a_minor_with_leading_tone_is_a_minor():
    r = detect_key(make_score(0, "A3 C4 E4 G#4 A4 E4 C4 B3 G#3 A3".split()))
    assert key_label(r.key) == "A minor"


def test_major_minor_tie_is_not_confident():
    r = detect_key(make_score(-3, "E-4 G4 B-4 C5".split()))
    assert not r.confident and r.alternative is not None


def test_missing_key_signature_means_zero_sharps():
    assert detect_key(make_score(None, "C4 E4 G4 C5".split())).sharps == 0


def test_real_chorale_is_f_sharp_minor():
    r = detect_key(corpus.parse("bach/bwv66.6"))
    assert key_label(r.key) == "F♯ minor" and r.sharps == 3


def test_labels_round_trip():
    for name in CONVENTIONAL_MAJORS:
        assert key_label(key_from_label(f"{name} major")) == f"{name} major"
    for name in CONVENTIONAL_MINORS:
        assert key_label(key_from_label(f"{name} minor")) == f"{name} minor"


def test_choices_are_twelve_conventional_keys():
    assert key_choices("major") == [f"{n} major" for n in CONVENTIONAL_MAJORS]
    assert key_choices("minor") == [f"{n} minor" for n in CONVENTIONAL_MINORS]


def test_choices_include_unconventional_detected_key():
    choices = key_choices("major", include=key.Key("C#"))
    assert "C♯ major" in choices and len(choices) == 13


def test_signature_label():
    assert signature_label(-3) == "3 flats"
    assert signature_label(1) == "1 sharp"
    assert signature_label(0) == "no sharps or flats"

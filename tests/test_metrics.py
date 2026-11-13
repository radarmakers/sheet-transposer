import copy

from bench.metrics import compare


def test_identical_scores_are_perfect(k545_score):
    s = compare(k545_score, k545_score, "C major")
    assert s.note_f1 == 1.0 and s.duration_acc == 1.0
    assert s.bars_ok and s.key_ok and s.key_sig_ok
    assert s.full_bars_frac == 1.0


def test_one_wrong_pitch_lowers_f1(k545_score):
    got = copy.deepcopy(k545_score)
    first = next(iter(got.recurse().notes))
    first.pitches[0].midi += 1
    s = compare(k545_score, got, "C major")
    assert 0.9 < s.note_f1 < 1.0


def test_missing_bar_breaks_bars_ok(k545_score):
    got = copy.deepcopy(k545_score)
    for part in got.parts:
        part.remove(part.getElementsByClass("Measure")[-1])
    assert not compare(k545_score, got, "C major").bars_ok


def test_wrong_key_label_is_reported(k545_score):
    assert not compare(k545_score, k545_score, "G major").key_ok


def test_extra_empty_bar_does_not_shift_every_note(k545_score):
    from music21 import stream

    got = copy.deepcopy(k545_score)
    for part in got.parts:
        part.insert(0, stream.Measure(number=0))
        for number, measure in enumerate(part.getElementsByClass("Measure"), start=1):
            measure.number = number
    s = compare(k545_score, got, "C major")
    assert s.note_f1 == 1.0 and not s.bars_ok

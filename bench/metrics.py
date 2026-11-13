"""Score recognised music against the truth for one benchmark page."""

from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher

from music21 import stream

from sheet_transposer.keys import detect_key, key_label

ONSET_GRID = 12  # offsets compared on a 1/12-quarter grid (covers triplets and sixteenths)


@dataclass
class PageScore:
    key_sig_ok: bool
    key_ok: bool
    note_precision: float
    note_recall: float
    note_f1: float
    duration_acc: float  # among matched notes
    bars_ok: bool  # same measure count
    full_bars_frac: float  # inner measures whose content fills the time signature


def _bars(score: stream.Score) -> list[Counter]:
    """Per bar (by position, all parts merged): multiset of (onset in bar, midi, duration)."""
    bars: list[Counter] = []
    for part in score.parts:
        for index, measure in enumerate(part.getElementsByClass(stream.Measure)):
            if index == len(bars):
                bars.append(Counter())
            for item in measure.recurse().notes:
                onset = round(float(item.getOffsetInHierarchy(measure)) * ONSET_GRID) / ONSET_GRID
                for p in item.pitches:
                    bars[index][(onset, p.midi, float(item.quarterLength))] += 1
    return bars


def _without_duration(events: Counter) -> Counter:
    stripped: Counter = Counter()
    for (onset, midi, _), count in events.items():
        stripped[(onset, midi)] += count
    return stripped


def _aligned_pairs(truth: list[Counter], got: list[Counter]) -> list[tuple[Counter, Counter]]:
    """Pair truth bars with recognised bars, tolerating inserted or dropped bars."""
    def signature(bar: Counter) -> tuple:
        return tuple(sorted(_without_duration(bar).elements()))

    matcher = SequenceMatcher(None, [signature(b) for b in truth], [signature(b) for b in got], autojunk=False)
    pairs = []
    for _, t0, t1, g0, g1 in matcher.get_opcodes():
        pairs.extend(zip(truth[t0:t1], got[g0:g1]))  # equal/replace pair up by position
    return pairs


def _measure_count(score: stream.Score) -> int:
    return max((len(part.getElementsByClass(stream.Measure)) for part in score.parts), default=0)


def _full_bars_frac(score: stream.Score) -> float:
    inner = [
        m
        for part in score.parts
        for m in list(part.getElementsByClass(stream.Measure))[1:-1]
    ]
    if not inner:
        return 1.0
    full = sum(1 for m in inner if m.duration.quarterLength == m.barDuration.quarterLength)
    return full / len(inner)


def compare(truth: stream.Score, got: stream.Score, truth_key: str) -> PageScore:
    truth_bars, got_bars = _bars(truth), _bars(got)
    total_truth = sum(sum(b.values()) for b in truth_bars)
    total_got = sum(sum(b.values()) for b in got_bars)
    matched = duration_matched = 0
    for truth_bar, got_bar in _aligned_pairs(truth_bars, got_bars):
        matched += sum((_without_duration(truth_bar) & _without_duration(got_bar)).values())
        duration_matched += sum((truth_bar & got_bar).values())
    precision = matched / total_got if total_got else 0.0
    recall = matched / total_truth if total_truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    detected = detect_key(got)
    return PageScore(
        key_sig_ok=detected.sharps == detect_key(truth).sharps,
        key_ok=key_label(detected.key) == truth_key,
        note_precision=precision,
        note_recall=recall,
        note_f1=f1,
        duration_acc=duration_matched / matched if matched else 0.0,
        bars_ok=_measure_count(truth) == _measure_count(got),
        full_bars_frac=_full_bars_frac(got),
    )

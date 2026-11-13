"""Key detection and user-facing key names."""

from dataclasses import dataclass

from music21 import key, stream

CONVENTIONAL_MAJORS = ["C", "D♭", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"]
CONVENTIONAL_MINORS = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "G♯", "A", "B♭", "B"]

# How much better (correlation) the chosen mode must fit than its relative before we're "confident".
CONFIDENCE_MARGIN = 0.1


@dataclass(frozen=True)
class KeyResult:
    key: key.Key  # best guess
    sharps: int  # from the first key signature; flats are negative; 0 if none
    confident: bool
    alternative: key.Key | None  # the relative major/minor, only when not confident


def detect_key(score: stream.Score) -> KeyResult:
    """Read the key signature, then use the notes to choose between major and relative minor."""
    signature = score.recurse().getElementsByClass(key.KeySignature).first()
    sharps = signature.sharps if signature is not None else 0
    major = key.KeySignature(sharps).asKey("major")
    minor = key.KeySignature(sharps).asKey("minor")

    analysed = score.analyze("key")
    interpretations = [analysed, *analysed.alternateInterpretations]

    def fit(candidate: key.Key) -> float:
        for interpretation in interpretations:
            if _same_key(interpretation, candidate):
                return interpretation.correlationCoefficient
        return float("-inf")

    chosen, other = (major, minor) if fit(major) >= fit(minor) else (minor, major)
    confident = fit(chosen) - fit(other) >= CONFIDENCE_MARGIN and _same_key(analysed, chosen)
    return KeyResult(key=chosen, sharps=sharps, confident=confident, alternative=None if confident else other)


def _same_key(a: key.Key, b: key.Key) -> bool:
    return a.tonic.name == b.tonic.name and a.mode == b.mode


def key_label(k: key.Key) -> str:
    """'E♭ major', 'F♯ minor'."""
    return f"{_pretty(k.tonic.name)} {k.mode}"


def key_from_label(label: str) -> key.Key:
    tonic, mode = label.split()[:2]
    return key.Key(tonic.replace("♭", "-").replace("♯", "#"), mode)


def _pretty(music21_name: str) -> str:
    return music21_name.replace("-", "♭").replace("#", "♯")


def signature_label(sharps: int) -> str:
    """'3 flats', '1 sharp', 'no sharps or flats'."""
    if sharps == 0:
        return "no sharps or flats"
    count, kind = abs(sharps), "sharp" if sharps > 0 else "flat"
    return f"{count} {kind}{'s' if count > 1 else ''}"


def key_choices(mode: str, include: key.Key | None = None) -> list[str]:
    """The 12 conventional keys of a mode, ordered by pitch from C, plus `include` if it's missing."""
    names = CONVENTIONAL_MAJORS if mode == "major" else CONVENTIONAL_MINORS
    choices = [f"{name} {mode}" for name in names]
    if include is not None and key_label(include) not in choices:
        position = include.tonic.pitchClass + 1  # just after its enharmonic twin
        choices.insert(position, key_label(include))
    return choices

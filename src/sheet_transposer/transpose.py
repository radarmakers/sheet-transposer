"""Move a score from one key to another by the nearest interval, spelled for the target key."""

from music21 import interval, key, pitch, stream


def semitone_shift(src: key.Key, dst: key.Key) -> int:
    """Nearest move between tonics, in -6..5 semitones (a tritone goes down)."""
    shift = (dst.tonic.pitchClass - src.tonic.pitchClass) % 12
    return shift - 12 if shift >= 6 else shift


def shift_label(semitones: int) -> str:
    """'no change', 'up 1 semitone', 'down 3 semitones'."""
    if semitones == 0:
        return "no change"
    direction = "up" if semitones > 0 else "down"
    count = abs(semitones)
    return f"{direction} {count} semitone{'s' if count > 1 else ''}"


def transpose_score(score: stream.Score, src: key.Key, dst: key.Key) -> stream.Score:
    """Return a new score moved from `src` to `dst`; key signatures all become `dst`'s."""
    start = pitch.Pitch(f"{src.tonic.name}4")
    end = pitch.Pitch(f"{dst.tonic.name}4")
    wanted = semitone_shift(src, dst)
    # Pick the octave of the target tonic that gives the nearest move.
    end.octave += round((wanted - (end.ps - start.ps)) / 12)
    moved = score.transpose(interval.Interval(noteStart=start, noteEnd=end), inPlace=False)
    for signature in moved.recurse().getElementsByClass(key.KeySignature):
        signature.sharps = dst.sharps
    return moved

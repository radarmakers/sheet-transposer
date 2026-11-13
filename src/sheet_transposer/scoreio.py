"""Convert between MusicXML text and music21 scores."""

from music21 import converter, stream
from music21.musicxml.m21ToXml import GeneralObjectExporter


def parse_musicxml(text: str) -> stream.Score:
    """Parse MusicXML text into a music21 Score. Raises ValueError if it can't be read."""
    try:
        parsed = converter.parseData(text, format="musicxml")
    except Exception as error:  # music21 raises many different exception types
        raise ValueError(f"Not readable MusicXML: {error}") from error
    if not isinstance(parsed, stream.Score):
        raise ValueError("MusicXML did not contain a score")
    return parsed


def to_musicxml(score: stream.Score) -> str:
    """Serialise a music21 Score to MusicXML text."""
    return GeneralObjectExporter(score).parse().decode("utf-8")

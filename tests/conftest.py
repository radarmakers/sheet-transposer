import pytest
from music21 import corpus

from sheet_transposer.scoreio import to_musicxml


@pytest.fixture(scope="session")
def k545_score():
    return corpus.parse("mozart/k545/movement1_exposition.mxl").measures(1, 12)


@pytest.fixture(scope="session")
def k545_xml(k545_score):
    return to_musicxml(k545_score)

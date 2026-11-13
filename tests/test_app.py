import pytest
from streamlit.testing.v1 import AppTest


def test_app_loads_with_uploader_and_footer():
    at = AppTest.from_file("../app.py").run(timeout=30)
    assert not at.exception
    assert "Sheet Transposer" in at.title[0].value
    assert any("AGPL" in caption.value for caption in at.caption)
    assert at.get("file_uploader")


def _app_with_upload():
    """Runs app.py with st.file_uploader returning the file named in $UPLOAD_PATH."""
    import os
    from pathlib import Path
    from types import SimpleNamespace

    import streamlit as st

    upload_path = Path(os.environ["UPLOAD_PATH"])
    fake = SimpleNamespace(name=upload_path.name, getvalue=upload_path.read_bytes)
    st.file_uploader = lambda *args, **kwargs: fake
    import sheet_transposer.workflow as workflow

    # Patches persist across AppTest runs in one process, so always start from the real function.
    real_read_page = workflow.__dict__.setdefault("_real_read_page", workflow.read_page)
    workflow.read_page = real_read_page
    real_build_outputs = workflow.__dict__.setdefault("_real_build_outputs", workflow.build_outputs)
    workflow.build_outputs = real_build_outputs
    if os.environ.get("FAIL_OUTPUTS"):
        def failing_build_outputs(*args, **kwargs):
            raise RuntimeError("engraving failed")

        workflow.build_outputs = failing_build_outputs
        st.cache_data.clear()  # an earlier run may have cached a successful result
    if os.environ.get("FAKE_MUSICXML"):
        musicxml = Path(os.environ["FAKE_MUSICXML"]).read_text()
        workflow.read_page = lambda upload: real_read_page(upload, recognise=lambda image: musicxml)
    app = Path(os.environ["APP_PATH"])
    exec(compile(app.read_text(), str(app), "exec"), {"__name__": "__main__"})


def _run_uploaded(monkeypatch, upload, musicxml_path=None, timeout=60):
    from pathlib import Path

    monkeypatch.setenv("UPLOAD_PATH", str(upload))
    monkeypatch.setenv("APP_PATH", str(Path(__file__).parents[1] / "app.py"))
    if musicxml_path:
        monkeypatch.setenv("FAKE_MUSICXML", str(musicxml_path))
    return AppTest.from_function(_app_with_upload).run(timeout=timeout)


def test_upload_shows_key_choices_music_and_downloads(monkeypatch, tmp_path, k545_xml):
    import io

    from PIL import Image

    upload = tmp_path / "page.png"
    Image.new("RGB", (200, 200), "white").save(upload)
    musicxml = tmp_path / "k545.musicxml"
    musicxml.write_text(k545_xml)
    at = _run_uploaded(monkeypatch, upload, musicxml)
    assert not at.exception
    original, target = at.selectbox
    assert original.value == "C major"
    assert target.value == "C major"
    assert "C major (original)" in target.options
    assert "D major — up 2 semitones" in target.options
    assert any(c.value == "no change" for c in at.caption)
    target.select("D major").run(timeout=60)
    assert any(c.value == "up 2 semitones" for c in at.caption)
    assert [b.label for b in at.get("download_button")] == ["Download MusicXML", "Download PDF"]


def test_unreadable_upload_shows_friendly_error(monkeypatch, tmp_path):
    upload = tmp_path / "notes.txt"
    upload.write_text("not an image")
    at = _run_uploaded(monkeypatch, upload)
    assert not at.exception
    assert "photo or scan" in at.error[0].value
    assert not at.selectbox


@pytest.mark.slow
def test_real_homr_end_to_end_on_phone_photo(monkeypatch):
    from pathlib import Path

    page = Path(__file__).parents[1] / "bench" / "data" / "mozart_k545__c-major" / "phone.png"
    at = _run_uploaded(monkeypatch, page, timeout=300)
    assert not at.exception
    assert at.selectbox[0].value == "C major"
    assert len(at.get("download_button")) == 2


def _k545_upload(tmp_path, k545_xml):
    from PIL import Image

    upload = tmp_path / "page.png"
    Image.new("RGB", (200, 200), "white").save(upload)
    musicxml = tmp_path / "k545.musicxml"
    musicxml.write_text(k545_xml)
    return upload, musicxml


def test_original_key_can_be_corrected_to_relative_minor(monkeypatch, tmp_path, k545_xml):
    at = _run_uploaded(monkeypatch, *_k545_upload(tmp_path, k545_xml))
    original = at.selectbox[0]
    assert "A minor" in original.options
    original.select("A minor").run(timeout=60)
    assert not at.exception
    target = at.selectbox[1]
    assert target.value == "A minor"
    assert "B minor — up 2 semitones" in target.options
    assert all(option.split()[1].startswith("minor") for option in target.options)


def test_engraving_failure_is_a_friendly_error(monkeypatch, tmp_path, k545_xml):
    monkeypatch.setenv("FAIL_OUTPUTS", "1")
    at = _run_uploaded(monkeypatch, *_k545_upload(tmp_path, k545_xml))
    assert not at.exception
    assert "Couldn't draw" in at.error[0].value

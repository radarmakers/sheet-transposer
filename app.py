"""Sheet Transposer — Streamlit app (single column, top to bottom)."""

import hashlib
import time
from pathlib import Path

import streamlit as st

from sheet_transposer import omr, workflow
from sheet_transposer.keys import key_choices, key_from_label, key_label, signature_label
from sheet_transposer.transpose import semitone_shift, shift_label
from sheet_transposer.workflow import Outputs, Page, ReadError

SOURCE_URL = "https://github.com/radarmakers/sheet-transposer"  # set at deploy (see README)


@st.cache_resource(max_entries=20, show_spinner=False)
def cached_read(upload: bytes) -> Page:
    """Identical uploads are read once; homr only runs for new images."""
    return workflow.read_page(upload)


@st.cache_data(max_entries=50, show_spinner=False)
def cached_outputs(musicxml: str, _page: Page, original: str, target: str) -> Outputs:
    """Keyed on the MusicXML text and key labels (`_page` is not hashed)."""
    return workflow.build_outputs(_page, original, target)


def slug(label: str) -> str:
    return label.lower().replace("♭", "-flat").replace("♯", "-sharp").replace(" ", "-")


st.set_page_config(page_title="Sheet Transposer", page_icon="🎼")
st.title("Sheet Transposer")
st.caption("Works best with printed piano music: flat, well-lit, whole page in frame.")

upload = st.file_uploader("Upload a photo or scan of one page", type=["jpg", "jpeg", "png", "webp"])
st.caption("On Android, take the photo with your camera app first, then upload it from your gallery.")

if upload is not None:
    data = upload.getvalue()
    digest = hashlib.sha256(data).hexdigest()[:16]
    read_seconds = st.session_state.setdefault("read_seconds", {})
    if digest in read_seconds:  # already read in this session: no status box on key changes
        page = cached_read(data)
    else:
        with st.status("Reading the music… this can take a few minutes. Keep this screen open.") as status:
            if omr.is_busy():
                st.write("A friend's page is being read first — yours will start straight after.")
            started = time.monotonic()
            try:
                page = cached_read(data)
            except ReadError as error:
                status.update(label="Couldn't read the music", state="error")
                st.error(str(error))
                if error.details:
                    with st.expander("Technical details"):
                        st.code(error.details, language=None)
                st.stop()
            read_seconds[digest] = time.monotonic() - started
            status.update(label="Music read", state="complete")
    st.caption(f"Music read in {read_seconds[digest]:.0f} s")

    detected = page.detected
    other_mode = "minor" if detected.key.mode == "major" else "major"
    # Detected mode first; the other mode too, so "actually C minor" can be chosen.
    original_choices = key_choices(detected.key.mode, include=detected.key) + key_choices(
        other_mode, include=detected.alternative or detected.key.relative
    )
    original = st.selectbox(
        "Original key",
        original_choices,
        index=original_choices.index(key_label(detected.key)),
        key=f"original-{digest}",
        help="Detected from the key signature and the notes. Change it if it's wrong.",
    )
    st.caption(f"Detected: {signature_label(detected.sharps)}")
    if not detected.confident and detected.alternative is not None:
        st.info(f"Not sure — this could also be {key_label(detected.alternative)}. Change it above if so.")

    original_key = key_from_label(original)
    target_choices = key_choices(original_key.mode, include=original_key)

    def describe(label: str) -> str:
        if label == original:
            return f"{label} (original)"
        return f"{label} — {shift_label(semitone_shift(original_key, key_from_label(label)))}"

    # Remember the chosen target so correcting the original key doesn't reset it.
    wanted = st.session_state.get(f"target-{digest}", original)
    target = st.selectbox(
        "Change to",
        target_choices,
        index=target_choices.index(wanted if wanted in target_choices else original),
        format_func=describe,
    )
    st.session_state[f"target-{digest}"] = target

    try:
        outputs = cached_outputs(page.musicxml, page, original, target)
    except Exception:  # engraving odd recognised music can fail in music21 or Verovio
        st.error("Couldn't draw the music in that key. Try another key, or download the MusicXML instead.")
        st.download_button("Download recognised MusicXML", page.musicxml, file_name=f"{Path(upload.name).stem}.musicxml")
        st.stop()
    st.caption(outputs.shift)

    for svg in outputs.svgs:
        st.image(svg, width="stretch")

    stem = f"{Path(upload.name).stem}-{slug(target)}"
    left, right = st.columns(2)
    left.download_button(
        "Download MusicXML",
        outputs.musicxml,
        file_name=f"{stem}.musicxml",
        mime="application/vnd.recordare.musicxml+xml",
    )
    right.download_button("Download PDF", outputs.pdf, file_name=f"{stem}.pdf", mime="application/pdf")

st.divider()
st.caption(f"Source code (AGPL-3.0): {SOURCE_URL}")
st.caption(
    "Recognition by homr; it may misread notes — fix them in MuseScore via the MusicXML download."
)

"""Sheet Transposer — Streamlit app (single column, top to bottom)."""

import time
from pathlib import Path

import streamlit as st

from sheet_transposer.keys import key_choices, key_from_label, key_label, signature_label
from sheet_transposer.workflow import Outputs, Page, ReadError, build_outputs, read_page

SOURCE_URL = "https://github.com/OWNER/sheet-transposer"  # set at deploy (see README)
ORIGINAL_SUFFIX = " (original)"


@st.cache_resource(max_entries=20, show_spinner=False)
def cached_read(upload: bytes) -> Page:
    """Identical uploads are read once; homr only runs for new images."""
    return read_page(upload)


@st.cache_data(max_entries=50, show_spinner=False)
def cached_outputs(musicxml: str, _page: Page, original: str, target: str) -> Outputs:
    """Keyed on the MusicXML text and key labels (`_page` is not hashed)."""
    return build_outputs(_page, original, target)


def slug(label: str) -> str:
    return label.lower().replace("♭", "-flat").replace("♯", "-sharp").replace(" ", "-")


st.set_page_config(page_title="Sheet Transposer", page_icon="🎼")
st.title("Sheet Transposer")
st.caption("Works best with printed piano music: flat, well-lit, whole page in frame.")

upload = st.file_uploader("Upload a photo or scan of one page", type=["jpg", "jpeg", "png", "webp"])

if upload is not None:
    data = upload.getvalue()
    with st.status("Reading the music… this can take a few minutes. Keep this screen open.") as status:
        st.write("If a friend is also using the app, yours will start when theirs finishes.")
        started = time.monotonic()
        try:
            page = cached_read(data)
        except ReadError as error:
            status.update(label="Couldn't read the music", state="error")
            st.error(str(error))
            st.stop()
        status.update(label=f"Music read in {time.monotonic() - started:.0f} s", state="complete")

    detected = page.detected
    original_choices = key_choices(detected.key.mode, include=detected.key)
    original = st.selectbox(
        "Original key",
        original_choices,
        index=original_choices.index(key_label(detected.key)),
        help=f"Detected from the key signature ({signature_label(detected.sharps)}) and the notes.",
    )
    st.caption(f"Detected: {signature_label(detected.sharps)}")
    if not detected.confident and detected.alternative is not None:
        st.info(f"Not sure — this could also be {key_label(detected.alternative)}. Change it above if so.")

    original_key = key_from_label(original)
    target_choices = [
        f"{label}{ORIGINAL_SUFFIX}" if label == original else label
        for label in key_choices(original_key.mode, include=original_key)
    ]
    target_display = st.selectbox(
        "Change to", target_choices, index=target_choices.index(f"{original}{ORIGINAL_SUFFIX}")
    )
    target = target_display.removesuffix(ORIGINAL_SUFFIX)

    outputs = cached_outputs(page.musicxml, page, original, target)
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

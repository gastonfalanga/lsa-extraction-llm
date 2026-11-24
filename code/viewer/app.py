import os
import sys
import random
import streamlit as st

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

from io_utils import load_all_signs, save_sign_changes
from validate_dataset import validate_sign_entry, load_schema
from filter_utils import render_filters, apply_filters
from ui_pdf_viewer import render_pdf_preview, render_image_crop_tab, render_image_upload_tab             
from ui_phonology import render_phonology_tab             
from ui_components import (                               
    render_meanings_tab,
    render_raw_json_editor_tab
)

st.set_page_config(page_title="LSA-MorphDict Auditor", layout="wide")

st.html("""<style>

    code {font-size:0.85em !important}
    textarea { font-family:monospace!important; font-size:0.8em !important}
    .stMarkdown p { margin-bottom: 0.5em !important}
    button {border-color: transparent !important}
    button p {margin: 0 !important}
    .stVerticalBlock label p {font-size: 0.8em !important; font-family: Monaco !important}
    
    </style>""")

all_signs = load_all_signs()

if not all_signs:
    st.warning("No JSON files found in 'data/processed/'. Process some batches first!")
else:
    col_stat, col_rand, col_val = st.sidebar.columns([2, 1, 1])
    errors = []
    if len(all_signs) != int(all_signs[-1].get("sign_id")[-4:]):
        st.sidebar.warning(f"⚠️ Last ID (`{int(all_signs[-1].get('sign_id')[-4:])}`) is not the same as the total count (`{len(all_signs)}`). Sign IDs might not be sequential and there might be duplicates. Consider re-indexing the dataset.")
    with col_stat:
        st.markdown(f"**Total Signs:** {len(all_signs)}")
    with col_rand:
        if st.button("🎲", help="Randomize Sign Selection"):
            st.session_state["current_index"] = random.randint(0, len(all_signs) - 1)
            st.rerun()
    with col_val:
        if st.button("✅", help="Validate ALL signs against Schema"):
            schema = load_schema()
            with st.spinner("Validating dataset..."):
                for s in all_signs:
                    is_valid, err_msg = validate_sign_entry(s, schema)
                    if not is_valid:
                        errors.append((s.get("sign_id"), err_msg))
            
            if errors:
                st.sidebar.error(f"Found {len(errors)} invalid signs!")
                with st.sidebar.expander("View Validation Errors", expanded=True):
                    for sign_id, err in errors:
                        st.markdown(f"**{sign_id}**: `{err}`")
            else:
                st.sidebar.success("All signs are perfectly valid!")

    schema = load_schema()
    with st.sidebar.expander("Filters & Sorting", expanded=False):
        filters = render_filters(schema)
        
    search_query = st.sidebar.text_input("Search", placeholder="Type Spanish word or ID...")

    filtered_signs = apply_filters(all_signs, filters, search_query)

    if not filtered_signs:
        st.sidebar.warning("No signs match criteria.")
        filtered_signs = all_signs

    if "current_index" not in st.session_state:
        st.session_state["current_index"] = 0

    if st.session_state["current_index"] >= len(filtered_signs):
        st.session_state["current_index"] = 0

    list_options = [f"{s.get('sign_id')}: {s.get('spanish_word')}" for s in filtered_signs]
    
    with st.sidebar.container(height=500):
        selected_option = st.radio(
            "Sign List",
            options=list_options,
            index=st.session_state["current_index"],
            label_visibility="collapsed"
        )
    
    new_index = list_options.index(selected_option)
    if new_index != st.session_state["current_index"]:
        st.session_state["current_index"] = new_index
        st.rerun()

    current_sign = filtered_signs[st.session_state["current_index"]]
    ocr_data = current_sign.get("ocr_data", {})

    col1, col2 = st.columns([1, 1.3])

    with col1:
        is_valid_current, current_err_msg = validate_sign_entry(current_sign, schema)
        if not is_valid_current:
            st.error(f"⚠️ {current_err_msg}")

        st.markdown(f"### {current_sign.get('spanish_word')} <small><i>({current_sign.get('english_word', '')})</i> <span style='font-size: 0.6em'>`{current_sign.get('sign_id')}`</span></small>", unsafe_allow_html=True)

        btn_prev, btn_next = st.columns(2)
        with btn_prev:
            if st.button("◀ Prev", width="stretch"):
                st.session_state["current_index"] = (st.session_state["current_index"] - 1) % len(filtered_signs)
                st.rerun()
        with btn_next:
            if st.button("Next ▶", width="stretch"):
                st.session_state["current_index"] = (st.session_state["current_index"] + 1) % len(filtered_signs)
                st.rerun()

        st.markdown(f"**JSON File:** `{current_sign.get('_source_file')}` &nbsp;|&nbsp; **PDF:** `{ocr_data.get('source_batch_file', 'N/A')}`")
        st.markdown(
            f"**OCR Page:** `{ocr_data.get('source_page_ocr')}` &nbsp;|&nbsp; "
            f"**OCR Index:** `{ocr_data.get('sign_index_on_page')}`"
        )

        def get_confidence_badge(score):
            score = score or 0
            if score >= 0.9:
                return f"🟢 `{score}`"
            elif score >= 0.5:
                return f"🟡 `{score}`"
            else:
                return f"🔴 `{score}`"

        st.markdown(
            f"OCR Confidence: {get_confidence_badge(ocr_data.get('ocr_confidence'))} &nbsp;|&nbsp; "
            f"Translation Confidence: {get_confidence_badge(ocr_data.get('translation_confidence'))}",
            unsafe_allow_html=True
        )
        
        ocr_notes = ocr_data.get("ocr_notes")
        if ocr_notes:
            st.warning(f"**OCR Agent Note:** {ocr_notes}")

        
        v_col1, v_col2 = st.columns([1, 1])
        with v_col1:
            st.markdown("**Human Verification Level:**", unsafe_allow_html=True)
        with v_col2:
            current_level = ocr_data.get("human_verification_level") or 0
            new_level = st.selectbox(
                "Human Verification Level",
                options=[0, 1, 2, 3, 4, 5],
                index=current_level,
                key=f"verif_{current_sign.get('sign_id')}",
                label_visibility="collapsed"
            )

            if new_level != current_level:
                if "ocr_data" not in current_sign:
                    current_sign["ocr_data"] = {}
                current_sign["ocr_data"]["human_verification_level"] = new_level if new_level > 0 else None
                save_sign_changes(current_sign)
                st.toast("Verification level updated!", icon="💾")
                st.rerun()
                
        notes_key = f"edit_notes_{current_sign.get('sign_id')}"
        
        if st.session_state.get(notes_key):
            new_notes = st.text_area("Edit Notes", value=ocr_data.get("human_notes") or "")
            n_col1, n_col2 = st.columns(2)
            with n_col1:
                if st.button("💾", width='stretch'):
                    current_sign["ocr_data"]["human_notes"] = new_notes if new_notes else None
                    save_sign_changes(current_sign)
                    st.session_state[notes_key] = False
                    st.rerun()
            with n_col2:
                if st.button("✖️", width='stretch'):
                    st.session_state[notes_key] = False
                    st.rerun()
        else:
            h_col1, h_col2 = st.columns([0.85, 0.15])
            with h_col1:
                notes_val = ocr_data.get("human_notes")
                if notes_val:
                    st.info(f"**Human Notes:** {notes_val}")
                else:
                    st.markdown("*No human notes.*")
            with h_col2:
                if st.button("✏️", key=f"btn_edit_notes_{current_sign.get('sign_id')}"):
                    st.session_state[notes_key] = True
                    st.rerun()

        
        render_pdf_preview(current_sign)

    with col2:
        tab_variants, tab_meanings, tab_editor, tab_image, tab_upload = st.tabs([
            "Variants",
            "Meanings",
            "JSON Editor",
            "Image Crop",
            "Upload Image"
        ])

        with tab_variants:
            render_phonology_tab(current_sign)

        with tab_meanings:
            render_meanings_tab(current_sign)

        with tab_editor:
            render_raw_json_editor_tab(current_sign)
            
        with tab_image:
            render_image_crop_tab(current_sign)

        with tab_upload:
            render_image_upload_tab(current_sign)

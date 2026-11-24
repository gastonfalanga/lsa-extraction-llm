import json
import sys
import os
import hashlib
import streamlit as st
from streamlit_ace import st_ace

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from io_utils import save_sign_changes
from validate_dataset import validate_sign_entry, load_schema


def render_meanings_tab(current_sign):
    meanings = current_sign.get("meanings", [])
    if not meanings and current_sign.get("sign_variants"):
        for v in current_sign["sign_variants"]:
            meanings.extend(v.get("meanings", []))

    if not meanings:
        st.info("No meanings recorded for this sign.")
        return

    for m_idx, meaning in enumerate(meanings, 1):
        def_es = meaning.get("definition") or "N/A"
        def_en = meaning.get("definition_en")
        
        st.markdown(f"#### Meaning Definition #{m_idx}")
        if def_en:
            st.markdown(f"**Definition:** {def_es} *({def_en})*")
        else:
            st.markdown(f"**Definition:** {def_es}")

        examples = meaning.get("examples", [])
        examples_en = meaning.get("examples_en", [])
        if examples:
            st.markdown("##### Examples")
            for ex_es, ex_en in zip(examples, examples_en or [""] * len(examples)):
                if ex_en:
                    st.markdown(f"- {ex_es} *({ex_en})*")
                else:
                    st.markdown(f"- {ex_es}")

        notes = meaning.get("notes", {})
        if notes:
            st.markdown("##### Notes & Lexical Network")
            syn_es = notes.get("synonyms", [])
            syn_en = notes.get("synonyms_en", [])
            if syn_es or syn_en:
                es_str = ", ".join(syn_es) if syn_es else "None"
                en_str = f" ({', '.join(syn_en)})" if syn_en else ""
                st.markdown(f"- **Synonyms:** {es_str}*{en_str}*")

            wf_es = notes.get("word_family", [])
            wf_en = notes.get("word_family_en", [])
            if wf_es or wf_en:
                es_str = ", ".join(wf_es) if wf_es else "None"
                en_str = f" ({', '.join(wf_en)})" if wf_en else ""
                st.markdown(f"- **Word Family:** {es_str}*{en_str}*")

            fig_es = notes.get("figurative_uses_expressions", [])
            fig_en = notes.get("figurative_uses_expressions_en", [])
            if fig_es or fig_en:
                st.markdown("- **Figurative Uses & Expressions:**")
                for f_es, f_en in zip(fig_es, fig_en or [""] * len(fig_es)):
                    if f_en:
                        st.markdown(f"  - {f_es} *({f_en})*")
                    else:
                        st.markdown(f"  - {f_es}")


def render_raw_json_editor_tab(current_sign):
    editable_data = {k: v for k, v in current_sign.items() if not k.startswith("_")}
    json_string = json.dumps(editable_data, indent=2, ensure_ascii=False)

    data_hash = hashlib.md5(json_string.encode("utf-8")).hexdigest()[:8]

    edited_text = st_ace(
        value=json_string,
        height=600,
        language="json",
        theme="twilight",     
        show_gutter=True,   
        show_print_margin=False,
        wrap=True,
        auto_update=True,   
        min_lines=25,
        key=f"raw_text_{current_sign.get('sign_id')}_{data_hash}"
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🔍 Validate JSON & Enums", width="stretch"):
            try:
                parsed_data = json.loads(edited_text)
                schema = load_schema()
                is_valid, err_msg = validate_sign_entry(parsed_data, schema)

                if is_valid:
                    st.success("✅ JSON is perfectly valid!")
                else:
                    st.error(f"❌ Schema Error:\n\n{err_msg}")
            except json.JSONDecodeError as e:
                st.error(f"❌ Syntax Error: Invalid JSON.\n\n{e}")

    with col2:
        if st.button("💾 Validate & Save Changes", type="primary", width="stretch"):
            try:
                parsed_data = json.loads(edited_text)
                schema = load_schema()
                is_valid, err_msg = validate_sign_entry(parsed_data, schema)

                if not is_valid:
                    st.error(f"Cannot save invalid JSON:\n\n{err_msg}")
                else:
                    parsed_data["_source_file"] = current_sign.get("_source_file")
                    if save_sign_changes(parsed_data):
                        st.success("Sign entry saved!")
                        st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"Cannot save: Invalid JSON.\n\n{e}")

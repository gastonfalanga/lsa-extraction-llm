import os
import json
import streamlit as st

PROCESSED_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "processed")
)


def load_all_signs():
    all_signs = []
    if not os.path.exists(PROCESSED_DIR):
        return all_signs

    for filename in sorted(os.listdir(PROCESSED_DIR)):
        if filename.endswith(".json"):
            filepath = os.path.join(PROCESSED_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    for sign in data:
                        sign["_source_file"] = filename
                        all_signs.append(sign)
                except Exception as e:
                    st.error(f"Error loading {filename}: {e}")
    return all_signs


def save_sign_changes(updated_sign):
    sign_to_save = json.loads(json.dumps(updated_sign))
    filename = sign_to_save.pop("_source_file", None)

    if not filename:
        st.error("Missing source filename. Cannot save changes.")
        return False

    filepath = os.path.join(PROCESSED_DIR, filename)
    if not os.path.exists(filepath):
        st.error(f"Target file {filename} not found.")
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        signs = json.load(f)

    for i, s in enumerate(signs):
        if s["sign_id"] == sign_to_save["sign_id"]:
            signs[i] = sign_to_save
            break

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(signs, f, indent=2, ensure_ascii=False)

    return True

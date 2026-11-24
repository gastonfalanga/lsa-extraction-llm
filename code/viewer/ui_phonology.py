import sys
import os
import copy
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from io_utils import save_sign_changes
from validate_dataset import validate_sign_entry, load_schema

def render_phonology_tab(current_sign):
    variants = current_sign.get("sign_variants", [])
    if not variants:
        st.warning("No variants found for this sign.")
        return

    schema = load_schema()
    defs = schema.get("definitions", {})
    def get_enum(k): return [e for e in defs.get(k, {}).get("enum", []) if e is not None]

    handshapes = [""] + get_enum("handshape_enum")
    move_manners = get_enum("hand_movement_manner_enum")
    move_paths = get_enum("hand_movement_path_enum")
    body_locs = get_enum("body_location_enum")
    space_locs = get_enum("space_location_enum")
    hand_oris = get_enum("hand_orientation_enum")
    arm_oris = get_enum("arm_orientation_enum")
    nmc_facials = get_enum("nmc_facial_enum")
    nmc_movs = get_enum("nmc_body_movement_enum")

    def ensure_options(valid_options, current_value):
        opts = list(valid_options)
        if isinstance(current_value, list):
            for v in current_value:
                if v and v not in opts:
                    opts.append(v)
        elif current_value and current_value not in opts:
            opts.append(current_value)
        return opts

    deduced_fields = current_sign.get("ocr_data", {}).get("visually_deduced_fields", [])

    def mark(text, path):
        return f":red[{text}]" if path in deduced_fields else text

    for v_index, variant in enumerate(variants):
        v_label = variant.get("variant_label") or f"Variante {chr(65 + v_index)}"
        v_type = variant.get("variant_type", "N/A")

        st.markdown(f"`Variant: {v_label}`")
        if variant.get("variant_origin"):
            st.caption(f"**Origin:** {variant.get('variant_origin')} | **Type:** `{v_type}`")

        components = variant.get("sequential_components", [])
        for c_index, comp in enumerate(components):
            order = comp.get("component_order", 1)
            seq_id = f"{current_sign.get('sign_id')}_{v_index}_{c_index}"
            base_path = f"sign_variants[{v_index}].sequential_components[{c_index}]"

            if st.session_state.get("edit_seq_id") == seq_id:
                st.markdown(f"#### ✏️ Editing Sequence {order}")

                with st.container():
                    exec_c1, exec_c2 = st.columns(2)
                    with exec_c1:
                        new_notes = st.text_input("Execution Notes (ES)", value=comp.get("execution_notes") or "", key=f"es_{seq_id}")
                    with exec_c2:
                        new_notes_en = st.text_input("Execution Notes (EN)", value=comp.get("execution_notes_en") or "", key=f"en_{seq_id}")

                    def edit_hand(label, prefix, hand_data):
                        st.markdown(f"##### {label}")

                        ic_val = hand_data.get("initial_configuration")
                        fc_val = hand_data.get("final_configuration")

                        ipb_val = hand_data.get("initial_position", {}).get("body") or []
                        ips_val = hand_data.get("initial_position", {}).get("space") or []
                        fpb_val = hand_data.get("final_position", {}).get("body") or []
                        fps_val = hand_data.get("final_position", {}).get("space") or []

                        ioh_val = hand_data.get("initial_orientation", {}).get("hand") or []
                        ioa_val = hand_data.get("initial_orientation", {}).get("arm") or []
                        foh_val = hand_data.get("final_orientation", {}).get("hand") or []
                        foa_val = hand_data.get("final_orientation", {}).get("arm") or []

                        mov = hand_data.get("movement", {})
                        m_manner_val = mov.get("manner") or []
                        m_path_val = mov.get("path") or []
                        m_contact_val = mov.get("contact", False)
                        m_rep_val = mov.get("repetition", False)

                        ic_opts = ensure_options(handshapes, ic_val)
                        fc_opts = ensure_options(handshapes, fc_val)

                        ipb_opts = ensure_options(body_locs, ipb_val)
                        ips_opts = ensure_options(space_locs, ips_val)
                        fpb_opts = ensure_options(body_locs, fpb_val)
                        fps_opts = ensure_options(space_locs, fps_val)

                        ioh_opts = ensure_options(hand_oris, ioh_val)
                        ioa_opts = ensure_options(arm_oris, ioa_val)
                        foh_opts = ensure_options(hand_oris, foh_val)
                        foa_opts = ensure_options(arm_oris, foa_val)

                        mman_opts = ensure_options(move_manners, m_manner_val)
                        mpath_opts = ensure_options(move_paths, m_path_val)

                        def safe_idx(opts, val): return opts.index(val) if val in opts else 0

                        col_init, col_final = st.columns(2)
                        with col_init:
                            st.markdown("**🔹 Initial**")
                            ic = st.selectbox("Configuration*", ic_opts, index=safe_idx(ic_opts, ic_val), key=f"{prefix}_ic")
                            ipb = st.multiselect("Body Position**", ipb_opts, default=ipb_val, key=f"{prefix}_ipb")
                            ips = st.multiselect("Space Position**", ips_opts, default=ips_val, key=f"{prefix}_ips")
                            
                            if ipb and ips:
                                st.warning("⚠️ Choose either Body OR Space, not both.")
                                
                            ioh = st.multiselect("Hand Orientation***", ioh_opts, default=ioh_val, key=f"{prefix}_ioh")
                            ioa = st.multiselect("Arm Orientation***", ioa_opts, default=ioa_val, key=f"{prefix}_ioa")
                            
                        with col_final:
                            st.markdown("**🔸 Final**")
                            fc = st.selectbox("Configuration", fc_opts, index=safe_idx(fc_opts, fc_val), key=f"{prefix}_fc")
                            fpb = st.multiselect("Body Position**", fpb_opts, default=fpb_val, key=f"{prefix}_fpb")
                            fps = st.multiselect("Space Position**", fps_opts, default=fps_val, key=f"{prefix}_fps")
                            
                            if fpb and fps:
                                st.warning("⚠️ Choose either Body OR Space, not both.")
                                
                            foh = st.multiselect("Hand Orientation***", foh_opts, default=foh_val, key=f"{prefix}_foh")
                            foa = st.multiselect("Arm Orientation***", foa_opts, default=foa_val, key=f"{prefix}_foa")

                        st.markdown("###### Movement")
                        m1, m2, m3 = st.columns(3)
                        with m1: m_manner = st.multiselect("Manner", mman_opts, default=m_manner_val, key=f"{prefix}_mman")
                        with m2: m_path = st.multiselect("Path", mpath_opts, default=m_path_val, key=f"{prefix}_mpath")
                        with m3:
                            m_contact = st.checkbox("Contact", value=m_contact_val, key=f"{prefix}_mcont")
                            m_rep = st.checkbox("Repetition", value=m_rep_val, key=f"{prefix}_mrep")

                        is_empty = not any([ic, fc, ipb, ips, fpb, fps, ioh, ioa, foh, foa, m_manner, m_path])
                        if is_empty and not m_contact and not m_rep:
                            return None

                        out = {}
                        if ic: out["initial_configuration"] = ic
                        if fc: out["final_configuration"] = fc

                        ip_obj = {}
                        if ipb: ip_obj["body"] = ipb
                        if ips: ip_obj["space"] = ips
                        out["initial_position"] = ip_obj

                        io_obj = {}
                        if ioh: io_obj["hand"] = ioh
                        if ioa: io_obj["arm"] = ioa
                        out["initial_orientation"] = io_obj

                        mov_obj = {"contact": m_contact, "repetition": m_rep}
                        if m_manner: mov_obj["manner"] = m_manner
                        if m_path: mov_obj["path"] = m_path
                        out["movement"] = mov_obj

                        if fpb or fps:
                            fp_obj = {}
                            if fpb: fp_obj["body"] = fpb
                            if fps: fp_obj["space"] = fps
                            out["final_position"] = fp_obj

                        if foh or foa:
                            fo_obj = {}
                            if foh: fo_obj["hand"] = foh
                            if foa: fo_obj["arm"] = foa
                            out["final_orientation"] = fo_obj

                        return out

                    new_dom = edit_hand("✋ Dominant Hand", f"dom_{seq_id}", comp.get("dominant_hand", {}))

                    if st.button("⬇️ Copy DH to NDH", key=f"copy_dh_{seq_id}", help="Copies the live inputs from the Dominant Hand into the Non-Dominant Hand."):
                        prefix_dh = f"dom_{seq_id}_"
                        prefix_ndh = f"ndom_{seq_id}_"

                        for k in list(st.session_state.keys()):
                            if k.startswith(prefix_dh):
                                ndh_key = k.replace(prefix_dh, prefix_ndh)
                                st.session_state[ndh_key] = copy.deepcopy(st.session_state[k])

                        st.rerun()

                    new_ndom = edit_hand("🤚 Non-Dominant Hand", f"ndom_{seq_id}", comp.get("non_dominant_hand", {}))

                    st.markdown("##### 🔄 Non-Manual Components (NMC)")
                    nmc_f_val = comp.get("non_manual_components", {}).get("facial_expression") or []
                    nmc_m_val = comp.get("non_manual_components", {}).get("body_movement") or []

                    nmc_f = st.multiselect("Facial Expression", ensure_options(nmc_facials, nmc_f_val), default=nmc_f_val, key=f"nmcf_{seq_id}")
                    nmc_m = st.multiselect("Non-Manual Movement", ensure_options(nmc_movs, nmc_m_val), default=nmc_m_val, key=f"nmcm_{seq_id}")

                    st.write("")
                    b_col1, b_col2 = st.columns([1, 1])
                    with b_col1:
                        if st.button("💾 Validate & Save Sequence", type="primary", use_container_width=True, key=f"save_{seq_id}"):
                            updated_comp = {"component_order": order}
                            if new_notes: updated_comp["execution_notes"] = new_notes
                            if new_notes_en: updated_comp["execution_notes_en"] = new_notes_en
                            if new_dom: updated_comp["dominant_hand"] = new_dom
                            if new_ndom: updated_comp["non_dominant_hand"] = new_ndom

                            if nmc_f or nmc_m:
                                nmc_obj = {}
                                if nmc_f: nmc_obj["facial_expression"] = nmc_f
                                if nmc_m: nmc_obj["body_movement"] = nmc_m
                                updated_comp["non_manual_components"] = nmc_obj

                            temp_sign = copy.deepcopy(current_sign)
                            temp_sign["sign_variants"][v_index]["sequential_components"][c_index] = updated_comp

                            is_val, err = validate_sign_entry(temp_sign, schema)
                            if is_val:
                                if save_sign_changes(temp_sign):
                                    st.success("Sequence saved successfully!")
                                    st.session_state.pop("edit_seq_id", None)
                                    st.rerun()
                            else:
                                st.error(f"❌ Cannot save. Resulting JSON is invalid:\n\n{err}")

                    with b_col2:
                        if st.button("✖️ Cancel", use_container_width=True, key=f"cancel_{seq_id}"):
                            st.session_state.pop("edit_seq_id", None)
                            st.rerun()

                st.divider()
                continue

            hdr_col, btn_col = st.columns([0.85, 0.15])
            with hdr_col:
                st.markdown(f"`Component order: {order}`")
            with btn_col:
                if st.button("✏️", key=f"edit_btn_{seq_id}"):
                    st.session_state["edit_seq_id"] = seq_id
                    st.rerun()

            exec_notes = comp.get("execution_notes")
            exec_notes_en = comp.get("execution_notes_en")
            if exec_notes:
                st.info(f"**Execution Notes:** {exec_notes} *({exec_notes_en})*")

            dom = comp.get("dominant_hand", {})
            non_dom = comp.get("non_dominant_hand", {})

            def render_hand_ro(hand_title, hand_data, hand_path):
                st.markdown(f"##### {hand_title}")
                if not hand_data:
                    st.markdown("`None`")
                    return

                ic = hand_data.get('initial_configuration') or 'None'
                ip = hand_data.get('initial_position') or {}
                fc = hand_data.get('final_configuration')
                fp = hand_data.get('final_position') or {}

                io = hand_data.get('initial_orientation', {}) or {}
                fo = hand_data.get('final_orientation', {}) or {}

                mov = hand_data.get('movement', {}) or {}

                has_final_pos = bool(fp.get('body') or fp.get('space'))
                has_final_ori = bool(fo.get('hand') or fo.get('arm'))
                has_final = bool(fc) or has_final_pos or has_final_ori

                ip_body = ", ".join(ip.get("body", [])) or "None"
                ip_space = ", ".join(ip.get("space", [])) or "None"
                fp_body = ", ".join(fp.get("body", [])) or "None"
                fp_space = ", ".join(fp.get("space", [])) or "None"

                io_hand = ", ".join(io.get("hand", [])) or "None"
                io_arm = ", ".join(io.get("arm", [])) or "None"
                fo_hand = ", ".join(fo.get("hand", [])) or "None"
                fo_arm = ", ".join(fo.get("arm", [])) or "None"

                l_conf_i = mark("**Conf.:**", f"{hand_path}.initial_configuration")
                l_conf_f = mark("**Conf.:**", f"{hand_path}.final_configuration")
                l_body_i = mark("**Body Pos.:**", f"{hand_path}.initial_position")
                l_body_f = mark("**Body Pos.:**", f"{hand_path}.final_position")
                l_space_i = mark("**Space Pos.:**", f"{hand_path}.initial_position")
                l_space_f = mark("**Space Pos.:**", f"{hand_path}.final_position")
                l_hand_or_i = mark("**Hand Orient.:**", f"{hand_path}.initial_orientation")
                l_hand_or_f = mark("**Hand Orient.:**", f"{hand_path}.final_orientation")
                l_arm_or_i = mark("**Arm Orient.:**", f"{hand_path}.initial_orientation")
                l_arm_or_f = mark("**Arm Orient.:**", f"{hand_path}.final_orientation")

                l_mov = mark("**Movement:**", f"{hand_path}.movement")
                if not mov.get('manner') and not mov.get('path') and not mov.get('contact', False) and not mov.get('repetition', False):
                    mov_str = "`None`"
                else:
                    mov_str = (
                        f"Manner: `{', '.join(mov.get('manner', [])) or 'None'}` | "
                        f"Path: `{', '.join(mov.get('path', [])) or 'None'}` | "
                        f"Contact: `{'Yes' if mov.get('contact', False) else 'No'}` | "
                        f"Repetition: `{'Yes' if mov.get('repetition', False) else 'No'}`"
                    )

                col_init, col_final = st.columns(2)
                with col_init:
                    st.markdown("**🔹 Initial**")
                    st.markdown(
                        f"{l_conf_i} `{ic}`\n\n"
                        f"{l_body_i} `{ip_body}`\n\n"
                        f"{l_space_i} `{ip_space}`\n\n"
                        f"{l_hand_or_i} `{io_hand}`\n\n"
                        f"{l_arm_or_i} `{io_arm}`"
                    )
                with col_final:
                    st.markdown("**🔸 Final**")
                    if has_final:
                        st.markdown(
                            f"{l_conf_f} `{fc or 'None'}`\n\n"
                            f"{l_body_f} `{fp_body}`\n\n"
                            f"{l_space_f} `{fp_space}`\n\n"
                            f"{l_hand_or_f} `{fo_hand}`\n\n"
                            f"{l_arm_or_f} `{fo_arm}`"
                        )
                    else:
                        st.markdown("`N/A`")

                st.markdown(f"{l_mov} {mov_str}")

            render_hand_ro("✋ Dominant Hand:", dom, f"{base_path}.dominant_hand")

            has_non_dom = non_dom is not None and any([
                non_dom.get("initial_configuration"),
                non_dom.get("final_configuration"),
                non_dom.get("movement"),
                non_dom.get("initial_position", {}).get("body"),
                non_dom.get("initial_position", {}).get("space"),
                non_dom.get("final_position", {}).get("body"),
                non_dom.get("final_position", {}).get("space"),
                non_dom.get("initial_orientation"),
                non_dom.get("final_orientation")
            ])

            if has_non_dom:
                render_hand_ro("🤚 Non-Dominant Hand:", non_dom, f"{base_path}.non_dominant_hand")

            st.markdown("##### 👤 Non-Manual Components (NMC):")
            nmc = comp.get("non_manual_components", {})
            fe_lbl = mark("**Facial Expression:**", f"{base_path}.non_manual_components.facial_expression")
            nm_lbl = mark("**Non-Manual Movement:**", f"{base_path}.non_manual_components.body_movement")

            facial_val = ", ".join(nmc.get('facial_expression', [])) or 'None'
            mov_nmc_val = ", ".join(nmc.get('body_movement', [])) or 'None'

            st.markdown(
                f"{fe_lbl} `{facial_val}`\n\n"
                f"{nm_lbl} `{mov_nmc_val}`\n\n"
                f"**Textual NMC:** `{nmc.get('nmc_text', 'None')}`"
            )
            st.divider()

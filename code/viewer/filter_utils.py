import streamlit as st

def get_filter_options(schema):
    defs = schema.get("definitions", {})
    
    def get_enum(def_key):
        enum_list = defs.get(def_key, {}).get("enum", [])
        return [e for e in enum_list if e is not None]

    handshapes = get_enum("handshape_enum")
    move_manners = get_enum("hand_movement_manner_enum")
    move_paths = get_enum("hand_movement_path_enum")
    locations = get_enum("body_location_enum") + get_enum("space_location_enum")
    orientations = get_enum("hand_orientation_enum") + get_enum("arm_orientation_enum")
    nmcs = get_enum("nmc_facial_enum") + get_enum("nmc_body_movement_enum")
    
    return {
        "handshapes": sorted(list(set(handshapes))),
        "move_manners": sorted(list(set(move_manners))),
        "move_paths": sorted(list(set(move_paths))),
        "locations": sorted(list(set(locations))),
        "orientations": sorted(list(set(orientations))),
        "nmcs": sorted(list(set(nmcs)))
    }

def render_filters(schema):
    options = get_filter_options(schema)
    filters = {}
    
    filters["sort_option"] = st.radio("Sort Order:", options=["ID", "Spanish W."], horizontal=True)
    filters["min_confidence"] = st.slider("Max Confidence Threshold:", 1, 20, 20)
    
    filters["human_verif"] = st.slider("Human Verification Level:", 0, 5, (0, 5))
    
    filters["handshape"] = st.multiselect("Hand Shape:", options=options["handshapes"])
    
    filters["move_manner"] = st.multiselect("Movement Manner:", options=options["move_manners"])
    filters["move_path"] = st.multiselect("Movement Path:", options=options["move_paths"])
    
    col1, col2 = st.columns(2)
    with col1:
        filters["contact"] = st.selectbox("Contact:", options=["Any", "Yes", "No"])
    with col2:
        filters["repetition"] = st.selectbox("Repetition:", options=["Any", "Yes", "No"])
        
    filters["location"] = st.multiselect("Location:", options=options["locations"])
    filters["orientation"] = st.multiselect("Orientation:", options=options["orientations"])
    filters["nmc"] = st.multiselect("NMC:", options=options["nmcs"])
    
    return filters

def apply_filters(all_signs, filters, search_query):
    filtered = []
    
    for s in all_signs:
        ocr_data = s.get("ocr_data", {})
        
        if (ocr_data.get("ocr_confidence") or 20) > filters["min_confidence"] and \
           (ocr_data.get("translation_confidence") or 20) > filters["min_confidence"]:
            continue
            
        verif_level = ocr_data.get("human_verification_level") or 0
        if not (filters["human_verif"][0] <= verif_level <= filters["human_verif"][1]):
            continue
            
        if search_query:
            sq = search_query.lower()
            if sq not in s.get("spanish_word", "").lower() and sq not in s.get("sign_id", "").lower():
                continue
                
        if any([
            filters["handshape"], 
            filters["move_manner"], 
            filters["move_path"], 
            filters["contact"] != "Any",
            filters["repetition"] != "Any",
            filters["location"], 
            filters["orientation"], 
            filters["nmc"]
        ]):
            if not _check_phonology(s, filters):
                continue
        
        filtered.append(s)
        
    if filters["sort_option"] == "ID":
        filtered = sorted(filtered, key=lambda x: x.get("sign_id", ""))
    else:
        filtered = sorted(filtered, key=lambda x: x.get("spanish_word", "").lower())
        
    return filtered

def _check_phonology(sign, filters):
    sign_handshapes = set()
    sign_move_manners = set()
    sign_move_paths = set()
    sign_contacts = set()
    sign_reps = set()
    sign_locations = set()
    sign_orientations = set()
    sign_nmcs = set()
    
    variants = sign.get("sign_variants", [])
    for v in variants:
        for comp in v.get("sequential_components", []):
            
            nmc = comp.get("non_manual_components", {})
            sign_nmcs.update(nmc.get("facial_expression", []))
            sign_nmcs.update(nmc.get("body_movement", []))
            
            for hand_key in ["dominant_hand", "non_dominant_hand"]:
                hand = comp.get(hand_key)
                if not hand:
                    continue
                
                sign_handshapes.add(hand.get("initial_configuration"))
                sign_handshapes.add(hand.get("final_configuration"))
                
                mov = hand.get("movement", {})
                sign_move_manners.update(mov.get("manner", []))
                sign_move_paths.update(mov.get("path", []))
                if "contact" in mov:
                    sign_contacts.add(mov["contact"])
                if "repetition" in mov:
                    sign_reps.add(mov["repetition"])
                
                init_pos = hand.get("initial_position", {})
                sign_locations.update(init_pos.get("body", []))
                sign_locations.update(init_pos.get("space", []))
                
                fin_pos = hand.get("final_position", {})
                sign_locations.update(fin_pos.get("body", []))
                sign_locations.update(fin_pos.get("space", []))
                
                init_ori = hand.get("initial_orientation", {})
                sign_orientations.update(init_ori.get("hand", []))
                sign_orientations.update(init_ori.get("arm", []))

                fin_ori = hand.get("final_orientation", {})
                sign_orientations.update(fin_ori.get("hand", []))
                sign_orientations.update(fin_ori.get("arm", []))
                
    sign_handshapes.discard(None)
    
    if filters["handshape"] and not set(filters["handshape"]).intersection(sign_handshapes):
        return False
        
    if filters["move_manner"] and not set(filters["move_manner"]).intersection(sign_move_manners):
        return False
        
    if filters["move_path"] and not set(filters["move_path"]).intersection(sign_move_paths):
        return False
        
    if filters["contact"] != "Any":
        wants_contact = filters["contact"] == "Yes"
        if wants_contact not in sign_contacts:
            return False
            
    if filters["repetition"] != "Any":
        wants_rep = filters["repetition"] == "Yes"
        if wants_rep not in sign_reps:
            return False
            
    if filters["location"] and not set(filters["location"]).intersection(sign_locations):
        return False
        
    if filters["orientation"] and not set(filters["orientation"]).intersection(sign_orientations):
        return False
        
    if filters["nmc"] and not set(filters["nmc"]).intersection(sign_nmcs):
        return False
        
    return True

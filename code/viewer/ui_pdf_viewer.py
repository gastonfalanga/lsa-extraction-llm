import os
import sys
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def render_pdf_preview(current_sign):
    
    ocr_data = current_sign.get("ocr_data", {})
    batch_file = ocr_data.get("source_batch_file")
    current_page_ocr = ocr_data.get("source_page_ocr")
    pos_on_page = ocr_data.get("sign_index_on_page")
    
    if not batch_file or current_page_ocr is None or not pos_on_page:
        st.warning("Missing Batch File, OCR Page, or Sign Index to render preview.")
        return

    try:
        from io_utils import load_all_signs
        all_signs = load_all_signs()
        batch_signs = [s for s in all_signs if s.get("ocr_data", {}).get("source_batch_file") == batch_file]
        
        unique_pages = sorted(list(set(
            s.get("ocr_data", {}).get("source_page_ocr") 
            for s in batch_signs 
            if s.get("ocr_data", {}).get("source_page_ocr") is not None
        )))
        
        if current_page_ocr not in unique_pages:
            st.error(f"Page {current_page_ocr} not found in batch {batch_file}.")
            return
            
        pdf_page_index = unique_pages.index(current_page_ocr)
        
        signs_on_this_page = [s for s in batch_signs if s.get("ocr_data", {}).get("source_page_ocr") == current_page_ocr]
        total_slots = max([s.get("ocr_data", {}).get("sign_index_on_page", 1) for s in signs_on_this_page])
        
        if total_slots < 1: total_slots = 3  
        
    except Exception as e:
        st.warning(f"Could not compute page index dynamically: {e}")
        return

    raw_dir = os.path.abspath(os.path.join(ROOT_DIR, "data", "raw"))
    pdf_path = os.path.join(raw_dir, batch_file)

    if not os.path.exists(pdf_path):
        st.error(f"PDF not found locally at: `data/raw/{batch_file}`")
        return

    try:
        import fitz
        from PIL import Image
        
        doc = fitz.open(pdf_path)
        if pdf_page_index >= len(doc):
            st.error(f"Calculated page index ({pdf_page_index}) is out of bounds for {batch_file}.")
            doc.close()
            return
            
        page = doc.load_page(pdf_page_index)
        
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        width, height = img.size
        
        HEADER_MARGIN_PCT = 0.095  
        FOOTER_MARGIN_PCT = 0.075  
        
        content_top = int(height * HEADER_MARGIN_PCT)
        content_bottom = int(height * (1 - FOOTER_MARGIN_PCT))
        content_height = content_bottom - content_top
        
        segment_height = content_height // total_slots
        
        top = content_top + ((pos_on_page - 1) * segment_height)
        bottom = content_top + (pos_on_page * segment_height)
        
        padding = int(segment_height * 0.05)
        top = max(0, top - padding)        
        bottom = min(height, bottom + padding) 
        
        cropped_img = img.crop((0, top, width, bottom))
        
        st.image(
            cropped_img, 
            caption=f"Printed Page: {current_page_ocr} | Position: {pos_on_page}/{total_slots}",
            width='stretch'
        )
        
        with st.expander(f"📄 Full page ({batch_file})"):
            st.image(
                img, 
                caption=f"Full printed page: {current_page_ocr} | PDF Index: {pdf_page_index + 1}",
                width='stretch'
            )
            
        doc.close()
        
    except ImportError:
        st.error("⚠️ **Missing Dependency:** Please run `pip install PyMuPDF pillow` to enable the visualizer.")
    except Exception as e:
        st.error(f"Error rendering PDF: {e}")


def render_image_crop_tab(current_sign):
    st.markdown("### Interactive Image Cropper")
    st.caption("Fine-tune the auto-calculated boundaries using the sliders, then save the final image.")
    
    ocr_data = current_sign.get("ocr_data", {})
    batch_file = ocr_data.get("source_batch_file")
    current_page_ocr = ocr_data.get("source_page_ocr")
    pos_on_page = ocr_data.get("sign_index_on_page")
    sign_id = current_sign.get("sign_id")
    
    if not batch_file or current_page_ocr is None or not pos_on_page:
        st.info("Missing OCR data (Batch File, Page, or Index) required to calculate the crop.")
        return

    try:
        from io_utils import load_all_signs
        all_signs = load_all_signs()
        batch_signs = [s for s in all_signs if s.get("ocr_data", {}).get("source_batch_file") == batch_file]
        
        unique_pages = sorted(list(set(
            s.get("ocr_data", {}).get("source_page_ocr") 
            for s in batch_signs 
            if s.get("ocr_data", {}).get("source_page_ocr") is not None
        )))
        
        if current_page_ocr not in unique_pages:
            st.error("Page not found in batch.")
            return
            
        pdf_page_index = unique_pages.index(current_page_ocr)
        
        signs_on_this_page = [s for s in batch_signs if s.get("ocr_data", {}).get("source_page_ocr") == current_page_ocr]
        total_slots = max([s.get("ocr_data", {}).get("sign_index_on_page", 1) for s in signs_on_this_page])
        
        if total_slots < 1: total_slots = 3  
        
    except Exception as e:
        st.error(f"Could not compute page index: {e}")
        return

    raw_dir = os.path.abspath(os.path.join(ROOT_DIR, "data", "raw"))
    pdf_path = os.path.join(raw_dir, batch_file)

    if not os.path.exists(pdf_path):
        st.error(f"PDF not found locally at: `data/raw/{batch_file}`")
        return

    try:
        import fitz  
        from PIL import Image
        
        doc = fitz.open(pdf_path)
        if pdf_page_index >= len(doc):
            st.error("Calculated page index is out of bounds.")
            doc.close()
            return
            
        page = doc.load_page(pdf_page_index)
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        
        width, height = img.size
        
        HEADER_MARGIN_PCT = 0.095  
        FOOTER_MARGIN_PCT = 0.075  
        
        content_top = int(height * HEADER_MARGIN_PCT)
        content_bottom = int(height * (1 - FOOTER_MARGIN_PCT))
        content_height = content_bottom - content_top
        
        segment_height = content_height // total_slots
        
        top_bound = content_top + ((pos_on_page - 1) * segment_height)
        bottom_bound = content_top + (pos_on_page * segment_height)
        
        padding = int(segment_height * 0.05)
        
        default_left = 0
        default_right = width
        default_top = max(0, top_bound - padding)        
        default_bottom = min(height, bottom_bound + padding)
        
        st.markdown("##### 1. Fine-Tune Boundaries")
        
        assets_dir = os.path.join(ROOT_DIR, "assets")
        out_path = os.path.join(assets_dir, f"{sign_id}.png")
        
        if os.path.exists(out_path):
            st.warning(f"ℹ️ `assets/{sign_id}.png` already exists. Saving will overwrite the previous image.")
                    
        horiz_bounds = st.slider(
            "Horizontal Bounds (Left / Right)", 
            0, width, 
            (default_left, default_right), 
            key=f"crop_h_{sign_id}"
        )
        vert_bounds = st.slider(
            "Vertical Bounds (Top / Bottom)", 
            0, height, 
            (default_top, default_bottom), 
            key=f"crop_v_{sign_id}"
        )
        
        left, right = horiz_bounds
        top, bottom = vert_bounds
        
        if left == right: right += 1
        if top == bottom: bottom += 1

        cropped_img = img.crop((left, top, right, bottom))
        
        st.markdown("##### 2. Final Preview")
        st.image(cropped_img, caption=f"Preview of {sign_id}.png", width="stretch")
        
        if st.button("✂️ Crop & Save Image", type="primary", use_container_width=True):
            os.makedirs(assets_dir, exist_ok=True)
            cropped_img.save(out_path, format="PNG")
            st.success(f"✅ Image successfully saved to `{out_path}`")
            
    except Exception as e:
        st.error(f"Error processing image: {e}")


def render_image_upload_tab(current_sign):
    sign_id = current_sign.get("sign_id")
    
    st.markdown("### Upload Edited Image")
    st.caption("If you edited or cropped the image outside this application, you can upload it here. It will automatically be converted to PNG and saved with the correct ID.")
    
    uploaded_file = st.file_uploader(f"Upload image for {sign_id}", type=["png", "jpg", "jpeg"])
    
    if uploaded_file is not None:
        try:
            from PIL import Image
            img = Image.open(uploaded_file)
            
            assets_dir = os.path.join(ROOT_DIR, "assets")
            out_path = os.path.join(assets_dir, f"{sign_id}.png")
            
            if os.path.exists(out_path):
                st.info(f"ℹ️ `assets/{sign_id}.png` already exists. Saving will overwrite the previous image.")
                
            if st.button("💾 Save Uploaded Image", type="primary", use_container_width=True):
                os.makedirs(assets_dir, exist_ok=True)
                img.save(out_path, format="PNG")
                st.success(f"✅ Uploaded image successfully saved to `{out_path}`")            
            st.markdown("##### Preview")
            st.image(img, caption="Image ready to be saved", width="stretch")
            

        except Exception as e:
            st.error(f"Error processing uploaded image: {e}")

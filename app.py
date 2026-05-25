import streamlit as st
from PIL import Image
import fitz

st.set_page_config(
    page_title="排樁圖檢視系統",
    layout="wide"
)

st.title("📂 排樁圖檢視系統")

uploaded_file = st.file_uploader(
    "請上傳 JPG / PNG / PDF",
    type=["jpg", "jpeg", "png", "pdf"]
)

if uploaded_file is not None:

    file_type = uploaded_file.type

    # 圖片顯示
    if file_type in ["image/jpeg", "image/png"]:

        image = Image.open(uploaded_file)

        st.image(
            image,
            caption="上傳的圖面",
            use_container_width=True
        )

    # PDF 顯示
    elif file_type == "application/pdf":

        pdf_bytes = uploaded_file.read()

        pdf_document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        st.success(f"PDF 共 {len(pdf_document)} 頁")

        for page_num in range(len(pdf_document)):

            page = pdf_document.load_page(page_num)

            pix = page.get_pixmap()

            img_bytes = pix.tobytes("png")

            st.image(
                img_bytes,
                caption=f"第 {page_num + 1} 頁",
                use_container_width=True
            )

import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image, ImageDraw
import io
import random
from datetime import datetime, timedelta
import fitz
import cv2

from streamlit_drawable_canvas import st_canvas

# =========================================================
# 頁面設定
# =========================================================

st.set_page_config(
    page_title="AI 排樁施工系統",
    layout="wide"
)

# =========================================================
# 顏色產生器（不重複）
# =========================================================

def generate_random_colors(n):

    colors = []

    while len(colors) < n:

        color = "#{:06x}".format(random.randint(0, 0xFFFFFF))

        if color not in colors:
            colors.append(color)

    return colors

# =========================================================
# PDF轉圖片
# =========================================================

def pdf_to_image(uploaded_file):

    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")

    page = pdf.load_page(0)

    pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))

    img = Image.frombytes(
        "RGB",
        [pix.width, pix.height],
        pix.samples
    )

    return img

# =========================================================
# AI辨識樁位
# =========================================================

def detect_piles(img_pil, roi=None):

    img = np.array(img_pil)

    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    if roi is not None:

        x, y, w, h = roi

        crop = img[y:y+h, x:x+w]

    else:

        x, y = 0, 0

        crop = img

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    blur = cv2.GaussianBlur(gray, (5, 5), 1)

    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=40,
        param1=50,
        param2=20,
        minRadius=10,
        maxRadius=30
    )

    pile_positions = []

    if circles is not None:

        circles = np.round(circles[0, :]).astype("int")

        radii = [c[2] for c in circles]

        avg_r = np.mean(radii)

        pile_id = 1

        for (cx, cy, r) in circles:

            if abs(r - avg_r) > 5:
                continue

            pile_positions.append({
                "pile": pile_id,
                "x": cx + x,
                "y": cy + y,
                "r": int(avg_r)
            })

            pile_id += 1

    # 排序
    pile_positions = sorted(
        pile_positions,
        key=lambda p: (p["y"], p["x"])
    )

    # 重編號
    for i, p in enumerate(pile_positions):
        p["pile"] = i + 1

    return pile_positions

# =========================================================
# 排程
# =========================================================

def generate_schedule(
    piles,
    daily_count,
    cycle
):

    total_piles = len(piles)

    total_days = int(np.ceil(total_piles / daily_count))

    schedule = []

    start_date = datetime.today()

    groups = [[] for _ in range(cycle)]

    for i, pile in enumerate(piles):

        groups[i % cycle].append(pile)

    ordered = []

    max_len = max(len(g) for g in groups)

    for i in range(max_len):

        for g in groups:

            if i < len(g):
                ordered.append(g[i])

    colors = generate_random_colors(total_days)

    for day in range(total_days):

        start = day * daily_count
        end = start + daily_count

        day_piles = ordered[start:end]

        schedule.append({
            "day": f"Day {day+1}",
            "date": (
                start_date +
                timedelta(days=day)
            ).strftime("%Y-%m-%d"),
            "color": colors[day],
            "piles": [p["pile"] for p in day_piles],
            "pile_objects": day_piles
        })

    return schedule

# =========================================================
# 繪製圖面
# =========================================================

def draw_schedule_image(image, schedule):

    result = image.copy()

    draw = ImageDraw.Draw(result)

    for day in schedule:

        color = day["color"]

        for pile in day["pile_objects"]:

            x = pile["x"]
            y = pile["y"]
            r = pile["r"]

            draw.ellipse(
                (
                    x-r,
                    y-r,
                    x+r,
                    y+r
                ),
                fill=color,
                outline=color
            )

    return result

# =========================================================
# Session State
# =========================================================

if "result_image" not in st.session_state:
    st.session_state.result_image = None

if "schedule_df" not in st.session_state:
    st.session_state.schedule_df = None

if "schedule_data" not in st.session_state:
    st.session_state.schedule_data = None

# =========================================================
# 標題
# =========================================================

st.title("🏗️ AI 排樁施工系統")

# =========================================================
# 上傳
# =========================================================

uploaded_file = st.file_uploader(
    "上傳 JPG / PNG / PDF 圖面",
    type=["png", "jpg", "jpeg", "pdf"]
)

if uploaded_file:

    # =====================================================
    # 讀取圖面
    # =====================================================

    if uploaded_file.type == "application/pdf":

        image = pdf_to_image(uploaded_file)

    else:

        image = Image.open(uploaded_file).convert("RGB")

    st.image(image, caption="原始圖面")

    # =====================================================
    # 框選區域
    # =====================================================

    st.subheader("✏️ 框選施工區域")

    canvas_result = st_canvas(
        fill_color="rgba(255,0,0,0.1)",
        stroke_width=3,
        stroke_color="red",
        background_image=image,
        update_streamlit=True,
        height=image.height,
        width=image.width,
        drawing_mode="rect",
        key="canvas"
    )

    # =====================================================
    # 有框選後才顯示施工條件
    # =====================================================

    if (
        canvas_result.json_data and
        len(canvas_result.json_data["objects"]) > 0
    ):

        rect = canvas_result.json_data["objects"][-1]

        roi = (
            int(rect["left"]),
            int(rect["top"]),
            int(rect["width"]),
            int(rect["height"])
        )

        piles = detect_piles(image, roi)

        st.success(f"AI辨識 {len(piles)} 支樁體")

        # =================================================
        # 施工條件
        # =================================================

        st.header("📅 施工條件設定")

        col1, col2 = st.columns(2)

        with col1:

            start_date = st.date_input(
                "施工開始日期"
            )

        with col2:

            daily_count = st.number_input(
                "每日施工支數",
                min_value=1,
                value=10
            )

        cycle = st.selectbox(
            "幾支樁一循環",
            [2, 3, 4, 5, 6, 7, 8]
        )

        # =================================================
        # 執行排程
        # =================================================

        if st.button("🚀 執行排程"):

            schedule = generate_schedule(
                piles,
                daily_count,
                cycle
            )

            # =============================================
            # DataFrame
            # =============================================

            schedule_df = pd.DataFrame({
                "施工日": [
                    s["day"] for s in schedule
                ],
                "日期": [
                    s["date"] for s in schedule
                ],
                "日期顏色": [
                    s["color"] for s in schedule
                ],
                "施工樁號": [
                    ",".join(map(str, s["piles"]))
                    for s in schedule
                ]
            })

            st.session_state.schedule_df = schedule_df

            st.session_state.schedule_data = schedule

            # =============================================
            # 繪圖
            # =============================================

            result_img = draw_schedule_image(
                image,
                schedule
            )

            st.session_state.result_image = result_img

# =========================================================
# 顯示結果
# =========================================================

if st.session_state.schedule_df is not None:

    st.header("📋 施工排程結果")

    st.dataframe(
        st.session_state.schedule_df,
        use_container_width=True
    )

    # =====================================================
    # 顏色說明
    # =====================================================

    st.header("🎨 顏色說明")

    for i, row in st.session_state.schedule_df.iterrows():

        color = row["日期顏色"]

        st.markdown(
            f"""
            <div style="
                display:flex;
                align-items:center;
                gap:10px;
                margin-bottom:10px;
            ">
                <div style="
                    width:25px;
                    height:25px;
                    border-radius:50%;
                    background:{color};
                "></div>

                <div style="
                    font-size:18px;
                    font-weight:bold;
                ">
                    {row["施工日"]} - {color}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# =========================================================
# 顯示排樁圖
# =========================================================

if st.session_state.result_image is not None:

    st.header("🗺️ 排樁施工圖")

    st.image(
        st.session_state.result_image,
        use_container_width=True
    )

    # =====================================================
    # 檔名
    # =====================================================

    filename = st.text_input(
        "下載檔案名稱",
        value="pile_schedule"
    )

    # =====================================================
    # 下載
    # =====================================================

    img_buffer = io.BytesIO()

    st.session_state.result_image.save(
        img_buffer,
        format="PNG"
    )

    st.download_button(
        label="📥 下載排程圖面",
        data=img_buffer.getvalue(),
        file_name=f"{filename}.png",
        mime="image/png"
    )

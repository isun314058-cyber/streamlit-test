import streamlit as st
from PIL import Image, ImageDraw
import pandas as pd
import numpy as np
import random
import io
import cv2
from streamlit_drawable_canvas import st_canvas

# ============================================
# 頁面設定
# ============================================

st.set_page_config(
    page_title="AI 排樁施工系統",
    layout="wide"
)

st.title("🏗️ AI 排樁施工系統")

# ============================================
# Session State
# ============================================

if "result_image" not in st.session_state:
    st.session_state.result_image = None

if "schedule_df" not in st.session_state:
    st.session_state.schedule_df = None

if "pile_positions" not in st.session_state:
    st.session_state.pile_positions = []

if "uploaded" not in st.session_state:
    st.session_state.uploaded = False

# ============================================
# 上傳圖面
# ============================================

uploaded_file = st.file_uploader(
    "上傳 JPG / PNG / PDF 圖面",
    type=["jpg", "jpeg", "png"]
)

# ============================================
# 顏色產生器（不重複）
# ============================================

def generate_unique_colors(n):
    colors = []

    while len(colors) < n:
        color = (
            random.randint(30, 255),
            random.randint(30, 255),
            random.randint(30, 255)
        )

        if color not in colors:
            colors.append(color)

    return colors

# ============================================
# AI辨識樁體
# ============================================

def detect_piles(pil_image, roi=None):

    img = np.array(pil_image)

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    if roi:

        x1, y1, x2, y2 = roi

        gray_roi = gray[y1:y2, x1:x2]

        circles = cv2.HoughCircles(
            gray_roi,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=25,
            param1=50,
            param2=18,
            minRadius=6,
            maxRadius=18
        )

        positions = []

        if circles is not None:

            circles = np.round(circles[0, :]).astype("int")

            for (x, y, r) in circles:

                positions.append(
                    (x + x1, y + y1, r)
                )

        return positions

    else:

        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=25,
            param1=50,
            param2=18,
            minRadius=6,
            maxRadius=18
        )

        positions = []

        if circles is not None:

            circles = np.round(circles[0, :]).astype("int")

            for (x, y, r) in circles:

                positions.append((x, y, r))

        return positions

# ============================================
# 排程邏輯
# ============================================

def create_schedule(
    total_piles,
    start_no,
    daily_count,
    cycle
):

    pile_numbers = list(range(start_no, start_no + total_piles))

    groups = [[] for _ in range(cycle)]

    for idx, pile in enumerate(pile_numbers):
        groups[idx % cycle].append(pile)

    result = []

    day = 1

    for group in groups:

        for i in range(0, len(group), daily_count):

            result.append({
                "施工日": f"Day {day}",
                "日期顏色": "",
                "施工樁號": group[i:i+daily_count]
            })

            day += 1

    return result

# ============================================
# 主程式
# ============================================

if uploaded_file:

    st.session_state.uploaded = True

    image = Image.open(uploaded_file).convert("RGBA")

    st.subheader("✏️ 框選施工區域")

    canvas_result = st_canvas(
        fill_color="rgba(255,0,0,0.08)",
        stroke_width=3,
        stroke_color="#ff0000",
        background_image=image,
        update_streamlit=True,
        drawing_mode="rect",
        height=image.height,
        width=image.width,
        key="canvas"
    )

    # ============================================
    # 取得框選區域
    # ============================================

    roi = None

    if canvas_result.json_data is not None:

        objects = canvas_result.json_data["objects"]

        if len(objects) > 0:

            rect = objects[-1]

            left = int(rect["left"])
            top = int(rect["top"])

            width = int(rect["width"] * rect["scaleX"])
            height = int(rect["height"] * rect["scaleY"])

            roi = (
                left,
                top,
                left + width,
                top + height
            )

    # ============================================
    # 施工條件
    # ============================================

    if roi:

        st.success("已框選施工區域")

        st.subheader("📅 施工條件設定")

        col1, col2 = st.columns(2)

        with col1:

            start_date = st.date_input("施工開始日期")

            daily_count = st.number_input(
                "每日施工支數",
                min_value=1,
                value=10
            )

        with col2:

            start_no = st.number_input(
                "起始樁號",
                min_value=1,
                value=1
            )

            cycle = st.selectbox(
                "幾支樁一循環",
                [3,4,5,6,7,8]
            )

        # ============================================
        # 執行排程
        # ============================================

        if st.button("🚀 執行排程"):

            piles = detect_piles(image, roi)

            st.session_state.pile_positions = piles

            total_piles = len(piles)

            st.success(f"AI辨識 {total_piles} 支樁體")

            schedule = create_schedule(
                total_piles,
                start_no,
                daily_count,
                cycle
            )

            colors = generate_unique_colors(len(schedule))

            color_names = []

            for i, row in enumerate(schedule):

                c = colors[i]

                hex_color = '#%02x%02x%02x' % c

                row["日期顏色"] = hex_color

                color_names.append(hex_color)

            df = pd.DataFrame(schedule)

            st.session_state.schedule_df = df

            # ============================================
            # 繪製排樁圖
            # ============================================

            draw_img = image.copy()

            draw = ImageDraw.Draw(draw_img)

            pile_positions = piles

            for i, row in df.iterrows():

                color = colors[i]

                piles_today = row["施工樁號"]

                for pile_no in piles_today:

                    idx = pile_no - start_no

                    if idx >= len(pile_positions):
                        continue

                    x, y, r = pile_positions[idx]

                    rr = int(r * 0.9)

                    draw.ellipse(
                        (
                            x - rr,
                            y - rr,
                            x + rr,
                            y + rr
                        ),
                        fill=color
                    )

            st.session_state.result_image = draw_img

# ============================================
# 顯示施工結果
# ============================================

if st.session_state.schedule_df is not None:

    st.subheader("📋 施工排程結果")

    show_df = st.session_state.schedule_df.copy()

    show_df["施工樁號"] = show_df["施工樁號"].apply(
        lambda x: ", ".join(map(str, x))
    )

    st.dataframe(
        show_df,
        use_container_width=True
    )

    # ============================================
    # 顏色說明
    # ============================================

    st.subheader("🎨 顏色說明")

    for i, row in st.session_state.schedule_df.iterrows():

        color = row["日期顏色"]

        st.markdown(
            f"""
            <div style="
                display:flex;
                align-items:center;
                margin-bottom:10px;
            ">
                <div style="
                    width:25px;
                    height:25px;
                    border-radius:50%;
                    background:{color};
                    margin-right:10px;
                    border:1px solid white;
                "></div>

                <div>
                    {row['施工日']} - {color}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# ============================================
# 顯示圖面
# ============================================

if st.session_state.result_image is not None:

    st.subheader("🗺️ 排樁施工圖")

    st.image(
        st.session_state.result_image,
        use_container_width=True
    )

    # ============================================
    # 下載圖片
    # ============================================

    col1, col2 = st.columns([3,1])

    with col1:

        filename = st.text_input(
            "下載檔案名稱",
            value="排樁施工圖"
        )

    with col2:

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

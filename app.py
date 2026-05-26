import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from pdf2image import convert_from_bytes

import pandas as pd
import numpy as np
import random
import io
import cv2

from streamlit_image_coordinates import streamlit_image_coordinates

# =====================================================
# 頁面設定
# =====================================================

st.set_page_config(
    page_title="AI 排樁施工系統",
    layout="wide"
)

# =====================================================
# 深色模式
# =====================================================

st.markdown("""
<style>

.stApp{
    background-color:#020617;
    color:white;
}

h1,h2,h3,h4,h5,h6,p,span,label{
    color:white;
}

.stButton>button{
    border-radius:12px;
    height:50px;
    font-size:20px;
    font-weight:bold;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# Title
# =====================================================

st.title("🏗️ AI 排樁施工系統")

# =====================================================
# Session State
# =====================================================

DEFAULT_STATES = {
    "result_image": None,
    "schedule_df": None,
    "pile_positions": [],
    "processed": False,
    "original_image": None,
    "points": [],
    "last_clicked": None
}

for key, value in DEFAULT_STATES.items():

    if key not in st.session_state:
        st.session_state[key] = value

# =====================================================
# 點位顏色
# =====================================================

POINT_COLORS = [
    ("左上", "red"),
    ("左下", "blue"),
    ("右上", "orange"),
    ("右下", "lime")
]

COLOR_TEXT = {
    "red": "紅色",
    "blue": "藍色",
    "orange": "橘色",
    "lime": "綠色"
}

# =====================================================
# 隨機顏色
# =====================================================

def generate_unique_colors(n):

    colors = []

    while len(colors) < n:

        color = (
            random.randint(50, 255),
            random.randint(50, 255),
            random.randint(50, 255)
        )

        if color not in colors:
            colors.append(color)

    return colors

# =====================================================
# AI辨識樁位
# =====================================================

def detect_piles(pil_image, roi=None):

    img = np.array(pil_image.convert("RGB"))

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    if roi:

        x1, y1, x2, y2 = roi

        gray = gray[y1:y2, x1:x2]

    gray = cv2.GaussianBlur(gray, (5, 5), 1.5)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=25,
        param1=80,
        param2=18,
        minRadius=8,
        maxRadius=22
    )

    positions = []

    if circles is not None:

        circles = np.round(circles[0, :]).astype("int")

        filtered = []

        for (x, y, r) in circles:

            if roi:
                x += x1
                y += y1

            duplicated = False

            for fx, fy, fr in filtered:

                dist = ((x - fx) ** 2 + (y - fy) ** 2) ** 0.5

                # 修正重複辨識
                if dist < 25:
                    duplicated = True
                    break

            if not duplicated:
                filtered.append((x, y, r))

        # =====================================================
        # 正確排序
        # 左上 → 右上
        # 再往下
        # =====================================================

        row_tolerance = 40

        filtered = sorted(filtered, key=lambda p: p[1])

        grouped_rows = []

        for circle in filtered:

            placed = False

            for row in grouped_rows:

                if abs(circle[1] - row[0][1]) < row_tolerance:
                    row.append(circle)
                    placed = True
                    break

            if not placed:
                grouped_rows.append([circle])

        final_sorted = []

        for row in grouped_rows:

            row = sorted(row, key=lambda p: p[0])

            final_sorted.extend(row)

        positions = final_sorted

    return positions

# =====================================================
# 新版排程邏輯
# =====================================================

def create_schedule(
    total_piles,
    start_no,
    daily_count,
    cycle,
    start_date
):

    pile_numbers = list(range(start_no, start_no + total_piles))

    remaining = pile_numbers.copy()

    result = []

    day = 1

    colors = generate_unique_colors(300)

    while remaining:

        today = []

        used_mod = set()

        for pile in remaining[:]:

            mod_value = pile % cycle

            # 保留循環區間
            if mod_value in used_mod:
                continue

            # 避開鄰近樁位
            adjacent = False

            for t in today:

                if abs(pile - t) <= 1:
                    adjacent = True
                    break

            if adjacent:
                continue

            today.append(pile)

            used_mod.add(mod_value)

            remaining.remove(pile)

            # 每日盡量排滿
            if len(today) >= daily_count:
                break

        current_date = (
            pd.to_datetime(start_date)
            + pd.Timedelta(days=day - 1)
        )

        color = colors[day - 1]

        hex_color = '#%02x%02x%02x' % color

        result.append({
            "施工日": f"Day {day}",
            "日期": current_date.strftime("%Y-%m-%d"),
            "日期顏色": hex_color,
            "RGB": color,
            "施工樁號": today
        })

        day += 1

    return result

# =====================================================
# 上傳
# =====================================================

uploaded_file = st.file_uploader(
    "上傳 JPG / PNG / PDF 圖面",
    type=["jpg", "jpeg", "png", "pdf"]
)

# =====================================================
# 主流程
# =====================================================

if uploaded_file:

    if uploaded_file.type == "application/pdf":

        pdf_bytes = uploaded_file.read()

        pdf_pages = convert_from_bytes(
            pdf_bytes,
            dpi=300
        )

        image = pdf_pages[0].convert("RGB")

    else:

        image = Image.open(uploaded_file).convert("RGB")

    st.session_state.original_image = image

    MAX_WIDTH = 900
    MAX_HEIGHT = 650

    scale_w = MAX_WIDTH / image.width
    scale_h = MAX_HEIGHT / image.height

    scale = min(scale_w, scale_h)

    display_width = int(image.width * scale)
    display_height = int(image.height * scale)

    scale_x = image.width / display_width
    scale_y = image.height / display_height

    canvas_bg = image.resize(
        (display_width, display_height)
    )

    st.subheader("✏️ 框選施工區域")

    st.markdown("""

✏️ 點選順序

🔴 左上　🔵 左下　🟠 右上　🟢 右下
""")

    left_col, right_col = st.columns([5, 1.3])

    preview_canvas = canvas_bg.copy()

    draw_preview = ImageDraw.Draw(preview_canvas)

    # =====================================================
    # 畫點位
    # =====================================================

    for idx, point in enumerate(st.session_state.points):

        px, py = point

        label, color = POINT_COLORS[idx]

        draw_preview.ellipse(
            (
                px - 10,
                py - 10,
                px + 10,
                py + 10
            ),
            fill=color,
            outline="white",
            width=3
        )

        draw_preview.text(
            (px + 15, py - 15),
            label,
            fill=color
        )

    # =====================================================
    # ROI
    # =====================================================

    roi = None

    if len(st.session_state.points) == 4:

        xs = [p[0] for p in st.session_state.points]
        ys = [p[1] for p in st.session_state.points]

        x1 = min(xs)
        y1 = min(ys)

        x2 = max(xs)
        y2 = max(ys)

        draw_preview.rectangle(
            (
                x1,
                y1,
                x2,
                y2
            ),
            outline="lime",
            width=5
        )

        roi = (
            int(x1 * scale_x),
            int(y1 * scale_y),
            int(x2 * scale_x),
            int(y2 * scale_y)
        )

    # =====================================================
    # 點擊
    # =====================================================

    with left_col:

        coords = streamlit_image_coordinates(
            preview_canvas,
            key=f"pile_roi_selector_{len(st.session_state.points)}"
        )

    if coords is not None:

        clicked_point = (
            coords["x"],
            coords["y"]
        )

        if st.session_state.last_clicked != clicked_point:

            st.session_state.last_clicked = clicked_point

            duplicated = False

            for old_point in st.session_state.points:

                dist = (
                    (clicked_point[0] - old_point[0]) ** 2
                    +
                    (clicked_point[1] - old_point[1]) ** 2
                ) ** 0.5

                if dist < 10:
                    duplicated = True
                    break

            if (
                not duplicated
                and len(st.session_state.points) < 4
            ):

                st.session_state.points.append(clicked_point)

                st.rerun()

    with right_col:

        st.subheader("📍 點位資訊")

        if len(st.session_state.points) == 0:

            st.info("尚未點選")

        else:

            for idx, point in enumerate(st.session_state.points):

                label, color = POINT_COLORS[idx]

                st.markdown(
                    f"""
{label}

顏色：{COLOR_TEXT[color]}
"""
                )

        st.markdown("---")

        if roi:

            st.success("✅ 已完成施工區域")

        if st.button("🔄 重新選取"):

            st.session_state.points = []
            st.session_state.last_clicked = None
            st.session_state.pile_positions = []
            st.session_state.schedule_df = None
            st.session_state.result_image = None
            st.session_state.processed = False

            st.rerun()

    # =====================================================
    # AI辨識
    # =====================================================

    if roi:

        piles = detect_piles(image, roi)

        st.session_state.pile_positions = piles

        total_piles = len(piles)

        st.success(f"✅ AI 辨識到 {total_piles} 支樁體")

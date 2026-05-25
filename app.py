import streamlit as st
from PIL import Image, ImageDraw
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

st.title("🏗️ AI 排樁施工系統")

# =====================================================
# Session State
# =====================================================

DEFAULT_STATES = {
    "result_image": None,
    "schedule_df": None,
    "pile_positions": [],
    "uploaded": False,
    "roi": None,
    "processed": False,
    "original_image": None,
    "points": []
}

for key, value in DEFAULT_STATES.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =====================================================
# 工具函式
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
# AI辨識樁體
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

                if dist < 12:
                    duplicated = True
                    break

            if not duplicated:
                filtered.append((x, y, r))

        filtered = sorted(filtered, key=lambda k: (k[1], k[0]))

        positions = filtered

    return positions

# =====================================================
# 排程邏輯
# =====================================================

def create_schedule(
    total_piles,
    start_no,
    daily_count,
    cycle,
    start_date
):

    pile_numbers = list(range(start_no, start_no + total_piles))

    groups = [[] for _ in range(cycle)]

    for idx, pile in enumerate(pile_numbers):
        groups[idx % cycle].append(pile)

    result = []

    day = 1

    colors = generate_unique_colors(300)

    for group in groups:

        for i in range(0, len(group), daily_count):

            current_date = pd.to_datetime(start_date) + pd.Timedelta(days=day - 1)

            color = colors[day - 1]

            hex_color = '#%02x%02x%02x' % color

            result.append({
                "施工日": f"Day {day}",
                "日期": current_date.strftime("%Y-%m-%d"),
                "日期顏色": hex_color,
                "RGB": color,
                "施工樁號": group[i:i + daily_count]
            })

            day += 1

    return result

# =====================================================
# 上傳圖面
# =====================================================

uploaded_file = st.file_uploader(
    "上傳 JPG / PNG 圖面",
    type=["jpg", "jpeg", "png"]
)

# =====================================================
# 主流程
# =====================================================

if uploaded_file:

    image = Image.open(uploaded_file).convert("RGB")

    st.session_state.original_image = image

    # =====================================================
    # 固定顯示尺寸
    # =====================================================

    MAX_WIDTH = 1400

    scale = MAX_WIDTH / image.width

    display_width = int(image.width * scale)
    display_height = int(image.height * scale)

    scale_x = image.width / display_width
    scale_y = image.height / display_height

    canvas_bg = image.resize(
        (display_width, display_height)
    )

    st.subheader("✏️ 框選施工區域")

    st.info("請依序點選：左上角 → 右下角")

    # =====================================================
    # 顯示圖片
    # =====================================================

    coords = streamlit_image_coordinates(canvas_bg)

    # =====================================================
    # 點擊座標
    # =====================================================

    if coords is not None:

        st.session_state.points.append(
            (coords["x"], coords["y"])
        )

    # =====================================================
    # 顯示點位
    # =====================================================

    if len(st.session_state.points) > 0:

        st.write("已選點位：", st.session_state.points)

    # =====================================================
    # 兩點完成ROI
    # =====================================================

    roi = None

    if len(st.session_state.points) >= 2:

        p1 = st.session_state.points[0]
        p2 = st.session_state.points[1]

        x1 = min(p1[0], p2[0])
        y1 = min(p1[1], p2[1])

        x2 = max(p1[0], p2[0])
        y2 = max(p1[1], p2[1])

        roi = (
            int(x1 * scale_x),
            int(y1 * scale_y),
            int(x2 * scale_x),
            int(y2 * scale_y)
        )

        st.success(f"框選完成 ROI：{roi}")

    # =====================================================
    # AI辨識
    # =====================================================

    if roi:

        piles = detect_piles(image, roi)

        st.session_state.pile_positions = piles

        total_piles = len(piles)

        st.success(f"AI 辨識到 {total_piles} 支樁體")

        preview_img = image.copy()

        preview_draw = ImageDraw.Draw(preview_img)

        for idx, (x, y, r) in enumerate(piles):

            preview_draw.ellipse(
                (
                    x - r,
                    y - r,
                    x + r,
                    y + r
                ),
                outline="red",
                width=3
            )

            preview_draw.text(
                (x + 10, y - 10),
                str(idx + 1),
                fill="red"
            )

        st.image(
            preview_img,
            use_container_width=True
        )

        # =====================================================
        # 施工條件
        # =====================================================

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
                [3, 4, 5, 6, 7, 8]
            )

        estimated_days = int(np.ceil(total_piles / daily_count))

        st.info(f"AI 預估施工天數：約 {estimated_days} 天")

        # =====================================================
        # 執行排程
        # =====================================================

        if st.button("🚀 執行排程"):

            schedule = create_schedule(
                total_piles=total_piles,
                start_no=start_no,
                daily_count=daily_count,
                cycle=cycle,
                start_date=start_date
            )

            df = pd.DataFrame(schedule)

            st.session_state.schedule_df = df

            result_img = image.copy()

            draw = ImageDraw.Draw(result_img)

            pile_positions = piles

            for i, row in df.iterrows():

                color = row["RGB"]

                for pile_no in row["施工樁號"]:

                    idx = pile_no - start_no

                    if idx >= len(pile_positions):
                        continue

                    x, y, r = pile_positions[idx]

                    rr = int(r * 0.85)

                    draw.ellipse(
                        (
                            x - rr,
                            y - rr,
                            x + rr,
                            y + rr
                        ),
                        fill=color,
                        outline="black",
                        width=1
                    )

            st.session_state.result_image = result_img

            st.session_state.processed = True

# =====================================================
# 排程結果
# =====================================================

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

# =====================================================
# 顯示成果圖
# =====================================================

if st.session_state.result_image is not None:

    st.subheader("🗺️ 排樁施工圖")

    st.image(
        st.session_state.result_image,
        use_container_width=True
    )

    # =====================================================
    # 下載
    # =====================================================

    st.subheader("📥 下載圖面")

    img_buffer = io.BytesIO()

    st.session_state.result_image.save(
        img_buffer,
        format="PNG"
    )

    st.download_button(
        label="下載排程圖面",
        data=img_buffer.getvalue(),
        file_name="排樁施工圖.png",
        mime="image/png"
    )

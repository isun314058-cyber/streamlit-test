# =====================================================
# AI 排樁施工系統 完整版
# =====================================================

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
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

.stApp {
    background-color: #050816;
    color: white;
}

h1,h2,h3,h4,h5,h6,p,div,label {
    color: white !important;
}

.stButton button {
    border-radius: 12px;
    height: 45px;
    font-size: 16px;
    font-weight: bold;
}

[data-testid="stDataFrame"] {
    background-color: #111827;
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)

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
    ("第一點", "red"),
    ("第二點", "blue"),
    ("第三點", "orange"),
    ("第四點", "lime")
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
### ✏️ 點選順序

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

    # =====================================================
    # 點位資訊
    # =====================================================

    with right_col:

        st.markdown("## 📍 點位資訊")

        if len(st.session_state.points) == 0:

            st.info("尚未點選")

        else:

            for idx, point in enumerate(st.session_state.points):

                label, color = POINT_COLORS[idx]

                st.markdown(
                    f"""
### {label}

顏色：{COLOR_TEXT[color]}
"""
                )

        st.markdown("---")

        if roi:

            st.success("✅ 已完成施工區域")

        # =====================================================
        # 重新選取
        # =====================================================

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

        # =====================================================
        # AI辨識結果圖
        # =====================================================

        preview_img = image.copy()

        preview_draw = ImageDraw.Draw(preview_img)

        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()

        # =====================================================
        # 畫樁位 + AI編號
        # =====================================================

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
                (
                    x + 12,
                    y - 18
                ),
                str(idx + 1),
                fill="red",
                font=font
            )

        AI_PREVIEW_WIDTH = 900

        scale_ratio = AI_PREVIEW_WIDTH / preview_img.width

        ai_height = int(preview_img.height * scale_ratio)

        preview_display = preview_img.resize(
            (AI_PREVIEW_WIDTH, ai_height)
        )

        ai_col, setting_col = st.columns([4, 1.2])

        with ai_col:

            st.subheader("🔍 AI辨識結果")

            st.image(
                preview_display,
                use_container_width=False
            )

        with setting_col:

            st.subheader("📅 施工條件")

            start_date = st.date_input("施工開始日期")

            daily_count = st.number_input(
                "每日施工支數",
                min_value=1,
                value=10
            )

            start_no = st.number_input(
                "起始樁號",
                min_value=1,
                value=1
            )

            cycle = st.selectbox(
                "循環間隔",
                [3, 4, 5, 6, 7, 8]
            )

            execute = st.button(
                "🚀 執行排程",
                use_container_width=True
            )

        if execute:

            schedule = create_schedule(
                total_piles=total_piles,
                start_no=start_no,
                daily_count=daily_count,
                cycle=cycle,
                start_date=start_date
            )

            df = pd.DataFrame(schedule)

            st.session_state.schedule_df = df

            # =====================================================
            # 建立加寬畫布
            # =====================================================

            LEGEND_WIDTH = 320

            new_width = image.width + LEGEND_WIDTH
            new_height = image.height

            result_img = Image.new(
                "RGB",
                (new_width, new_height),
                (255, 255, 255)
            )

            result_img.paste(image, (0, 0))

            draw = ImageDraw.Draw(result_img)

            pile_positions = piles

            try:
                day_font = ImageFont.truetype("arial.ttf", 16)
                legend_font = ImageFont.truetype("arial.ttf", 20)
            except:
                day_font = ImageFont.load_default()
                legend_font = ImageFont.load_default()

            # =====================================================
            # 畫樁體 + Day文字 + 樁號
            # =====================================================

            for i, row in df.iterrows():

                color = row["RGB"]

                day_text = row["施工日"].replace("Day ", "D")

                for pile_no in row["施工樁號"]:

                    idx = pile_no - start_no

                    if idx >= len(pile_positions):
                        continue

                    x, y, r = pile_positions[idx]

                    rr = int(r * 0.85)

                    # 彩色樁體
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

                    # Day文字
                    draw.text(
                        (
                            x - 10,
                            y + rr + 5
                        ),
                        day_text,
                        fill="black",
                        font=day_font
                    )

                    # 樁號
                    draw.text(
                        (
                            x - 8,
                            y - rr - 18
                        ),
                        str(pile_no),
                        fill="red",
                        font=day_font
                    )

            # =====================================================
            # 右側 Legend
            # =====================================================

            legend_x = image.width + 40
            legend_y = 80

            draw.text(
                (
                    legend_x,
                    legend_y - 35
                ),
                "施工日顏色對照表",
                fill="black",
                font=legend_font
            )

            legend_height = (len(df) * 32) + 50

            draw.rectangle(
                (
                    legend_x - 20,
                    legend_y - 10,
                    legend_x + 220,
                    legend_y + legend_height
                ),
                outline="black",
                width=2
            )

            for i, row in df.iterrows():

                color = row["RGB"]

                yy = legend_y + (i * 30)

                draw.rectangle(
                    (
                        legend_x,
                        yy,
                        legend_x + 20,
                        yy + 20
                    ),
                    fill=color,
                    outline="black"
                )

                day_no = row["施工日"].replace("Day ", "D")

                draw.text(
                    (
                        legend_x + 35,
                        yy
                    ),
                    day_no,
                    fill="black",
                    font=day_font
                )

            st.session_state.result_image = result_img

            st.session_state.processed = True

            st.rerun()

# =====================================================
# 排程結果
# =====================================================

if st.session_state.schedule_df is not None:

    st.subheader("📋 施工排程結果")

    show_df = st.session_state.schedule_df.copy()

    show_df["施工樁號"] = show_df["施工樁號"].apply(
        lambda x: ", ".join(map(str, x))
    )

    if "RGB" in show_df.columns:
        show_df = show_df.drop(columns=["RGB"])

    def color_date_column(val):

        return f"""
        background-color: {val};
        color: {val};
        """

    styled_df = show_df.style.map(
        color_date_column,
        subset=["日期顏色"]
    )

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=500
    )

# =====================================================
# 成果圖
# =====================================================

if st.session_state.result_image is not None:

    result_col, download_col = st.columns([4, 1])

    with result_col:

        st.subheader("🗺️ 排樁施工圖")

        RESULT_WIDTH = 1200

        result_img = st.session_state.result_image

        scale_ratio = RESULT_WIDTH / result_img.width

        result_height = int(result_img.height * scale_ratio)

        result_display = result_img.resize(
            (RESULT_WIDTH, result_height)
        )

        st.image(
            result_display,
            use_container_width=False
        )

    with download_col:

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
            mime="image/png",
            use_container_width=True
        )

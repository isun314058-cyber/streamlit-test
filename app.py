import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import numpy as np
import cv2
import random
import math
import io
from datetime import datetime, timedelta

st.set_page_config(
    page_title="AI 排樁施工系統",
    layout="wide"
)

# =========================================================
# 深色模式
# =========================================================

st.markdown("""
<style>
.stApp {
    background-color: #000522;
    color: white;
}

h1,h2,h3,h4,h5,h6,label,p,span,div {
    color: white !important;
}

.stButton button {
    border-radius: 12px;
    border: 1px solid #555;
    background-color: #111827;
    color: white;
}

.stDataFrame {
    background-color: white;
}

section[data-testid="stSidebar"] {
    background-color: #020817;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# AI辨識
# =========================================================

def detect_piles(image):

    img = np.array(image)

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=30,
        param1=50,
        param2=18,
        minRadius=8,
        maxRadius=25
    )

    piles = []

    if circles is not None:

        circles = np.round(circles[0, :]).astype("int")

        filtered = []

        for (x, y, r) in circles:

            # 只保留施工區
            if (
                100 < x < 900 and
                180 < y < 980
            ):
                filtered.append((x, y, r))

        # 排序：左到右、上到下
        filtered = sorted(filtered, key=lambda k: (k[1], k[0]))

        row_threshold = 25
        rows = []

        for c in filtered:

            placed = False

            for row in rows:

                if abs(row[0][1] - c[1]) < row_threshold:
                    row.append(c)
                    placed = True
                    break

            if not placed:
                rows.append([c])

        rows = sorted(rows, key=lambda r: r[0][1])

        pile_no = 1

        for row in rows:

            row = sorted(row, key=lambda r: r[0])

            for (x, y, r) in row:

                piles.append({
                    "pile_no": pile_no,
                    "x": x,
                    "y": y,
                    "r": r
                })

                pile_no += 1

    return piles

# =========================================================
# 鄰近判斷
# =========================================================

def is_neighbor(p1, p2, threshold=55):

    dx = p1["x"] - p2["x"]
    dy = p1["y"] - p2["y"]

    distance = math.sqrt(dx * dx + dy * dy)

    return distance < threshold

# =========================================================
# 動態排程
# =========================================================

def generate_schedule(
    piles,
    daily_count,
    start_no,
    interval,
    start_date
):

    piles = sorted(piles, key=lambda p: p["pile_no"])

    total = len(piles)

    start_index = 0

    for i, p in enumerate(piles):

        if p["pile_no"] == start_no:
            start_index = i
            break

    reordered = piles[start_index:] + piles[:start_index]

    remaining = reordered.copy()

    schedule = []

    day = 1

    while remaining:

        today = []

        remove_list = []

        for pile in remaining:

            if len(today) >= daily_count:
                break

            safe = True

            for t in today:

                if is_neighbor(pile, t):
                    safe = False
                    break

            if safe:
                today.append(pile)
                remove_list.append(pile)

        for r in remove_list:
            remaining.remove(r)

        schedule.append({
            "day": day,
            "date": (
                start_date +
                timedelta(days=day - 1)
            ).strftime("%Y-%m-%d"),
            "piles": today
        })

        day += 1

    return schedule

# =========================================================
# 顏色
# =========================================================

def random_color():

    return (
        random.randint(80,255),
        random.randint(80,255),
        random.randint(80,255)
    )

# =========================================================
# 上傳
# =========================================================

uploaded_file = st.file_uploader(
    "上傳圖面",
    type=["png", "jpg", "jpeg", "pdf"]
)

if uploaded_file:

    image = Image.open(uploaded_file).convert("RGB")

    piles = detect_piles(image)

    st.success(f"✅ AI辨識到 {len(piles)} 支樁體")

    # =====================================================
    # AI辨識結果 + 施工條件
    # =====================================================

    col1, col2 = st.columns([2,1])

    with col1:

        st.markdown("## 🔎 AI辨識結果")

        draw_img = image.copy()

        draw = ImageDraw.Draw(draw_img)

        for pile in piles:

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
                outline="red",
                width=3
            )

            draw.text(
                (x+10, y-10),
                str(pile["pile_no"]),
                fill="red"
            )

        st.image(draw_img, width=900)

    with col2:

        st.markdown("## 🗓️ 施工條件")

        start_date = st.date_input(
            "施工開始日期"
        )

        daily_count = st.number_input(
            "每日施工支數",
            min_value=1,
            value=14
        )

        start_no = st.number_input(
            "起始樁號",
            min_value=1,
            max_value=len(piles),
            value=1
        )

        interval = st.selectbox(
            "循環間隔",
            [3,4,5,6,7,8],
            index=1
        )

        run_btn = st.button("🚀 執行排程")

    # =====================================================
    # 執行排程
    # =====================================================

    if run_btn:

        schedule = generate_schedule(
            piles,
            daily_count,
            start_no,
            interval,
            start_date
        )

        st.markdown("---")

        st.markdown("## 📋 施工排程結果")

        result_data = []

        color_map = {}

        for item in schedule:

            color = random_color()

            color_map[item["day"]] = color

            result_data.append({
                "施工日": f"Day {item['day']}",
                "日期": item["date"],
                "施工樁號":
                    ", ".join(
                        str(p["pile_no"])
                        for p in item["piles"]
                    )
            })

        df = pd.DataFrame(result_data)

        st.dataframe(df, use_container_width=True)

        # Excel下載
        excel_buffer = io.BytesIO()

        with pd.ExcelWriter(
            excel_buffer,
            engine="openpyxl"
        ) as writer:

            df.to_excel(
                writer,
                index=False
            )

        st.download_button(
            "📥 下載 Excel",
            excel_buffer.getvalue(),
            file_name="施工排程.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # =================================================
        # 排樁施工圖
        # =================================================

        st.markdown("---")

        col3, col4 = st.columns([2,1])

        with col3:

            st.markdown("## 🗺️ 排樁施工圖")

            output = image.copy()

            draw = ImageDraw.Draw(output)

            legend_x = output.width - 220
            legend_y = 120

            for item in schedule:

                day = item["day"]

                color = color_map[day]

                for pile in item["piles"]:

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
                        outline="black",
                        width=2
                    )

                    draw.text(
                        (x-8, y-28),
                        str(pile["pile_no"]),
                        fill="red"
                    )

                    draw.text(
                        (x-10, y+18),
                        f"D{day}",
                        fill="black"
                    )

                # 圖例
                ly = legend_y + (day * 40)

                draw.rectangle(
                    (
                        legend_x,
                        ly,
                        legend_x + 25,
                        ly + 25
                    ),
                    fill=color,
                    outline="black"
                )

                draw.text(
                    (legend_x + 40, ly),
                    f"D{day}",
                    fill="black"
                )

            st.image(output, width=900)

        with col4:

            st.markdown("## 📥 下載圖面")

            img_buffer = io.BytesIO()

            output.save(
                img_buffer,
                format="PNG"
            )

            st.download_button(
                "下載 PNG 圖面",
                img_buffer.getvalue(),
                file_name="排樁施工圖.png",
                mime="image/png"
            )

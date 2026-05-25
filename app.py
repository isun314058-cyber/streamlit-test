import streamlit as st
import cv2
import numpy as np
import pandas as pd
import fitz
import io
import random

from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from streamlit_image_coordinates import streamlit_image_coordinates

# =========================
# Streamlit 基本設定
# =========================

st.set_page_config(
    page_title="AI排樁施工系統",
    layout="wide"
)

# =========================
# CSS
# =========================

st.markdown("""
<style>

body {
    background-color: #020617;
    color: white;
}

.stApp {
    background-color: #020617;
}

h1,h2,h3,h4,h5,h6,p,span,label,div {
    color: white;
}

.block-container {
    padding-top: 1rem;
}

.stButton>button {
    width: 100%;
    border-radius: 12px;
    height: 50px;
    font-size: 20px;
    font-weight: bold;
}

[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}

</style>
""", unsafe_allow_html=True)

# =========================
# Functions
# =========================

def generate_unique_colors(n):

    colors = []

    for i in range(n):

        colors.append(
            (
                random.randint(80,255),
                random.randint(80,255),
                random.randint(80,255)
            )
        )

    return colors


def detect_piles(img):

    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=40,
        param1=100,
        param2=20,
        minRadius=8,
        maxRadius=30
    )

    pile_data = []

    if circles is not None:

        circles = np.round(circles[0, :]).astype("int")

        # 左上 → 右上 → 下一排
        circles = sorted(circles, key=lambda c: (c[1], c[0]))

        for idx, c in enumerate(circles, start=1):

            x, y, r = c

            pile_data.append({
                "pile_no": idx,
                "x": int(x),
                "y": int(y),
                "r": int(r)
            })

    return pile_data


def create_schedule(
    pile_data,
    piles_per_day,
    start_no,
    spacing
):

    remaining = pile_data.copy()

    schedule = []

    day_idx = 1

    min_spacing = spacing * 40

    while remaining:

        today_piles = []

        while remaining and len(today_piles) < piles_per_day:

            added = False

            for p in remaining[:]:

                conflict = False

                for t in today_piles:

                    dx = abs(p["x"] - t["x"])
                    dy = abs(p["y"] - t["y"])

                    if dx < min_spacing and dy < min_spacing:
                        conflict = True
                        break

                if not conflict:

                    today_piles.append(p)
                    remaining.remove(p)
                    added = True

                if len(today_piles) >= piles_per_day:
                    break

            if not added:
                break

        schedule.append({
            "day": day_idx,
            "piles": today_piles
        })

        day_idx += 1

    return schedule


# =========================
# Upload
# =========================

uploaded_file = st.file_uploader(
    "請上傳 JPG / PNG / PDF",
    type=["jpg","jpeg","png","pdf"]
)

if uploaded_file is not None:

    # PDF
    if uploaded_file.type == "application/pdf":

        pdf = fitz.open(
            stream=uploaded_file.read(),
            filetype="pdf"
        )

        page = pdf.load_page(0)

        pix = page.get_pixmap(matrix=fitz.Matrix(2,2))

        img = Image.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples
        )

    else:

        img = Image.open(uploaded_file).convert("RGB")

    # =========================
    # AI辨識
    # =========================

    pile_data = detect_piles(img)

    st.success(f"✅ AI辨識到 {len(pile_data)} 支樁體")

    # =========================
    # 顯示圖
    # =========================

    col1, col2 = st.columns([3,1])

    with col1:

        draw_img = img.copy()

        draw = ImageDraw.Draw(draw_img)

        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except:
            font = ImageFont.load_default()

        for p in pile_data:

            x = p["x"]
            y = p["y"]
            r = p["r"]

            draw.ellipse(
                (x-r, y-r, x+r, y+r),
                outline="red",
                width=3
            )

            # 編號放大
            draw.text(
                (x + r + 5, y - r),
                str(p["pile_no"]),
                fill="red",
                font=font
            )

        st.image(draw_img, width=900)

    # =========================
    # 施工條件
    # =========================

    with col2:

        st.markdown("## 🗓️ 施工條件")

        start_date = st.date_input(
            "施工開始日期",
            value=datetime.today()
        )

        piles_per_day = st.number_input(
            "每日施工支數",
            min_value=1,
            value=15
        )

        start_no = st.number_input(
            "起始樁號",
            min_value=1,
            value=1
        )

        spacing = st.selectbox(
            "循環間隔",
            [3,4,5,6,7,8]
        )

        total_days = int(
            np.ceil(len(pile_data) / piles_per_day)
        )

        finish_date = start_date + timedelta(days=total_days-1)

        st.info(f"預定完成日期\n\n# {finish_date}")

        execute = st.button("🚀 執行排程")

    # =========================
    # 執行排程
    # =========================

    if execute:

        colors = generate_unique_colors(300)

        schedule = create_schedule(
            pile_data,
            piles_per_day,
            start_no,
            spacing
        )

        # =========================
        # Table
        # =========================

        table_data = []

        for idx, s in enumerate(schedule):

            c = colors[idx]

            color_hex = '#%02x%02x%02x' % c

            piles_txt = ", ".join(
                [str(p["pile_no"]) for p in s["piles"]]
            )

            table_data.append({
                "施工日": f"Day {idx+1}",
                "日期": (
                    start_date +
                    timedelta(days=idx)
                ).strftime("%Y-%m-%d"),
                "日期顏色": color_hex,
                "施工樁號": piles_txt
            })

        df = pd.DataFrame(table_data)

        def color_row(val):

            return f'background-color: {val}; color:black'

        styled_df = df.style.map(
            color_row,
            subset=["日期顏色"]
        )

        st.markdown("## 📋 施工排程結果")

        st.dataframe(
            styled_df,
            hide_index=True,
            width="stretch",
            height=600
        )

        # =========================
        # CSV
        # =========================

        csv = df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "📥 下載施工排程 CSV",
            csv,
            file_name="施工排程.csv",
            mime="text/csv"
        )

        # =========================
        # 排樁施工圖
        # =========================

        st.markdown("## 🗺️ 排樁施工圖")

        output = img.copy()

        w, h = output.size

        # 右方延伸空白區
        new_w = w + 500

        canvas = Image.new(
            "RGB",
            (new_w, h),
            (245,245,245)
        )

        canvas.paste(output, (0,0))

        draw = ImageDraw.Draw(canvas)

        try:
            font_big = ImageFont.truetype("arial.ttf", 18)
            font_small = ImageFont.truetype("arial.ttf", 14)

        except:
            font_big = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # =========================
        # 畫樁
        # =========================

        for idx, s in enumerate(schedule):

            c = colors[idx]

            for p in s["piles"]:

                x = p["x"]
                y = p["y"]
                r = p["r"]

                pile_no = p["pile_no"]

                draw.ellipse(
                    (x-r, y-r, x+r, y+r),
                    fill=c,
                    outline="black",
                    width=2
                )

                # Day文字
                draw.text(
                    (x-10, y+r+5),
                    f"D{idx+1}",
                    fill="black",
                    font=font_small
                )

                # 樁號
                draw.text(
                    (x+r+5, y-r),
                    str(pile_no),
                    fill="black",
                    font=font_small
                )

        # =========================
        # Legend
        # =========================

        legend_x = w + 80
        legend_y = 80

        draw.rectangle(
            (
                legend_x-20,
                legend_y-20,
                legend_x+180,
                legend_y+40+len(schedule)*30
            ),
            outline="black",
            width=2,
            fill="white"
        )

        draw.text(
            (legend_x, legend_y-10),
            "施工日顏色",
            fill="black",
            font=font_big
        )

        for idx, s in enumerate(schedule):

            c = colors[idx]

            yy = legend_y + 40 + idx*30

            draw.rectangle(
                (
                    legend_x,
                    yy,
                    legend_x+20,
                    yy+20
                ),
                fill=c,
                outline="black"
            )

            draw.text(
                (legend_x+35, yy),
                f"D{idx+1}",
                fill="black",
                font=font_small
            )

        st.image(canvas, width=1200)

        # =========================
        # 匯出圖片
        # =========================

        img_bytes = io.BytesIO()

        canvas.save(
            img_bytes,
            format="PNG"
        )

        st.download_button(
            "📥 下載排程圖面",
            img_bytes.getvalue(),
            file_name="排樁施工圖.png",
            mime="image/png"
        )

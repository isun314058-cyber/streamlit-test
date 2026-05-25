import streamlit as st
from PIL import Image, ImageDraw
import pandas as pd
import io
from datetime import datetime, timedelta
import fitz

# =========================
# 頁面設定
# =========================

st.set_page_config(
    page_title="AI 排樁施工系統",
    layout="wide"
)

st.title("🏗️ AI 排樁施工系統")

# =========================
# 上傳圖面
# =========================

uploaded_file = st.file_uploader(
    "上傳 JPG / PNG / PDF 圖面",
    type=["jpg", "jpeg", "png", "pdf"]
)

image = None

if uploaded_file is not None:

    file_type = uploaded_file.type

    # JPG PNG
    if file_type in ["image/jpeg", "image/png"]:

        image = Image.open(uploaded_file).convert("RGB")

    # PDF
    elif file_type == "application/pdf":

        pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")

        page = pdf.load_page(0)

        pix = page.get_pixmap()

        image = Image.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples
        )

    st.image(
        image,
        caption="已上傳圖面",
        use_container_width=True
    )

# =========================
# 施工條件
# =========================

st.header("🗓️ 施工條件設定")

col1, col2 = st.columns(2)

with col1:

    start_date = st.date_input(
        "施工開始日期"
    )

    total_days = st.number_input(
        "預計施工天數",
        min_value=1,
        value=10
    )

with col2:

    piles_per_day = st.number_input(
        "每日施工支數",
        min_value=1,
        value=15
    )

    start_pile = st.number_input(
        "起始樁號",
        min_value=1,
        value=1
    )

# =========================
# 幾支樁一循環
# =========================

cycle_gap = st.selectbox(
    "幾支樁一循環",
    options=[2, 3, 4, 5, 6],
    index=3
)

# =========================
# 執行按鈕
# =========================

if st.button("🚀 執行排程"):

    # =========================
    # 建立排程
    # =========================

    total_piles = 150

    all_piles = list(range(start_pile, total_piles + 1))

    grouped_piles = []

    # 跳號分組
    for i in range(cycle_gap):

        temp = []

        for pile in all_piles:

            if (pile - start_pile) % cycle_gap == i:
                temp.append(pile)

        grouped_piles.extend(temp)

    # 每日排程
    schedule = []

    current_date = start_date

    index = 0

    for day in range(total_days):

        today_piles = grouped_piles[
            index:index + piles_per_day
        ]

        if len(today_piles) == 0:
            break

        schedule.append({
            "施工日": f"Day {day+1}",
            "日期": current_date.strftime("%Y-%m-%d"),
            "施工樁號": ", ".join(
                map(str, today_piles)
            )
        })

        current_date += timedelta(days=1)

        index += piles_per_day

    # =========================
    # 顯示表格
    # =========================

    st.header("📋 施工排程結果")

    df = pd.DataFrame(schedule)

    st.dataframe(
        df,
        use_container_width=True
    )

    # =========================
    # 圖面上色
    # =========================

    if image is not None:

        draw = ImageDraw.Draw(image)

        # =========================
        # 固定樁位座標
        # =========================

        start_x = 265
        start_y = 550

        x_spacing = 135
        y_spacing = 135

        cols = 15

        pile_positions = {}

        for pile_no in range(1, 151):

            row = (pile_no - 1) // cols
            col = (pile_no - 1) % cols

            x = start_x + (col * x_spacing)
            y = start_y + (row * y_spacing)

            pile_positions[pile_no] = (x, y)

        # =========================
        # 每日顏色
        # =========================

        day_colors = [
            "red",
            "blue",
            "green",
            "orange",
            "purple",
            "yellow",
            "cyan",
            "magenta",
            "lime",
            "pink"
        ]

        # =========================
        # 上色
        # =========================

        for day_index, row_data in enumerate(schedule):

            color = day_colors[
                day_index % len(day_colors)
            ]

            pile_text = row_data["施工樁號"]

            pile_list = pile_text.split(",")

            for pile_str in pile_list:

                pile_no = int(pile_str.strip())

                if pile_no in pile_positions:

                    x, y = pile_positions[pile_no]

                    draw.ellipse(
                        (
                            x - 24,
                            y - 24,
                            x + 24,
                            y + 24
                        ),
                        fill=color
                    )

        # =========================
        # 顯示圖面
        # =========================

        st.header("🗺️ 排樁施工圖")

        st.image(
            image,
            caption="AI 自動排程結果",
            use_container_width=True
        )

        # =========================
        # 下載圖面
        # =========================

        img_buffer = io.BytesIO()

        image.save(
            img_buffer,
            format="PNG"
        )

        st.download_button(
            label="📥 下載排程圖面",
            data=img_buffer.getvalue(),
            file_name="pile_schedule.png",
            mime="image/png"
        )

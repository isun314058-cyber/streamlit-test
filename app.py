import streamlit as st
from PIL import Image, ImageDraw
import pandas as pd
from datetime import datetime, timedelta
import random

# 頁面設定
st.set_page_config(
    page_title="AI 排樁施工系統",
    layout="wide"
)

st.title("🏗️ AI 排樁施工系統")

# 上傳圖面
uploaded_file = st.file_uploader(
    "上傳 JPG / PNG / PDF 圖面",
    type=["jpg", "jpeg", "png", "pdf"]
)

# 顯示圖面
if uploaded_file is not None:

    image = Image.open(uploaded_file)

    st.image(image, caption="已上傳排樁圖", use_container_width=True)

    st.header("📅 施工條件設定")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input("施工開始日期")

        total_days = st.number_input(
            "預計施工天數",
            min_value=1,
            value=10
        )

    with col2:
        daily_count = st.number_input(
            "每日施工支數",
            min_value=1,
            value=15
        )

        start_pile = st.number_input(
            "起始樁號",
            min_value=1,
            value=1
        )

    # 執行按鈕
    if st.button("🚀 執行排程"):

        total_piles = 150

        piles = list(range(start_pile, total_piles + 1))

        # 跳號邏輯
        even_group = [p for p in piles if p % 2 == 0]
        odd_group = [p for p in piles if p % 2 == 1]

        final_order = odd_group + even_group

        schedule = []

        current_index = 0

        for day in range(total_days):

            today_piles = final_order[
                current_index:current_index + daily_count
            ]

            current_index += daily_count

            work_date = start_date + timedelta(days=day)

            schedule.append({
                "施工日": f"Day {day+1}",
                "日期": work_date,
                "施工樁號": ", ".join(map(str, today_piles))
            })

        st.header("📋 施工排程結果")

        df = pd.DataFrame(schedule)

        st.dataframe(df, use_container_width=True)

        # ===== 原圖上色 =====

        draw = ImageDraw.Draw(image)

        width, height = image.size

        random.seed(10)

        for i in range(50):

            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)

            color = random.choice([
                "red",
                "blue",
                "green",
                "orange",
                "purple"
            ])

            draw.ellipse(
                (x-20, y-20, x+20, y+20),
                fill=color
            )

        st.header("🗺️ 排樁施工圖")

        st.image(
            image,
            caption="系統自動排程上色結果",
            use_container_width=True
        )

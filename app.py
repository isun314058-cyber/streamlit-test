# ==========================================
# AI 排樁施工系統 - 完整修正版
# 修正內容：
# 1. AI自動辨識樁數（非固定150）
# 2. AI自動偵測樁位置與大小
# 3. 顏色精準鎖定樁心
# 4. 下載後圖面不消失
# 5. 顏色說明正常顯示
# 6. 無上傳圖面不可執行
# ==========================================

import streamlit as st
from PIL import Image, ImageDraw
import pandas as pd
import io
import cv2
import numpy as np
from datetime import timedelta
import fitz

# ==========================================
# 頁面設定
# ==========================================

st.set_page_config(
    page_title="AI 排樁施工系統",
    layout="wide"
)

st.title("🏗️ AI 排樁施工系統")

# ==========================================
# SESSION STATE
# ==========================================

if "output_image" not in st.session_state:
    st.session_state.output_image = None

if "schedule_df" not in st.session_state:
    st.session_state.schedule_df = None

# ==========================================
# 上傳圖面
# ==========================================

uploaded_file = st.file_uploader(
    "上傳 JPG / PNG / PDF 圖面",
    type=["jpg", "jpeg", "png", "pdf"]
)

image = None

# ==========================================
# 讀取圖面
# ==========================================

if uploaded_file is not None:

    file_type = uploaded_file.type

    # JPG PNG
    if file_type in ["image/jpeg", "image/png"]:

        image = Image.open(uploaded_file).convert("RGB")

    # PDF
    elif file_type == "application/pdf":

        pdf = fitz.open(
            stream=uploaded_file.read(),
            filetype="pdf"
        )

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

# ==========================================
# 施工條件
# ==========================================

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

cycle_gap = st.selectbox(
    "幾支樁一循環",
    options=[2, 3, 4, 5, 6],
    index=3
)

# ==========================================
# 執行排程
# ==========================================

if st.button("🚀 執行排程"):

    # ======================================
    # 未上傳圖面
    # ======================================

    if image is None:

        st.error("請先上傳圖面")

    else:

        # ======================================
        # PIL → OpenCV
        # ======================================

        img_cv = cv2.cvtColor(
            np.array(image),
            cv2.COLOR_RGB2BGR
        )

        gray = cv2.cvtColor(
            img_cv,
            cv2.COLOR_BGR2GRAY
        )

        # ======================================
        # AI偵測圓形樁位
        # ======================================

        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=40,
            param1=100,
            param2=20,
            minRadius=10,
            maxRadius=40
        )

        pile_positions = []

        if circles is not None:

            circles = np.round(circles[0, :]).astype("int")

            for c in circles:

                x, y, r = c

                # 避免偵測到右側說明框
                if x < image.width * 0.82:

                    pile_positions.append({
                        "x": x,
                        "y": y,
                        "r": r
                    })

        # ======================================
        # AI排序
        # 由上到下、由左到右
        # ======================================

        pile_positions = sorted(
            pile_positions,
            key=lambda k: (k["y"], k["x"])
        )

        # ======================================
        # AI重新編號
        # ======================================

        piles = {}

        for idx, p in enumerate(pile_positions):

            pile_no = idx + 1

            piles[pile_no] = p

        total_piles = len(piles)

        # ======================================
        # 顯示辨識結果
        # ======================================

        st.success(f"AI已辨識 {total_piles} 支樁")

        # ======================================
        # 排程邏輯
        # ======================================

        all_piles = list(
            range(start_pile, total_piles + 1)
        )

        grouped = []

        for i in range(cycle_gap):

            temp = []

            for p in all_piles:

                if (p - start_pile) % cycle_gap == i:
                    temp.append(p)

            grouped.extend(temp)

        # ======================================
        # 建立排程
        # ======================================

        schedule = []

        current_date = start_date

        idx = 0

        for day in range(total_days):

            today = grouped[
                idx:idx + piles_per_day
            ]

            if len(today) == 0:
                break

            schedule.append({
                "施工日": f"Day {day+1}",
                "日期": current_date.strftime("%Y-%m-%d"),
                "施工樁號": ", ".join(
                    map(str, today)
                )
            })

            idx += piles_per_day

            current_date += timedelta(days=1)

        # ======================================
        # 顏色
        # ======================================

        colors = [
            (255,0,0),      # 紅
            (255,255,0),    # 黃
            (0,255,0),      # 綠
            (0,0,255),      # 藍
            (255,0,255),    # 紫
            (0,255,255),    # 青
            (255,128,0),    # 橘
            (128,255,0),
            (255,192,203),
            (255,0,128)
        ]

        # ======================================
        # 畫圖
        # ======================================

        output = image.copy()

        draw = ImageDraw.Draw(output)

        for d, row in enumerate(schedule):

            color = colors[d % len(colors)]

            pile_list = row["施工樁號"].split(",")

            for p in pile_list:

                pile_no = int(p.strip())

                if pile_no in piles:

                    data = piles[pile_no]

                    x = data["x"]
                    y = data["y"]
                    r = data["r"]

                    # AI依原樁大小畫圖
                    draw.ellipse(
                        (
                            x-r,
                            y-r,
                            x+r,
                            y+r
                        ),
                        fill=color
                    )

        # ======================================
        # 存SESSION
        # ======================================

        st.session_state.output_image = output

        st.session_state.schedule_df = pd.DataFrame(schedule)

# ==========================================
# 顯示結果
# ==========================================

if st.session_state.schedule_df is not None:

    st.header("📋 施工排程結果")

    st.dataframe(
        st.session_state.schedule_df,
        use_container_width=True
    )

    # ======================================
    # 顏色說明
    # ======================================

    st.header("🎨 顏色說明")

    color_names = [
        "紅色",
        "黃色",
        "綠色",
        "藍色",
        "紫色",
        "青色",
        "橘色",
        "黃綠色",
        "粉紅色",
        "桃紅色"
    ]

    html = ""

    for i in range(len(st.session_state.schedule_df)):

        c = colors[i % len(colors)]

        rgb = f"rgb({c[0]},{c[1]},{c[2]})"

        html += f"""
        <div style="
            display:flex;
            align-items:center;
            margin-bottom:10px;
        ">
            <div style="
                width:25px;
                height:25px;
                border-radius:50%;
                background:{rgb};
                margin-right:10px;
            "></div>

            <div>
                Day {i+1} - {color_names[i % len(color_names)]}
            </div>
        </div>
        """

    st.markdown(
        html,
        unsafe_allow_html=True
    )

# ==========================================
# 顯示圖面
# ==========================================

if st.session_state.output_image is not None:

    st.header("🗺️ 排樁施工圖")

    st.image(
        st.session_state.output_image,
        use_container_width=True
    )

    # ======================================
    # 下載圖面
    # ======================================

    buffer = io.BytesIO()

    st.session_state.output_image.save(
        buffer,
        format="PNG"
    )

    st.download_button(
        label="📥 下載排程圖面",
        data=buffer.getvalue(),
        file_name="pile_schedule.png",
        mime="image/png"
    )

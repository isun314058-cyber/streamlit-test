import streamlit as st
from PIL import Image, ImageDraw
import pandas as pd
import io
from datetime import timedelta
import fitz

# ====================================
# 頁面設定
# ====================================

st.set_page_config(
    page_title="AI 排樁施工系統",
    layout="wide"
)

st.title("🏗️ AI 排樁施工系統")

# ====================================
# 初始化變數
# ====================================

image = None
output_image = None

# ====================================
# 上傳圖面
# ====================================

uploaded_file = st.file_uploader(
    "上傳 JPG / PNG / PDF 圖面",
    type=["jpg", "jpeg", "png", "pdf"]
)

# ====================================
# 讀取圖面
# ====================================

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

# ====================================
# 施工條件設定
# 永遠顯示
# ====================================

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

# ====================================
# 幾支樁一循環
# ====================================

cycle_gap = st.selectbox(
    "幾支樁一循環",
    options=[2, 3, 4, 5, 6],
    index=3
)

# ====================================
# 執行排程
# ====================================

if st.button("🚀 執行排程"):

    # ====================================
    # 未上傳圖面
    # ====================================

    if image is None:

        st.error("請先上傳排樁圖面")

    else:

        # ====================================
        # 複製圖面
        # 避免下載後消失
        # ====================================

        output_image = image.copy()

        draw = ImageDraw.Draw(output_image)

        # ====================================
        # 圖片尺寸
        # ====================================

        img_width, img_height = output_image.size

        # ====================================
        # 樁位設定
        # ====================================

        total_piles = 150
        cols = 15

        # ====================================
        # 依圖片比例自動計算位置
        # ====================================

        start_x = img_width * 0.16
        start_y = img_height * 0.28

        x_spacing = img_width * 0.065
        y_spacing = img_height * 0.075

        # ====================================
        # 建立樁位座標
        # ====================================

        pile_positions = {}

        for pile_no in range(1, total_piles + 1):

            row = (pile_no - 1) // cols
            col = (pile_no - 1) % cols

            x = int(start_x + (col * x_spacing))
            y = int(start_y + (row * y_spacing))

            pile_positions[pile_no] = (x, y)

        # ====================================
        # 排程邏輯
        # ====================================

        all_piles = list(
            range(start_pile, total_piles + 1)
        )

        grouped_piles = []

        # 跳號排程
        for i in range(cycle_gap):

            temp = []

            for pile in all_piles:

                if (pile - start_pile) % cycle_gap == i:
                    temp.append(pile)

            grouped_piles.extend(temp)

        # ====================================
        # 建立每日排程
        # ====================================

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
                "施工日": f"Day {day + 1}",
                "日期": current_date.strftime("%Y-%m-%d"),
                "施工樁號": ", ".join(
                    map(str, today_piles)
                )
            })

            current_date += timedelta(days=1)

            index += piles_per_day

        # ====================================
        # 顏色
        # ====================================

        day_colors = [
            "red",
            "blue",
            "green",
            "orange",
            "purple",
            "cyan",
            "yellow",
            "lime",
            "pink",
            "magenta"
        ]

        # ====================================
        # 圖面上色
        # ====================================

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
                            x - 22,
                            y - 22,
                            x + 22,
                            y + 22
                        ),
                        fill=color
                    )

        # ====================================
        # 顯示排程表
        # ====================================

        st.header("📋 施工排程結果")

        df = pd.DataFrame(schedule)

        st.dataframe(
            df,
            use_container_width=True
        )

        # ====================================
        # 顏色說明
        # ====================================

        st.subheader("🎨 顏色說明")

        for i in range(len(schedule)):

            color = day_colors[i % len(day_colors)]

            st.markdown(
                f"""
                <div style="
                    display:flex;
                    align-items:center;
                    margin-bottom:8px;
                ">
                    <div style="
                        width:25px;
                        height:25px;
                        background:{color};
                        border-radius:50%;
                        margin-right:10px;
                    "></div>

                    <div>
                        Day {i+1}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # ====================================
        # 顯示圖面
        # ====================================

        st.header("🗺️ 排樁施工圖")

        st.image(
            output_image,
            caption="AI 自動排程結果",
            use_container_width=True
        )

        # ====================================
        # 下載圖面
        # ====================================

        img_buffer = io.BytesIO()

        output_image.save(
            img_buffer,
            format="PNG"
        )

        st.download_button(
            label="📥 下載排程圖面",
            data=img_buffer.getvalue(),
            file_name="pile_schedule.png",
            mime="image/png"
        )

import streamlit as st
from PIL import Image
import fitz
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import datetime

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

if uploaded_file is not None:

    file_type = uploaded_file.type

    # 圖片
    if file_type in ["image/jpeg", "image/png"]:

        image = Image.open(uploaded_file)

        st.image(
            image,
            caption="上傳圖面",
            use_container_width=True
        )

    # PDF
    elif file_type == "application/pdf":

        pdf_bytes = uploaded_file.read()

        pdf_document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        st.success(f"PDF 共 {len(pdf_document)} 頁")

        for page_num in range(len(pdf_document)):

            page = pdf_document.load_page(page_num)

            pix = page.get_pixmap()

            img_bytes = pix.tobytes("png")

            st.image(
                img_bytes,
                caption=f"第 {page_num + 1} 頁",
                use_container_width=True
            )

# =========================
# 施工條件設定
# =========================

st.header("📅 施工條件設定")

col1, col2 = st.columns(2)

with col1:

    start_date = st.date_input(
        "施工開始日期",
        datetime.date.today()
    )

    total_days = st.number_input(
        "預計施工天數",
        min_value=1,
        value=10
    )

    start_pile = st.number_input(
        "起始樁號",
        min_value=1,
        value=1
    )

with col2:

    daily_count = st.number_input(
        "每日施工支數",
        min_value=1,
        value=4
    )

    cols = st.number_input(
        "橫向樁數",
        min_value=1,
        value=5
    )

    rows = st.number_input(
        "縱向樁數",
        min_value=1,
        value=5
    )

# =========================
# 建立樁位
# =========================

pile_total = cols * rows

pile_positions = {}

pile_no = 1

for r in range(rows):

    for c in range(cols):

        pile_positions[pile_no] = (c, -r)

        pile_no += 1

# =========================
# 鄰樁判定
# =========================

neighbors = {}

for p1, pos1 in pile_positions.items():

    neighbors[p1] = []

    for p2, pos2 in pile_positions.items():

        if p1 == p2:
            continue

        dx = abs(pos1[0] - pos2[0])
        dy = abs(pos1[1] - pos2[1])

        # 上下左右
        if (dx == 1 and dy == 0) or (dx == 0 and dy == 1):

            neighbors[p1].append(p2)

# =========================
# 自動排程
# =========================

schedule = {}

remaining = list(range(start_pile, pile_total + 1))

day = 1

previous_day_piles = []

while remaining and day <= total_days:

    today_piles = []

    blocked = []

    for p in previous_day_piles:

        blocked.extend(neighbors[p])

    for pile in remaining:

        if pile not in blocked:

            today_piles.append(pile)

        if len(today_piles) >= daily_count:
            break

    for p in today_piles:

        remaining.remove(p)

    schedule[day] = today_piles

    previous_day_piles = today_piles

    day += 1

# =========================
# 顯示施工結果
# =========================

st.header("📋 施工排程結果")

result_data = []

for day, piles in schedule.items():

    work_date = start_date + datetime.timedelta(days=day - 1)

    result_data.append({
        "施工日": f"Day {day}",
        "日期": work_date,
        "施工樁號": ", ".join(map(str, piles))
    })

df = pd.DataFrame(result_data)

st.dataframe(
    df,
    use_container_width=True
)

# =========================
# 畫施工圖
# =========================

st.header("🗺️ 排樁施工圖")

fig, ax = plt.subplots(figsize=(10, 8))

colors = [
    "red",
    "blue",
    "green",
    "orange",
    "purple",
    "cyan",
    "yellow"
]

pile_day_map = {}

for day, piles in schedule.items():

    for p in piles:

        pile_day_map[p] = day

# 畫樁

for pile, (x, y) in pile_positions.items():

    color = "lightgray"

    if pile in pile_day_map:

        day_color = colors[(pile_day_map[pile] - 1) % len(colors)]

        color = day_color

    circle = plt.Circle(
        (x, y),
        0.35,
        color=color
    )

    ax.add_patch(circle)

    ax.text(
        x,
        y,
        str(pile),
        ha='center',
        va='center',
        fontsize=10,
        color='black'
    )

ax.set_xlim(-1, cols)
ax.set_ylim(-rows, 1)

ax.set_aspect('equal')

ax.set_title("施工排程圖")

ax.axis('off')

st.pyplot(fig)

# =========================
# 完工資訊
# =========================

finish_date = start_date + datetime.timedelta(days=len(schedule) - 1)

st.success(f"""
開工日期：{start_date}

預計完工日：{finish_date}

總施工天數：{len(schedule)} 天
""")

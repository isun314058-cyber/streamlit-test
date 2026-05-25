import streamlit as st
from PIL import Image, ImageDraw
import pandas as pd
import numpy as np
import random
import io
import cv2
from streamlit_drawable_canvas import st_canvas

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
    "canvas_key": "canvas_main",
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
            random.randint(40, 255),
            random.randint(40, 255),
            random.randint(40, 255)
        )

        if color not in colors:
            colors.append(color)

    return colors


# =====================================================
# AI 辨識樁體
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

    st.session_state.uploaded = True

    image = Image.open(uploaded_file).convert("RGBA")

    st.subheader("✏️ 框選施工區域")

    st.info("請直接在圖面上框選要施工的樁區域")

    canvas_result = st_canvas(
        fill_color="rgba(255,0,0,0.08)",
        stroke_width=3,
        stroke_color="#ff0000",
        background_image=image,
        update_streamlit=True,
        drawing_mode="rect",
        height=image.height,
        width=image.width,
        key=st.session_state.canvas_key
    )

    # =====================================================
    # ROI
    # =====================================================

    roi = None

    if (
        canvas_result.json_data is not None
        and len(canvas_result.json_data["objects"]) > 0
    ):

        rect = canvas_result.json_data["objects"][-1]

        left = int(rect["left"])
        top = int(rect["top"])

        width = int(rect["width"] * rect["scaleX"])
        height = int(rect["height"] * rect["scaleY"])

        roi = (
            left,
            top,
            left + width,
            top + height
        )

        st.session_state.roi = roi

    # =====================================================
    # 有框選後才顯示施工設定
    # =====================================================

    if roi:

        st.success("已完成施工區域框選")

        # =====================================================
        # AI 辨識
        # =====================================================

        piles = detect_piles(image, roi)

        st.session_state.pile_positions = piles

        total_piles = len(piles)

        st.success(f"AI 辨識到 {total_piles} 支樁體")

        # =====================================================
        # 顯示辨識結果
        # =====================================================

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
                width=2
            )

            preview_draw.text(
                (x + 10, y - 10),
                str(idx + 1),
                fill="red"
            )

        st.subheader("🔍 AI 樁位辨識結果")

        st.image(preview_img, use_container_width=True)

        # =====================================================
        # 施工設定
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

            # =====================================================
            # 繪圖
            # =====================================================

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

    show_df = show_df[[
        "施工日",
        "日期",
        "日期顏色",
        "施工樁號"
    ]]

    st.dataframe(
        show_df,
        use_container_width=True
    )

    # =====================================================
    # 顏色說明
    # =====================================================

    st.subheader("🎨 顏色說明")

    for _, row in st.session_state.schedule_df.iterrows():

        color = row["日期顏色"]

        st.markdown(
            f'''
            <div style="
                display:flex;
                align-items:center;
                gap:10px;
                margin-bottom:10px;
            ">
                <div style="
                    width:25px;
                    height:25px;
                    border-radius:50%;
                    background:{color};
                    border:1px solid white;
                "></div>

                <div>
                    {row['施工日']} - {row['日期']} - {color}
                </div>
            </div>
            ''',
            unsafe_allow_html=True
        )

# =====================================================
# 顯示結果圖
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

    col1, col2 = st.columns([3, 1])

    with col1:

        filename = st.text_input(
            "檔案名稱",
            value="排樁施工圖"
        )

    with col2:

        img_buffer = io.BytesIO()

        st.session_state.result_image.save(
            img_buffer,
            format="PNG"
        )

        st.download_button(
            label="下載排程圖面",
            data=img_buffer.getvalue(),
            file_name=f"{filename}.png",
            mime="image/png"
        )
```

---

# requirements.txt

```txt
streamlit
pillow
pandas
numpy
opencv-python-headless
streamlit-drawable-canvas
```

---

# GitHub 更新方式

1. 開啟 app.py
2. 全部刪除
3. 貼上新的完整 code
4. Commit changes
5. Streamlit Cloud → Reboot app

# =====================================================
# AI 排樁施工系統 完整版
# =====================================================

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from pdf2image import convert_from_bytes

import pandas as pd
import numpy as np
import math
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

.stApp{
    background-color:#020617;
    color:white;
}

h1,h2,h3,h4,h5,h6,p,span,label{
    color:white;
}

.stButton>button{
    border-radius:12px;
    height:50px;
    font-size:20px;
    font-weight:bold;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# Title
# =====================================================

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
    ("左上", "red"),
    ("左下", "blue"),
    ("右上", "orange"),
    ("右下", "lime")
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
# AI辨識樁位
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

                if dist < 25:
                    duplicated = True
                    break

            if not duplicated:
                filtered.append((x, y, r))

        row_tolerance = 40

        filtered = sorted(filtered, key=lambda p: p[1])

        grouped_rows = []

        for circle in filtered:

            placed = False

            for row in grouped_rows:

                if abs(circle[1] - row[0][1]) < row_tolerance:
                    row.append(circle)
                    placed = True
                    break

            if not placed:
                grouped_rows.append([circle])

        final_sorted = []

        for row in grouped_rows:

            row = sorted(row, key=lambda p: p[0])

            final_sorted.extend(row)

        positions = final_sorted

    return positions

# =====================================================
# 智慧避鄰排程
# =====================================================

def calculate_distance(p1, p2):

    x1, y1, _ = p1
    x2, y2, _ = p2

    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


# =====================================================
# 建立鄰樁關係
# =====================================================

def build_neighbor_map(
    pile_positions,
    safe_distance=120
):

    neighbor_map = {}

    for i, p1 in enumerate(pile_positions):

        pile_no = i + 1

        neighbor_map[pile_no] = []

        for j, p2 in enumerate(pile_positions):

            other_no = j + 1

            if pile_no == other_no:
                continue

            dist = calculate_distance(p1, p2)

            if dist < safe_distance:

                neighbor_map[pile_no].append(other_no)

    return neighbor_map


# =====================================================
# AI 智慧避鄰排程
# =====================================================

def create_schedule(
    pile_positions,
    total_piles,
    daily_count,
    start_date,
    start_no=1,
    cooldown_days=1
):

    import random
    import pandas as pd

    # =====================================================
    # 建立樁座標 Grid
    # =====================================================

    cols = 15

    pile_grid = {}

    for i in range(total_piles):

        row = i // cols
        col = i % cols

        pile_grid[i + 1] = (row, col)

    # =====================================================
    # 建立鄰樁表（九宮格）
    # =====================================================

    neighbor_map = {}

    for p1 in pile_grid:

        r1, c1 = pile_grid[p1]

        neighbor_map[p1] = []

        for p2 in pile_grid:

            if p1 == p2:
                continue

            r2, c2 = pile_grid[p2]

            # 九宮格鄰樁
            if (
                abs(r1 - r2) <= 1
                and
                abs(c1 - c2) <= 1
            ):

                neighbor_map[p1].append(p2)

    # =====================================================
    # 顏色
    # =====================================================

    colors = []

    for _ in range(100):

        colors.append(
            (
                random.randint(80, 230),
                random.randint(80, 230),
                random.randint(80, 230)
            )
        )

    # =====================================================
    # 初始化
    # =====================================================

    remaining = list(range(1, total_piles + 1))

    # 起始樁優先
    if start_no in remaining:

        remaining.remove(start_no)
        remaining.insert(0, start_no)

    blocked_until = {}

    result = []

    day = 1

    # =====================================================
    # 開始排程
    # =====================================================

    while remaining:

        today_piles = []

        # =================================================
        # 第一天第一支固定起始樁
        # =================================================

        if day == 1:

            if start_no in remaining:

                today_piles.append(start_no)

                remaining.remove(start_no)

                blocked_until[start_no] = (
                    day + cooldown_days
                )

                for neighbor in neighbor_map[start_no]:

                    blocked_until[neighbor] = (
                        day + cooldown_days
                    )

        # =================================================
        # 剩餘樁排序
        # 鄰樁越多越優先
        # =================================================

        sorted_remaining = sorted(

            remaining,

            key=lambda p: len(neighbor_map[p]),

            reverse=True
        )

        # =================================================
        # 找今日可施工樁
        # =================================================

        for pile in sorted_remaining:

            if len(today_piles) >= daily_count:
                break

            # 冷卻判定
            if pile in blocked_until:

                if day <= blocked_until[pile]:
                    continue

            # =================================================
            # 九宮格衝突檢查
            # =================================================

            conflict = False

            for existing in today_piles:

                if (
                    pile in neighbor_map[existing]
                    or
                    existing in neighbor_map[pile]
                ):

                    conflict = True
                    break

            if conflict:
                continue

            # =================================================
            # 加入今日施工
            # =================================================

            # =====================================================
            # AI 未來評估
            # =====================================================
            
            temp_today = today_piles + [pile]
            

            future_blocked = set()

            # 今天施工後會被封鎖的樁
            for p in temp_today:
            
                future_blocked.add(p)
            
                future_blocked.update(
                    neighbor_map[p]
                )
            
            # 未來還能施工的樁
            future_remaining = len([
            
                p for p in remaining
            
                if p not in future_blocked
            
            ])
            
            future_days = max(
                1,
                math.ceil(
                    future_remaining / daily_count
                )
            )
            
            future_avg = (
                future_remaining / future_days
            )
            
            # 避免最後幾天只剩1~2支
            if future_avg < daily_count * 0.75:
            
                continue

            MIN_LAST_DAY = int(daily_count * 0.5)
            
            if (
                future_remaining > 0
                and
                future_remaining < MIN_LAST_DAY
            ):
            
                continue
            
            today_piles.append(pile)

        # =================================================
        # 避免卡死
        # =================================================

        if len(today_piles) == 0:

            today_piles.append(remaining[0])

        # =================================================
        # 更新封鎖
        # =================================================

        for pile in today_piles:

            if pile in remaining:

                remaining.remove(pile)

            blocked_until[pile] = (
                day + cooldown_days
            )

            for neighbor in neighbor_map[pile]:

                blocked_until[neighbor] = (
                    day + cooldown_days
                )

        # =================================================
        # 日期
        # =================================================

        current_date = (
            pd.to_datetime(start_date)
            + pd.Timedelta(days=day - 1)
        )

        # =================================================
        # 顏色
        # =================================================

        color = colors[day - 1]

        hex_color = '#%02x%02x%02x' % color

        # =================================================
        # 儲存結果
        # =================================================

        result.append({

            "施工日": f"Day {day}",

            "日期": current_date.strftime("%Y-%m-%d"),

            "日期顏色": hex_color,

            "施工樁號": sorted(today_piles)

        })

        day += 1

    return result

# =====================================================
# 上傳
# =====================================================

uploaded_file = st.file_uploader(
    "上傳 JPG / PNG / PDF 圖面",
    type=["jpg", "jpeg", "png", "pdf"]
)

# =====================================================
# 主流程
# =====================================================

if uploaded_file:

    if uploaded_file.type == "application/pdf":

        pdf_bytes = uploaded_file.read()

        pdf_pages = convert_from_bytes(
            pdf_bytes,
            dpi=300
        )

        image = pdf_pages[0].convert("RGB")

    else:

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

✏️ 點選順序

🔴 左上　🔵 左下　🟠 右上　🟢 右下
""")

    left_col, right_col = st.columns([5, 1.3])

    preview_canvas = canvas_bg.copy()

    draw_preview = ImageDraw.Draw(preview_canvas)

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

    with right_col:

        st.subheader("📍 點位資訊")

        if len(st.session_state.points) == 0:

            st.info("尚未點選")

        else:

            for idx, point in enumerate(st.session_state.points):

                label, color = POINT_COLORS[idx]

                st.markdown(
                    f"""
{label}

顏色：{COLOR_TEXT[color]}
"""
                )

        st.markdown("---")

        if roi:

            st.success("✅ 已完成施工區域")

        if st.button("🔄 重新選取"):

            st.session_state.points = []
            st.session_state.last_clicked = None
            st.session_state.pile_positions = []
            st.session_state.schedule_df = None
            st.session_state.result_image = None
            st.session_state.processed = False

            st.rerun()

    if roi:

        piles = detect_piles(image, roi)

        st.session_state.pile_positions = piles

        total_piles = len(piles)

        st.success(f"✅ AI 辨識到 {total_piles} 支樁體")

        result_img = image.copy()

        draw = ImageDraw.Draw(result_img)

        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except:
            font = ImageFont.load_default()

        for idx, (x, y, r) in enumerate(piles):

            pile_no = idx + 1

            draw.ellipse(
                (
                    x - r,
                    y - r,
                    x + r,
                    y + r
                ),
                outline="red",
                width=4
            )

            draw.text(
                (
                    x + r + 5,
                    y - r - 5
                ),
                str(pile_no),
                fill="red",
                font=font
            )

        # =====================================================
        # AI辨識結果 + 施工條件
        # =====================================================

        left_area, right_area = st.columns([3, 1.2])

        with left_area:

            st.subheader("🔍 AI辨識結果")

            st.image(
                result_img,
                width=900
            )

        with right_area:

            st.subheader("📅 施工條件")

            start_date = st.date_input("施工開始日期")

            daily_count = st.number_input(
                "每日施工支數",
                min_value=1,
                value=14
            )

            start_no = st.number_input(
                "起始樁號",
                min_value=1,
                max_value=total_piles,
                value=1
            )

            
            execute = st.button(
                "🚀 執行排程",
                use_container_width=True
            )

        if execute:

            schedule = create_schedule(

                pile_positions=piles,
            
                total_piles=total_piles,
            
                daily_count=daily_count,
            
                start_date=start_date,
            
                start_no=start_no,
            
                cooldown_days=1
            )

            df = pd.DataFrame(schedule)

            st.session_state.schedule_df = df

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

            for i, row in df.iterrows():

                hex_color = row["日期顏色"]

                color = tuple(
                
                    int(hex_color[i:i+2], 16)
                
                    for i in (1, 3, 5)
                )

                day_text = row["施工日"].replace("Day ", "D")

                for pile_no in row["施工樁號"]:

                    idx = pile_no - 1

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

                    draw.text(
                        (
                            x - 10,
                            y + rr + 5
                        ),
                        day_text,
                        fill="black",
                        font=day_font
                    )

                    draw.text(
                        (
                            x - 8,
                            y - rr - 18
                        ),
                        str(pile_no),
                        fill="red",
                        font=day_font
                    )

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

                hex_color = row["日期顏色"]

                color = tuple(
                    int(hex_color[i:i+2], 16)
                    for i in (1, 3, 5)
                )

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
# 顯示排程結果
# =====================================================

if st.session_state.processed:

    st.markdown("---")

    st.subheader("📋 施工排程結果")

    df = st.session_state.schedule_df

    if df is not None:

        display_df = df.copy()

        display_df["施工樁號"] = display_df["施工樁號"].apply(
            lambda x: ", ".join(map(str, x))
        )
        # 刪除 RGB 欄位
        if "RGB" in display_df.columns:

            display_df = display_df.drop(columns=["RGB"])
    
        # 日期顏色改成色塊
        display_df["日期顏色"] = display_df["日期顏色"].apply(
            lambda c:
            f'<div style="background:{c}; width:80px; height:28px; border-radius:6px;"></div>'
        )
        
        st.markdown(
            f"""
            <div style="
                max-height:500px;
                overflow-y:auto;
                border:1px solid #333;
                border-radius:10px;
            ">
                {display_df.to_html(
                    escape=False,
                    index=False
                )}
            </div>
            """,
            unsafe_allow_html=True
        )

       

    # =====================================================
    # 排樁施工圖 + 下載圖面
    # =====================================================

    left_result, right_download = st.columns([3, 1])

    with left_result:

        st.subheader("🗺️ 排樁施工圖")

        st.image(
            st.session_state.result_image,
            width=900
        )

    with right_download:

        st.subheader("📥 下載圖面")

        export_type = st.selectbox(
            "選擇匯出格式",
            ["PNG", "JPG", "PDF"]
        )

        img_buffer = io.BytesIO()

        result_img = st.session_state.result_image

        if export_type == "PNG":

            result_img.save(img_buffer, format="PNG")

            st.download_button(
                label="下載 PNG 圖面",
                data=img_buffer.getvalue(),
                file_name="pile_schedule.png",
                mime="image/png",
                use_container_width=True
            )

        elif export_type == "JPG":

            rgb_img = result_img.convert("RGB")

            rgb_img.save(img_buffer, format="JPEG")

            st.download_button(
                label="下載 JPG 圖面",
                data=img_buffer.getvalue(),
                file_name="pile_schedule.jpg",
                mime="image/jpeg",
                use_container_width=True
            )

        else:

            rgb_img = result_img.convert("RGB")

            rgb_img.save(img_buffer, format="PDF")

            st.download_button(
                label="下載 PDF 圖面",
                data=img_buffer.getvalue(),
                file_name="pile_schedule.pdf",
                mime="application/pdf",
                use_container_width=True
            )


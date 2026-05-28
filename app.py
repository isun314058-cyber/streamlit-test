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
import easyocr
import math
import random

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

.schedule-table{
    width:100%;
    min-width:1400px;
    border-collapse:collapse;
    color:white;
    font-size:16px;
}

.schedule-table th{
    background:#132238;
    color:#ffffff;
    padding:14px;
    text-align:center;
    border:1px solid #2d3b55;
    position:sticky;
    top:0;
    z-index:2;
}

.schedule-table td{
    padding:12px;
    border:1px solid #2d3b55;
    vertical-align:top;
}

.schedule-table tr:nth-child(even){
    background:#0b1730;
}

.schedule-table tr:hover{
    background:#16284a;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# Title
# =====================================================

st.title("🏗️ AI 排樁施工系統")

# =====================================================
# 功能模式
# =====================================================

mode = st.radio(

    "請選擇功能模式",

    [

        "🆕 新建預定進度表",

        "🛠️ 修正當前進度表"

    ],

    horizontal=True

)

st.markdown("---")

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

        # =====================================
        # AI 自動統一樁半徑
        # =====================================
        
        all_radius = [r for (_, _, r) in final_sorted]
        
        valid_radius = [
            r for r in all_radius
            if 8 <= r <= 25
        ]
        
        median_radius = int(np.median(valid_radius))
        
        # 避免極端值
        median_radius = max(10, median_radius)
        median_radius = min(22, median_radius)
        
        positions = []
        
        for (x, y, r) in final_sorted:
        
            positions.append(
                (
                    x,
                    y,
                    median_radius
                )
            )

    return positions
    
# =====================================================
# OCR 自動辨識原圖樁號
# =====================================================

@st.cache_resource
def load_ocr():

    return easyocr.Reader(
        ['en'],
        gpu=False,
        download_enabled=True
    )

reader = load_ocr()

def detect_pile_numbers(image, piles):

    img = np.array(image)

    mapping = {}

    for idx, (x, y, r) in enumerate(piles):

        OCR_SIZE = 45
        
        x1 = max(0, x - OCR_SIZE)
        y1 = max(0, y - OCR_SIZE)
        
        x2 = min(img.shape[1], x + OCR_SIZE)
        y2 = min(img.shape[0], y + OCR_SIZE)

        crop = img[y1:y2, x1:x2]

        gray_crop = cv2.cvtColor(
            crop,
            cv2.COLOR_RGB2GRAY
        )
        
        gray_crop = cv2.resize(
            gray_crop,
            None,
            fx=2,
            fy=2
        )
        
        _, gray_crop = cv2.threshold(
            gray_crop,
            210,
            255,
            cv2.THRESH_BINARY
        )

        results = reader.readtext(
            gray_crop,
            detail=0,
            paragraph=False,
            allowlist='D0123456789',
            batch_size=4
        )

        detected_no = ""

        for text in results:
        
            text = text.strip()
        
            # ========================================
            # 過濾 D1 D2 D3 類型
            # ========================================
        
            if text.upper().startswith("D"):
                continue
        
            # ========================================
            # 只保留數字
            # ========================================
        
            text = ''.join(filter(str.isdigit, text))
        
            # ========================================
            # 必須是數字
            # ========================================
        
            if not text.isdigit():
                continue
        
            value = int(text)
        
            # ========================================
            # 限制合理樁號
            # ========================================
        
            if 1 <= value <= 300:
        
                detected_no = value
                break

        mapping[idx + 1] = detected_no

    return mapping

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
    # AI 自動學習最近鄰距離
    # =====================================================
    
    nearest_distances = []
    
    for i, p1 in enumerate(pile_positions):
    
        min_dist = 999999
    
        for j, p2 in enumerate(pile_positions):
    
            if i == j:
                continue
    
            dist = calculate_distance(p1, p2)
    
            if dist < min_dist:
    
                min_dist = dist
    
        nearest_distances.append(min_dist)
    
    # AI 學習真正樁距
    base_distance = np.median(nearest_distances)

    # =====================================================
    # Delaunay AI 鄰樁判定
    # =====================================================
    
    from scipy.spatial import Delaunay
    
    points = np.array([
        [x, y]
        for (x, y, r) in pile_positions
    ])
    
    tri = Delaunay(points)
    
    neighbor_map = {}
    
    for i in range(len(points)):
    
        neighbor_map[i + 1] = set()
    
    # 建立三角形鄰接
    for simplex in tri.simplices:
    
        for i in range(3):
    
            for j in range(3):
    
                if i != j:
    
                    p1 = simplex[i] + 1
                    p2 = simplex[j] + 1
    
                    # 計算真實距離
                    dist = calculate_distance(
                        pile_positions[p1 - 1],
                        pile_positions[p2 - 1]
                    )
    
                    if dist <= base_distance * 1.15:
                        # 避免超長斜角
                        dx = abs(
                            pile_positions[p1 - 1][0]
                            -
                            pile_positions[p2 - 1][0]
                        )
                    
                        dy = abs(
                            pile_positions[p1 - 1][1]
                            -
                            pile_positions[p2 - 1][1]
                        )
                    
                        # 過長斜角不算鄰樁
                        if (
                            dx > base_distance * 1.2
                            or
                            dy > base_distance * 1.2
                        ):
                        
                            continue
                        
                        neighbor_map[p1].add(p2)
    
    # set 轉 list
    MAX_NEIGHBORS = 8
    
    for p in neighbor_map:
    
        neighbors = list(neighbor_map[p])
    
        neighbors = sorted(
    
            neighbors,
    
            key=lambda n:
            calculate_distance(
                pile_positions[p - 1],
                pile_positions[n - 1]
            )
    
        )
    
        neighbor_map[p] = neighbors[:MAX_NEIGHBORS]

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
    loop_guard = 0
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
        # AI 智慧選樁
        # =================================================

        while len(today_piles) < daily_count:
        
            # =====================================
            # 先過濾還能施工的樁
            # =====================================
        
            candidate_piles = [
            
                p for p in remaining
            
                if (
            
                    p not in today_piles
            
                    and not (
            
                        p in blocked_until
                        and day <= blocked_until[p]
            
                    )
                )
            ]
        
            # 沒候選樁就停止
            if len(candidate_piles) == 0:
                break
        
            # =====================================
            # AI排序
            # =====================================
            random.shuffle(candidate_piles)
            sorted_remaining = sorted(
        
                candidate_piles,
        
                key=lambda p: (
        
                    len(neighbor_map[p]),
        
                    -abs(p - start_no)
        
                ),
        
                reverse=True
        
            )
        
            best_score = -999999
        
            best_pile = None
        
            for pile in sorted_remaining:

                # =========================================
                # 冷卻判定
                # =========================================

                if pile in blocked_until:

                    if day <= blocked_until[pile]:

                        continue

                # =========================================
                # 十字衝突檢查
                # =========================================

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

                # =========================================
                # 模擬加入後
                # =========================================

                temp_today = today_piles + [pile]

                future_blocked = set()

                for p in temp_today:

                    future_blocked.add(p)

                    future_blocked.update(
                        neighbor_map[p]
                    )

                future_remaining_list = [
                
                    p for p in remaining
                
                    if (
                
                        p not in future_blocked
                
                        and not (
                
                            p in blocked_until
                            and day <= blocked_until[p]
                
                        )
                
                    )
                
                ]

                # =========================================
                # 孤立檢查
                # =========================================

                isolated_count = 0

                for p in future_remaining_list:

                    available_neighbors = [

                        n for n in neighbor_map[p]

                        if n in future_remaining_list

                    ]

                    if len(available_neighbors) == 0:

                        isolated_count += 1

                # ==================================================
                # 二層模擬
                # ==================================================
                
                secondary_future = 0

                if len(future_remaining_list) > 0:
                
                    sample_future = random.sample(
                        future_remaining_list,
                        min(2, len(future_remaining_list))
                    )
                
                    for fp in sample_future:
                
                        second_blocked = set()
                
                        second_blocked.add(fp)
                
                        second_blocked.update(
                            neighbor_map[fp]
                        )
                
                        second_remaining = [
                
                            x for x in future_remaining_list
                
                            if x not in second_blocked
                        ]
                
                        secondary_future += len(second_remaining)
                
                        if secondary_future > 300:
                            break

                # =========================================
                # AI 評分
                # =========================================
                
                score = 0

                fill_ratio = len(temp_today) / daily_count
                
                score += fill_ratio * 350
                
                # 二層模擬加分
                score += secondary_future * 1.2
                
                # ==================================================
                # 1. 未來可施工量（最重要）
                # ==================================================
                
                future_count = len(future_remaining_list)
                
                future_days_left = math.ceil(
                    future_count / daily_count
                )
                
                # ==================================================
                # 尾盤預測（新增）
                # ==================================================
                
                if future_days_left > 0:
                
                    estimated_tail_avg = (
                        future_count / future_days_left
                    )
                
                    # 尾盤太少
                    if estimated_tail_avg < daily_count * 0.75:
                
                        score -= 500
                
                    # 尾盤穩定
                    else:
                
                        score += 120
                
                # ==================================================
                # 未來平均量
                # ==================================================
                
                if future_days_left >= 1:
                
                    expected_avg = (
                        future_count / future_days_left
                    )
                
                    score += expected_avg * 35
                
                # 未來可施工數量
                score += future_count * 12

                
                # ==================================================
                # 2. 孤立樁重罰
                # ==================================================
                
                score -= isolated_count * 80
                
                # ==================================================
                # 3. 未來平均施工量
                # ==================================================
                
                future_days = max(
                    1,
                    math.ceil(
                        future_count / daily_count
                    )
                )
                
                future_avg = (
                    future_count / future_days
                )
                
                score += future_avg * 25
                
                # ==================================================
                # 4. 如果未來平均太低
                # 代表後面會崩盤
                # ==================================================
                
                if future_avg < daily_count * 0.8:
                
                    score -= 400
                
                # ==================================================
                # 5. 最後幾天避免只剩單支
                # ==================================================
                
                if (
                    future_count > 0
                    and
                    future_count < daily_count * 0.5
                ):
                
                    score -= 150
                
                # ==================================================
                # 6. 鄰居多優先
                # ==================================================
                
                score += len(neighbor_map[pile]) * 8
                
                # ==================================================
                # 7. 靠近目前群組
                # ==================================================
                
                if len(today_piles) > 0:
                
                    cluster_score = 0
                
                    for existing in today_piles:
                
                        cluster_score += abs(
                            pile - existing
                        )
                
                    score -= cluster_score * 0.08
                
                # ==================================================
                # 8. 靠近起始樁
                # ==================================================
                
                score -= abs(pile - start_no) * 0.01
                # =========================================
                # 更新最佳選擇
                # =========================================
                
                if score > best_score:
                
                    best_score = score
                
                    best_pile = pile
                    
            # =============================================
            # 找不到可施工樁
            # =============================================

            if best_pile is None:

                break

            # =============================================
            # 加入今日施工
            # =============================================

            today_piles.append(best_pile)

            if best_pile in remaining:

                remaining.remove(best_pile)

            # 立即更新封鎖
            blocked_until[best_pile] = day + cooldown_days
            
            for neighbor in neighbor_map[best_pile]:
            
                blocked_until[neighbor] = day + cooldown_days

        # =================================================
        # 避免卡死
        # =================================================

        if len(today_piles) == 0:

            today_piles.append(remaining[0])

            remaining.remove(remaining[0])

        # =================================================
        # 更新封鎖
        # =================================================

        for pile in today_piles:

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

        color = colors[(day - 1) % len(colors)]

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
        loop_guard += 1
        
        if loop_guard > total_piles * 2:
        
            st.warning("AI 排程過久，已自動停止")
        
            break

    return result

# =====================================================
# 模式：新建預定進度表
# =====================================================

if mode == "🆕 新建預定進度表":

    uploaded_file = st.file_uploader(

        "上傳 JPG / PNG / PDF 圖面",

        type=["jpg", "jpeg", "png", "pdf"],

        key="new_schedule"

    )

# =====================================================
# 模式：修正當前進度表
# =====================================================

else:

    uploaded_file = st.file_uploader(

        "上傳目前施工進度圖",

        type=["jpg", "jpeg", "png", "pdf"],

        key="modify_schedule"

    )

    st.info(

        "📌 請上傳目前已編排施工日的圖面"

    )

# =====================================================
# 主流程
# =====================================================
if mode == "🆕 新建預定進度表":
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
                        
                st.session_state.repair_total_piles = total_piles
        
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
                    with st.spinner("🤖 AI 正在分析最佳施工排程中，請稍候..."):
            
                        best_schedule = None
            
                        best_total_score = -999999
                        
                        # AI 多次模擬
                        for sim in range(10):
                        
                            schedule = create_schedule(
                        
                                pile_positions=piles,
                        
                                total_piles=total_piles,
                        
                                daily_count=daily_count,
                        
                                start_date=start_date,
                        
                                start_no=start_no,
                        
                                cooldown_days=1
                            )
                        
                            # =====================================
                            # AI 總體評分
                            # =====================================
                        
                            schedule_score = 0
                        
                            # 天數越少越好
                            schedule_score -= len(schedule) * 120
                        
                            # 最後三天不要太少
                            last_days = schedule[-3:]
                        
                            last_count = sum(
                        
                                len(x["施工樁號"])
                        
                                for x in last_days
                            )
                        
                            schedule_score += last_count * 40
                        
                            # 平均施工量穩定
                            daily_counts = [
                        
                                len(x["施工樁號"])
                        
                                for x in schedule
        
                            ]
                            avg_daily = np.mean(daily_counts)
                                
                            schedule_score += avg_daily * 50
                        
                            variance = np.var(daily_counts)
                        
                            # 波動越小越好
                            schedule_score -= variance * 30
                        
                            # =====================================
                            # 尾盤修復
                            # =====================================
                            
                            tail_days = schedule[-5:]
                            
                            tail_total = sum(
                                len(x["施工樁號"])
                                for x in tail_days
                            )
                            
                            # 如果最後三天太少
                            if tail_total < daily_count * 4:
                            
                                schedule_score -= 200
                            
                            # 最後一天不能太少
                            last_day_count = len(schedule[-1]["施工樁號"])
                            
                            if last_day_count <= 2:
                            
                                schedule_score -= 300
                            
                            
                            # =====================================
                            # 更新最佳結果
                            # =====================================
                            
                            if schedule_score > best_total_score:
                            
                                best_total_score = schedule_score
                            
                                best_schedule = schedule
                        
                        # 最終最佳排程
                        schedule = best_schedule
        
                    df = pd.DataFrame(schedule)
        
                    st.session_state.schedule_df = df
        
                    LEGEND_WIDTH = 165
        
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

                        FONT_NAME = "DejaVuSans.ttf"
                    
                        day_font = ImageFont.truetype(
                            FONT_NAME,
                            14
                        )
                    
                        pile_font = ImageFont.truetype(
                            FONT_NAME,
                            18
                        )
                    
                        legend_font = ImageFont.truetype(
                            FONT_NAME,
                            28
                        )
                    
                        st.success("✅ 字型載入成功")
                    
                    except Exception as e:
                    
                        st.error(f"❌ 字型失敗: {e}")
                    
                        day_font = ImageFont.load_default()
                    
                        pile_font = ImageFont.load_default()
                    
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
        
                            # =====================================
                            # 日期固定在圓下方
                            # =====================================
                            
                            day_bbox = draw.textbbox(
                                (0, 0),
                                day_text,
                                font=day_font
                            )
                            
                            day_width = day_bbox[2] - day_bbox[0]
                            
                            day_x = x - (day_width // 2)
                            
                            # 日期往下移一點
                            day_y = y + 18
                            
                            # =====================================
                            # 畫施工日期 D1 D2
                            # =====================================
                            
                            draw.text(
                                (
                                    day_x,
                                    day_y
                                ),
                                day_text,
                                fill="black",
                                font=day_font,
                                stroke_width=2,
                                stroke_fill="white"
                            )
                            
                                                       
                            # =====================================
                            # 樁號固定在圓正上方
                            # 不受圓大小影響
                            # =====================================
                            
                            # =====================================
                            # 樁號固定在圓正上方
                            # =====================================
                            
                            pile_text = str(pile_no)
                            
                            pile_bbox = draw.textbbox(
                                (0, 0),
                                pile_text,
                                font=pile_font
                            )
                            
                            pile_width = pile_bbox[2] - pile_bbox[0]
                            pile_height = pile_bbox[3] - pile_bbox[1]
                            
                            pile_x = x - (pile_width // 2)
                            
                            # 自動依字體大小調整高度
                            pile_y = y - r - pile_height - 6
                            
                            draw.text(
                                (
                                    pile_x,
                                    pile_y
                                ),
                                pile_text,
                                fill="red",
                                font=pile_font,
                                stroke_width=2,
                                stroke_fill="white"
                            )
        
                    legend_x = image.width + 28
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
        
                    legend_height = (len(df) * 32) + 2
        
                    draw.rectangle(
                        (
                            legend_x - 20,
                            legend_y - 10,
                            legend_x + 125,
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
                                legend_x + 24,
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
            
                    display_df["施工數量"] = display_df["施工樁號"].apply(len)
            
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
            
                    display_df = display_df[
                        [
                            "施工日",
                            "日期",
                            "日期顏色",
                            "施工數量",
                            "施工樁號"
                        ]
                    ]
                    
                    st.markdown(
                        f"""
                        <div style="
                            width:100%;
                            overflow-x:auto;
                            overflow-y:auto;
                            max-height:650px;
                            border:1px solid #333;
                            border-radius:12px;
                            padding:10px;
                            background:#071225;
                        ">
                            {display_df.to_html(
                                escape=False,
                                index=False,
                                classes="schedule-table"
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
elif mode == "🛠️ 修正當前進度表":
    # ============================================
    # 初始化修正模式
    # ============================================
    
    if "repair_mode_init" not in st.session_state:
    
        st.session_state.repair_points = []
    
        st.session_state.repair_last_clicked = None
        
        st.session_state.repair_piles = []
    
        st.session_state.repair_mode_init = True
    
    # ============================================
    # 上傳圖面
    # ============================================
    
    if uploaded_file:
        current_file_name = uploaded_file.name
    
        if (
            "repair_current_file"
            not in st.session_state
        ):
    
            st.session_state.repair_current_file = current_file_name
    
        elif (
            st.session_state.repair_current_file
            != current_file_name
        ):
    
            st.session_state.repair_points = []
    
            st.session_state.repair_last_clicked = None
    
            st.session_state.repair_current_file = current_file_name

        piles = []

        st.markdown("---")

        st.subheader("🛠️ 修正當前施工進度")

        # ============================================
        # 初始化
        # ============================================

        if "repair_points" not in st.session_state:

            st.session_state.repair_points = []

        # ============================================
        # 讀取圖面
        # ============================================

        if uploaded_file.type == "application/pdf":

            pdf_bytes = uploaded_file.read()

            pdf_pages = convert_from_bytes(
                pdf_bytes,
                dpi=300
            )

            image = pdf_pages[0].convert("RGB")

        else:

            image = Image.open(
                uploaded_file
            ).convert("RGB")

        # ============================================
        # 顯示圖面
        # ============================================

        display_img = image.copy()

        display_img.thumbnail((900, 650))
        scale_x = image.width / display_img.width
        scale_y = image.height / display_img.height

        draw_img = display_img.copy()

        draw = ImageDraw.Draw(draw_img)

        point_colors = [
            "red",
            "blue",
            "orange",
            "lime"
        ]

        # ============================================
        # 畫點
        # ============================================

        for idx, point in enumerate(
            st.session_state.repair_points
        ):

            x, y = point

            draw.ellipse(
                (x-8, y-8, x+8, y+8),
                fill=point_colors[idx]
            )

        # ============================================
        # 畫框
        # ============================================
        
        if len(st.session_state.repair_points) == 4:
        
            pts = st.session_state.repair_points
        
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
        
            x1 = min(xs)
            y1 = min(ys)
        
            x2 = max(xs)
            y2 = max(ys)
        
            draw.rectangle(
                (
                    x1,
                    y1,
                    x2,
                    y2
                ),
                outline="lime",
                width=5
            )



        # ============================================
        # 左右欄位
        # ============================================
        
        left_col, right_col = st.columns([5, 1.3])
        
        # ============================================
        # 左側圖面
        # ============================================
        
        with left_col:
        
            value = streamlit_image_coordinates(
                draw_img,
                key="repair_roi"
            )
        
        # ============================================
        # 右側資訊
        # ============================================
        
        with right_col:
        
            st.subheader("📍 點位資訊")
        
            if len(st.session_state.repair_points) == 0:
        
                st.info("尚未點選")
        
            else:
        
                point_names = [
                    ("左上", "紅色"),
                    ("左下", "藍色"),
                    ("右上", "橘色"),
                    ("右下", "綠色")
                ]
        
                for idx, point in enumerate(
                    st.session_state.repair_points
                ):
        
                    name, color = point_names[idx]
        
                    st.markdown(
                        f"""
        {name}
        
        顏色：{color}
        """
                    )
        
            st.markdown("---")
        
            if len(st.session_state.repair_points) == 4:
        
                st.success("✅ 已完成施工區域")
        
            if st.button("🔄 重新選取"):
            
                st.session_state.repair_points = []
            
                st.session_state.repair_last_clicked = None
            
                st.session_state.repair_piles = []
            
                st.rerun()
        
        # ============================================
        # 點擊新增
        # ============================================
        
        if value is not None:
        
            clicked_point = (
                value["x"],
                value["y"]
            )
        
            if (
                st.session_state.repair_last_clicked
                != clicked_point
            ):
        
                st.session_state.repair_last_clicked = clicked_point
        
                duplicated = False
                
                for old_point in st.session_state.repair_points:
                
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
                    and len(st.session_state.repair_points) < 4
                ):
                
                    st.session_state.repair_points.append(
                        clicked_point
                    )
                
                    st.rerun()

        # ============================================
        # ROI完成 → AI辨識
        # ============================================

        if len(st.session_state.repair_points) == 4:

            pts = st.session_state.repair_points

            x1 = min(pts[0][0], pts[1][0])
            y1 = min(pts[0][1], pts[2][1])

            x2 = max(pts[2][0], pts[3][0])
            y2 = max(pts[1][1], pts[3][1])

            roi = (
                int(x1 * scale_x),
                int(y1 * scale_y),
                int(x2 * scale_x),
                int(y2 * scale_y)
            )

            # AI辨識
            piles = detect_piles(
                image,
                roi
            )
            
            st.session_state.repair_piles = piles

            total_piles = len(piles)

            st.success(
                f"✅ AI辨識到 {total_piles} 支樁體"
            )

            # ========================================
            # 顯示辨識結果
            # ========================================

            result_img = image.copy()

            draw_result = ImageDraw.Draw(result_img)

            try:

                font = ImageFont.truetype(
                    "arial.ttf",
                    20
                )

            except:

                font = ImageFont.load_default()

            for idx, (x, y, r) in enumerate(piles):

                pile_no = idx + 1

                draw_result.ellipse(
                    (
                        x-r,
                        y-r,
                        x+r,
                        y+r
                    ),
                    outline="red",
                    width=4
                )
                
            left_result, right_result = st.columns([2.2, 1])
            
            with left_result:
            
                st.image(
                    result_img,
                    width=900
                )
            
            with right_result:
            
                st.subheader("🤖 AI自動辨識原圖樁號")

        # ============================================
        # 有辨識到樁體才往下
        # ============================================

        if len(st.session_state.repair_piles) > 0:

            # ========================================
            # OCR 自動辨識原圖樁號
            # ========================================
         
            with st.spinner("AI正在辨識原圖樁號..."):
            
                pile_mapping = detect_pile_numbers(
                    image,
                    st.session_state.repair_piles
                )
            
            mapping_rows = []
            
            for ai_no, original_no in pile_mapping.items():
            
                # =========================
                # 預設正常
                # =========================
            
                status = "✅ 正常"
            
                # =========================
                # 空白
                # =========================
            
                if (
                    original_no == ""
                    or
                    original_no is None
                ):
            
                    status = "❌ OCR失敗"
            
                # =========================
                # 非數字
                # =========================
            
                elif not str(original_no).isdigit():
            
                    status = "⚠️ 非數字"
            
                else:
            
                    value = int(original_no)
            
                    # =========================
                    # 超出合理範圍
                    # =========================
            
                    if (
                        value < 1
                        or
                        value > total_piles
                    ):
            
                        status = "⚠️ 超出範圍"
            
                    # =========================
                    # 與AI排序差距過大
                    # =========================
            
                    elif abs(ai_no - value) > 3:
            
                        status = "⚠️ 疑似錯誤"
            
                mapping_rows.append({
            
                    "AI辨識樁號": ai_no,
            
                    "原圖樁號": original_no,
            
                    "錯誤標記": status
            
                })
            
            mapping_df = pd.DataFrame(mapping_rows)

            failed_ocr = mapping_df[
                mapping_df["原圖樁號"] == ""
            ]
            
            if len(failed_ocr) > 0:
            
                st.warning(
                    f"⚠️ 有 {len(failed_ocr)} 支樁 OCR辨識失敗，請確認圖面清晰度"
                )
            
            with right_result:
            
                st.dataframe(
                    mapping_df,
                    use_container_width=True,
                    height=420
                )
            
                st.success("✅ AI已完成原圖樁號對應")

            # ========================================
            # 已完成施工輸入
            # ========================================

            st.markdown("---")

            st.subheader("✅ 已完成施工")

            completed_text = st.text_area(

                "輸入已完成樁號（原圖樁號）",

                placeholder="例如：35,36,40"

            )

            # ========================================
            # 修正施工條件
            # ========================================

            st.markdown("---")

            st.subheader("📅 修正施工條件")

            col1, col2 = st.columns(2)

            with col1:

                start_date = st.date_input(
                    "後續施工開始日期"
                )

            with col2:

                daily_count = st.number_input(
                    "修正後每日施工支數",
                    min_value=1,
                    value=10
                )

            # ========================================
            # AI重新分析
            # ========================================

            if st.button(
                "🧠 AI重新分析後續排程",
                use_container_width=True
            ):

                reverse_mapping = {}

                for ai_no, original_no in pile_mapping.items():
                
                    if str(original_no).isdigit():
                
                        reverse_mapping[int(original_no)] = ai_no

                completed_piles = []

                if completed_text.strip():

                    for x in completed_text.split(","):

                        x = x.strip()

                        if x.isdigit():

                            original_no = int(x)

                            if original_no in reverse_mapping:

                                completed_piles.append(
                                    reverse_mapping[original_no]
                                )

                remaining_piles = []

                for i in range(
                    1,
                    st.session_state.repair_total_piles + 1
                ):
                
                    if i not in completed_piles:
                
                        remaining_piles.append(i)
                
                remaining_data = []
                
                for pile_no in remaining_piles:
                
                    remaining_data.append({
                    
                        "original_no": int(
                            pile_mapping[pile_no]
                        ) if str(
                            pile_mapping[pile_no]
                        ).isdigit() else pile_no,
                    
                        "position": st.session_state.repair_piles[pile_no - 1]
                    
                    })
                
                remaining_positions = [
                
                    x["position"]
                
                    for x in remaining_data
                ]

                with st.spinner(
                    "🤖 AI正在重新分析後續施工..."
                ):

                    new_schedule = create_schedule(

                        pile_positions=remaining_positions,

                        total_piles=len(
                            remaining_positions
                        ),

                        daily_count=daily_count,

                        start_date=start_date,

                        start_no=1,

                        cooldown_days=1

                    )

                st.success(
                    "✅ AI已完成後續最佳化排程"
                )

                # ============================================
                # AI樁號 轉回 原圖樁號
                # ============================================
                
                new_no_mapping = {}
                
                for idx, data in enumerate(remaining_data):
                
                    new_no_mapping[idx + 1] = data["original_no"]
                
                for row in new_schedule:
                
                    row["施工樁號"] = [
                
                        new_no_mapping[p]
                
                        for p in row["施工樁號"]
                    ]
                    
                new_df = pd.DataFrame(new_schedule)

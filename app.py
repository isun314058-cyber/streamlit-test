# =====================================================
# 建立預覽圖
# =====================================================

preview_canvas = canvas_bg.copy()

draw_preview = ImageDraw.Draw(preview_canvas)

# =====================================================
# 畫點位
# =====================================================

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

# =====================================================
# ROI框
# =====================================================

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

# =====================================================
# 左側圖片
# =====================================================

with left_col:

    coords = streamlit_image_coordinates(
        preview_canvas,
        key="pile_roi_selector"
    )

# =====================================================
# 點擊事件
# =====================================================

if coords is not None:

    new_point = (
        coords["x"],
        coords["y"]
    )

    duplicated = False

    for old_point in st.session_state.points:

        dist = (
            (new_point[0] - old_point[0]) ** 2
            +
            (new_point[1] - old_point[1]) ** 2
        ) ** 0.5

        if dist < 10:
            duplicated = True
            break

    if (
        not duplicated
        and len(st.session_state.points) < 4
    ):

        st.session_state.points.append(new_point)

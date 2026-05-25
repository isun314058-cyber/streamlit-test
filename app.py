# =====================================================
# AI辨識
# =====================================================

if roi:

    piles = detect_piles(image, roi)

    st.session_state.pile_positions = piles

    total_piles = len(piles)

    st.success(f"AI 辨識到 {total_piles} 支樁體")

    # =====================================================
    # 樁位預覽
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
            width=3
        )

        preview_draw.text(
            (x + 10, y - 10),
            str(idx + 1),
            fill="red"
        )

    st.subheader("🔍 AI辨識結果")

    st.image(
        preview_img,
        use_container_width=True
    )

    # =====================================================
    # 施工條件
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

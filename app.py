# =====================================================
# 排程結果
# =====================================================

if st.session_state.schedule_df is not None:

    st.subheader("📋 施工排程結果")

    show_df = st.session_state.schedule_df.copy()

    # =====================================================
    # 樁號格式化
    # =====================================================

    show_df["施工樁號"] = show_df["施工樁號"].apply(
        lambda x: ", ".join(map(str, x))
    )

    # =====================================================
    # 顏色樣式
    # =====================================================

    def color_circle(val):

        return f"""
        background-color: {val};
        color: transparent;
        border-radius: 50%;
        """

    # =====================================================
    # 刪除RGB欄位
    # =====================================================

    if "RGB" in show_df.columns:

        show_df = show_df.drop(columns=["RGB"])

    # =====================================================
    # styler
    # =====================================================

    styled_df = show_df.style.map(
        color_circle,
        subset=["日期顏色"]
    )

    # =====================================================
    # 顯示 dataframe
    # =====================================================

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True
    )

    # =====================================================
    # CSV下載
    # =====================================================

    csv = show_df.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        label="📥 下載施工排程 CSV",
        data=csv,
        file_name="施工排程.csv",
        mime="text/csv"
    )

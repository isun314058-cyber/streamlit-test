import streamlit as st

st.title("排樁進度管理系統")

st.write("Streamlit 測試成功")

pile_no = st.number_input("輸入樁號", value=1)

if st.button("送出"):
    st.success(f"已登錄樁號：{pile_no}")

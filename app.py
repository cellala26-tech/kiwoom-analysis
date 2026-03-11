import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta

# --- 숫자 변환 보조 함수 (VBA ToNum 재현) ---
def to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        if s in ['', '-', 'nan', 'NaN']: return 0.0
        return float(s)
    except: return 0.0

# --- 제목 줄 및 컬럼 매칭 보정 ---
def get_clean_df(content, min_col='종목명'):
    for i in range(10):
        try:
            temp_df = pd.read_excel(BytesIO(content), skiprows=i)
            if any(min_col in str(c) for c in temp_df.columns): return temp_df
        except: continue
    return pd.read_excel(BytesIO(content))

# --- 수급 데이터 추출 로직 ---
def get_flow_data(row):
    f_cols = [c for c in row.index if '외국인' in str(c) and ('순' in str(c) or '값' in str(c))]
    i_cols = [c for c in row.index if '기관' in str(c) and ('순' in str(c) or '값' in str(c))]
    f_val = to_num(row[f_cols[0]]) if f_cols else 0.0
    i_val = to_num(row[i_cols[0]]) if i_cols else 0.0
    
    # 수급 점수 계산 (VBA 로직 그대로)
    score = 0
    if f_val > 0: score += 40
    if i_val > 0: score += 40
    if f_val > 0 and i_val > 0: score += 60
    return f_val, i_val, score

st.set_page_config(layout="wide", page_title="키움 TOP200 분석기")
st.title("📊 키움 TOP200 통합 분석 시스템")

# --- 사이드바 설정 ---
st.sidebar.header("📂 분석 설정")
col_date1, col_date2 = st.sidebar.columns(2)
with col_date1:
    if 's_date' not in st.session_state: st.session_state.s_date = datetime(2026, 3, 5)
    start_date = st.date_input("📅 시작일", value=st.session_state.s_date)
with col_date2:
    end_date = st.date_input("📅 종료일", value=datetime(2026, 3, 11))

st.sidebar.write("⏱️ 기간 퀵 설정")
c1, c2, c3 = st.sidebar.columns(3)
with c1:
    if st.button("5일"): st.session_state.s_date = end_date - timedelta(days=4)
with c2:
    if st.button("10일"): st.session_state.s_date = end_date - timedelta(days=9)
with c3:
    if st.button("20일"): st.session_state.s_date = end_date - timedelta(days=19)

analysis_type = st.sidebar.selectbox("📋 분석유형", ["내일 공략 top5", "계좌수 급증", "수급분석", "신규진입종목"])
run_btn = st.sidebar.button("🚀 분석 실행", use_container_width=True)

if run_btn:
    try:
        e_str = end_date.strftime('%Y-%m-%d')
        date_list = pd.date_range(start_date, end_date).strftime('%Y-%m-%d').tolist()
        
        with st.spinner('엑셀 결과 시트 동기화 중...'):
            all_dfs = {}
            for d in date_list:
                res = requests.get(f"https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/{d}.xlsx")
                if res.status_code == 200: all_dfs[d] = get_clean_

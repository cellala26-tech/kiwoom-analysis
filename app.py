import streamlit as st
import pandas as pd
import numpy as np
import re

# 1. 숫자 변환 보조 함수
def safe_to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        if s in ['', '-', 'nan', 'NaN']: return 0.0
        return float(s)
    except:
        return 0.0

# 2. 수급 점수 계산 함수 (VBA CalcFlowScore 로직)
def calc_flow_score(row):
    s = 0
    f_net = safe_to_num(row.get('외국인순값', 0))
    i_net = safe_to_num(row.get('기관순값', 0))
    f_qty = safe_to_num(row.get('외국인수량순값', 0))
    i_qty = safe_to_num(row.get('기관수량순값', 0))
    if f_net > 0: s += 40
    if i_net > 0: s += 40
    if f_net > 0 and i_net > 0: s += 60
    if f_qty > 0: s += 20
    if i_qty > 0: s += 20
    return s

# --- 웹 화면 설정 ---
st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 통합 주식 분석기 (다중 파일 지원)")

# 사이드바 설정
st.sidebar.header("📂 데이터 일괄 업로드")
st.sidebar.info("키움TOP200 파일과 수급 파일을 한꺼번에 선택해서 올려주세요.")

# 다중 파일 업로드 활성화 (accept_multiple_files=True)
uploaded_files = st.sidebar.file_uploader(
    "여러 개의 엑셀 파일을 선택하세요", 
    type=['xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    data_list = []
    flow_list = []
    diva_df = pd.DataFrame()

    with st.spinner('파일들을 통합 분석 중입니다...'):
        for file in uploaded_files:
            fname = file.name
            # 1. DIVA 파일 처리 (파일명에 'DIVA'가 포함된 경우나 특정 시트)
            if 'DIVA' in fname.upper():
                diva_df = pd.read_excel(file)
            
            # 2. 수급 파일 처리 (파일명에 '수급' 포함된 경우)
            elif '수급' in fname:
                temp_df = pd.read_excel(file)
                # 파일명에서 날짜 추출 (예: 2026-03-06)
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
                if date_match:
                    temp_df['날짜'] = date_match.group()
                flow_list.append(temp_df)
            
            # 3. 일반 키움 TOP200 파일 (날짜만 있는 경우)
            else:
                temp_df = pd.read_excel(file)
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
                if date_match:
                    temp_df['날짜'] = date_match.group()
                data_list.append(temp_df)

    # 데이터 통합
    if data_list:
        all_data = pd.concat(data_list, ignore_index=True

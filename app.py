import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- 보조 함수 세트 (VBA의 각종 Function 대체) ---

def safe_to_num(v):
    """VBA의 ToNum, NzNum, SafeToNum 통합: 특수문자 제거 후 숫자로 변환"""
    if pd.na or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').replace(' ', '').strip()
        if s in ['', '-', 'nan', 'NaN']: return 0.0
        return float(s)
    except:
        return 0.0

def calc_flow_score(row):
    """VBA의 CalcFlowScore: 외인/기관 수급 기반 점수 산출"""
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

# 상단 제목 및 스타일
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stDataFrame { border: 1px solid #dee2e6; }
    </style>
    """, unsafe_allow_html=True)

st.title("🍜 미미국밥 주식 분석 시스템 (Web Ver.)")
st.caption("가게와 집 어디서든 확인하는 키움 TOP200 & DIVA 분석기")

# 사이드바: 파일 업로드 및 설정
st.sidebar.header("📂 데이터 관리")
uploaded_file = st.sidebar.file_uploader("엑셀 파일을 업로드하세요", type=['xlsx'])

if uploaded_file:
    try:
        # 시트별 데이터 로드
        with st.spinner('데이터를 분석 중입니다...'):
            df_data = pd.read_excel(uploaded_file, sheet_name='DATA')
            df_diva = pd.read_excel(uploaded_file, sheet_name='DIVA')
            # FLOW 시트가 없을 경우를 대비한 처리
            try:
                df_flow = pd.read_excel(uploaded_file, sheet_name='FLOW')
            except:
                df_flow = pd.DataFrame()

        # 1. 날짜 선택 (VBA UserForm_Initialize 역할)
        all_dates = sorted(df_data['날짜'].unique(), reverse=True)
        target_date = st.sidebar.selectbox("분석 기준일(종료일) 선택", all_dates)
        
        # 2. 분석 유형 선택
        analysis_type = st.sidebar.selectbox("분석 유형 선택", 
            ["전체 종목 보기", "신규진입 종목", "계좌수 급증", "Super Signal", "내일 공략 TOP5"])

        # --- 메인 분석 로직 ---
        
        # 기준일 데이터 필터링
        current_df = df_data[df_data['날짜'] == target_date].copy()
        
        # DIVA 신호 매칭 (모듈 3 HighlightD

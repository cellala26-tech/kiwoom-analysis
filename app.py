import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
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

# 2. 수급 점수 계산
def calc_flow_score(row):
    s = 0
    f_net = safe_to_num(row.get('외국인순값', 0))
    i_net = safe_to_num(row.get('기관순값', 0))
    if f_net > 0: s += 40
    if i_net > 0: s += 40
    if f_net > 0 and i_net > 0: s += 60
    return s

# --- 화면 설정 ---
st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 자동 분석 시스템")

# 🚩 사장님 깃허브 정보 (파일을 직접 긁어오기 위한 설정)
GITHUB_BASE_URL = "https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/"

# 사장님이 올리신 파일 목록 (서버에서 파일명을 못 읽을 때를 대비해 최근 날짜 위주로 자동 매칭)
@st.cache_data
def load_data_from_github(date_str):
    try:
        # 1. 메인 데이터 로드
        data_url = f"{GITHUB_BASE_URL}{date_str}.xlsx"
        resp_data = requests.get(data_url)
        if resp_data.status_code != 200: return None, None, None
        df_data = pd.read_excel(BytesIO(resp_data.content))
        
        # 2. 수급 데이터 로드 (선택 사항)
        flow_url = f"{GITHUB_BASE_URL}{date_str}_수급.xlsx"
        resp_flow = requests.get(flow_url)
        df_flow = pd.read_excel(BytesIO(resp_flow.content)) if resp_flow.status_code == 200 else pd.DataFrame()
        
        # 3. DIVA 데이터 로드 (고정 파일명일 가능성이 높음)
        diva_url = f"{GITHUB_BASE_URL}DIVA.xlsx" # 만약 파일명이 다르면 수정 필요
        resp_diva = requests.get(diva_url)
        df_diva = pd.read_excel(BytesIO(resp_diva.content)) if resp_diva.status_code == 200 else pd.DataFrame()
        
        return df_data, df_flow, df_diva
    except:
        return None, None, None

# 사이드바에서 분석할 날짜 입력 (파일 목록을 못 가져오므로 직접 선택)
st.sidebar.header("🗓️ 날짜 설정")
target_date = st.sidebar.text_input("분석할 날짜를 입력하세요 (예: 2026-03-10)", value="2026-03-10")

if st.sidebar.button("데이터 불러오기"):
    df_data, df_flow, df_diva = load_data_from_github(target_date)
    
    if df_data is not None:
        result = df_data.copy()
        
        # DIVA 연동
        if not df_diva.empty:
            diva_latest = df_diva.sort_values(by=df_diva.columns[0]).groupby('종목명').last().reset_index()
            result = pd.merge(result, diva_latest, on='종목명', how='left', suffixes=('', '_diva'))
        
        # 수급 점수 계산
        if not df_flow.empty:
            df_flow['수급점수'] = df_flow.apply(calc_flow_score, axis=1)
            result = pd.merge(result, df_flow[['종목명', '수급점수']], on='종목명', how='left')
        
        result['현재가'] = result['현재가'].apply(safe_to_num)
        
        st.subheader(f"📊 {target_date} 분석 결과")
        
        def style_rows(row):
            is_diva = any(pd.notna(row.get(c)) for c in row.index if '신호' in str(c) or 'diva' in str(c))
            return ['background-color: #ffffcc' if is_diva else '' for _ in row]

        st.dataframe(result.style.apply(style_rows, axis=1).format({
            '현재가': '{:,.0f}', '수급점수': '{:.0f}'
        }, na_rep='-'), use_container_width=True)
    else:
        st.error(f"{target_date}.xlsx 파일을 찾을 수 없습니다. data 폴더에 파일이 있는지 확인해주세요.")
else:
    st.info("왼쪽에서 날짜를 입력하고 [데이터 불러오기] 버튼을 눌러주세요.")

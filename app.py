import streamlit as st
import pandas as pd
import numpy as np
import os
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

# 2. 수급 점수 계산 (VBA 로직)
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

# 깃허브 data 폴더 경로
DATA_DIR = "data"

@st.cache_data
def load_all_data():
    data_list = []
    flow_list = []
    diva_df = pd.DataFrame()

    if not os.path.exists(DATA_DIR):
        return None, None, None

    files = os.listdir(DATA_DIR)
    for fname in files:
        fpath = os.path.join(DATA_DIR, fname)
        if not fname.endswith('.xlsx'): continue

        if 'DIVA' in fname.upper():
            diva_df = pd.read_excel(fpath)
        elif '수급' in fname:
            temp = pd.read_excel(fpath)
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
            if date_match: temp['날짜'] = date_match.group()
            flow_list.append(temp)
        else:
            temp = pd.read_excel(fpath)
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
            if date_match: temp['날짜'] = date_match.group()
            data_list.append(temp)

    full_data = pd.concat(data_list, ignore_index=True) if data_list else pd.DataFrame()
    full_flow = pd.concat(flow_list, ignore_index=True) if flow_list else pd.DataFrame()
    
    return full_data, full_flow, diva_df

# 데이터 로딩
df_all_data, df_all_flow, df_diva = load_all_data()

if df_all_data is not None and not df_all_data.empty:
    # 날짜 선택
    all_dates = sorted(df_all_data['날짜'].unique(), reverse=True)
    target_date = st.sidebar.selectbox("📅 분석 날짜 선택", all_dates)
    
    # 분석 로직
    current_data = df_all_data[df_all_data['날짜'] == target_date].copy()
    
    # DIVA 연동
    if not df_diva.empty:
        diva_latest = df_diva.sort_values(by='날짜').groupby('종목명').last().reset_index()
        result = pd.merge(current_data, diva_latest[['종목명', '날짜', '종가']], on='종목명', how='left')
        result.rename(columns={'날짜_y': '디바신호일', '종가': '기준종가', '날짜_x': '날

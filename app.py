import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta

# --- 숫자 변환 및 계산 함수 ---
def safe_to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan'] else 0.0
    except: return 0.0

def calc_flow_score(row):
    s = 0
    # 외국인/기관 컬럼 유연하게 찾기
    f_col = [c for c in row.index if '외국인' in str(c) and ('순' in str(c) or '값' in str(c))]
    i_col = [c for c in row.index if '기관' in str(c) and ('순' in str(c) or '값' in str(c))]
    f_val = safe_to_num(row[f_col[0]]) if f_col else 0.0
    i_val = safe_to_num(row[i_col[0]]) if i_col else 0.0
    
    if f_val > 0: s += 40
    if i_val > 0: s += 40
    if f_val > 0 and i_val > 0: s += 60
    return s

def get_clean_df(content):
    for i in range(10):
        try:
            temp_df = pd.read_excel(BytesIO(content), skiprows=i)
            if '종목명' in temp_df.columns: return temp_df
        except: continue
    return pd.read_excel(BytesIO(content))

# --- 화면 설정 ---
st.set_page_config(layout="wide", page_title="키움 TOP200 분석기")
st.title("🍜 미미국밥 주식 분석 시스템")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

# --- 사이드바: VBA UserForm 디자인 완벽 재현 ---
st.sidebar.header("📂 키움 TOP200 분석")

# 1. 종료일/시작일 설정
end_date = st.sidebar.date_input("📅 종료일(기준일)", value=datetime(2026, 3, 11))

# 기간 퀵 설정 버튼
st.sidebar.write("⏱️ 기간 퀵 설정")
c1, c2, c3 = st.sidebar.columns(3)
with c1:
    if st.button("5일"): st.session_state.s_date = end_date - timedelta(days=5)
with c2:
    if st.button("10일"): st.session_state.s_date = end_date - timedelta(days=10)
with c3:
    if st.button("20일"): st.session_state.s_date = end_date - timedelta(days=20)

if 's_date' not in st.session_state:
    st.session_state.s_date = datetime(2026, 1, 28)

start_date = st.sidebar.date_input("📅 시작일", value=st.session_state.s_date)

# 2. 분석유형 드롭다운 (사장님 요청사항 100% 반영)
analysis_type = st.sidebar.selectbox("📋 분석유형", [
    "신규진입종목", 
    "계좌수 급증", 
    "매수수량 급증", 
    "순매매수량 급증", 
    "잠복 세력", 
    "super signal", 
    "내일 공략 top5", 
    "수급분석", 
    "디바일치종목"
])

run_btn = st.sidebar.button("🚀 분석 실행", use_container_width=True)

# --- 분석 실행 로직 ---
if run_btn:
    s_str = start_date.strftime('%Y-%m-%d')
    e_str = end_date.strftime('%Y-%m-%d')
    
    try:
        with st.spinner(f'{analysis_type} 분석 중...'):
            res_e = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
            res_s = requests.get(f"{GITHUB_BASE}{s_str}.xlsx")
            res_f = requests.get(f"{GITHUB_BASE}{e_str}_수급.xlsx")
            res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")

            if res_e.status_code == 200:
                df_e = get_clean_df(res_e.content)
                
                # 분석 타겟 설정
                target_col = '계좌수'
                if "매수수량" in analysis_type: target_col = '매수수량'
                elif "순매매수량" in analysis_type: target_col = '순매매수량'
                
                # 시작일 대조 (비교 분석용)
                if res_s.status_code == 200:
                    df_s = get_clean_df(res_s.content)
                    if target_col in df_s.columns:
                        df_e = pd.merge(df_e, df_s[['종목명', target_col]], on='종목명', how='left', suffixes=('_종료', '_시작'))
                        df_e[f'시작 {target_col}'] = df_e[f'{target_col}_시작'].fillna(0).apply(safe_to_num)
                        df_e[f'종료 {target_col}'] = df_e[f'{target_col}_종료'].fillna(0).apply(safe_to_num)
                        df_e['증가폭'] = df_e[f'종료 {target_col}'] - df_e[f'시작 {target_col}']
                
                # 수급/DIVA 연동
                if res_f.status_code == 200:
                    df_f = get_clean_df(res_f.content)
                    df_f['수급점수'] = df_f.apply(calc_flow_score, axis=1)
                    df_e = pd.merge(df_e, df_f[['종목명', '수급점수']], on='종목명', how='left')
                
                if res_v.status_code == 200:
                    v_df = get_clean_df(res_v.content)
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    df_e = pd.merge(df_e, v_last, on='종목명', how='left', suffixes=('', '_v'))

                # --- 분석유형별 정렬 및 필터 ---
                final_df = df_e.copy()
                if "급증" in analysis_type:
                    final_df = final_df.sort_values('증가폭', ascending=False)
                elif analysis_type == "신규진입종목":
                    final_df = final_df[final_df[f'{target_col}_시작'].isna()]
                elif analysis_type == "수급분석":
                    final_df = final_df.sort_values('수급점수', ascending=False)
                elif analysis_type == "잠복 세력":
                    final_df = final_df[(final_df['거래량'] < final_df['거래량'].median()) & (final_df['수급점수'] > 0)]
                
                # 컬럼 정리 및 출력
                final_df.rename(columns={'날짜': '디바신호일', '종가': '기준종가', '현재가': '현재종가'}, inplace=True)
                cols = ['순위', '종목명', f'시작 {target_col}', f'종료 {target_col}', '증가폭',

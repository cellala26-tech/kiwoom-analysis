import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta

# --- 숫자 변환 및 계산 함수 ---
def to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '')
        s = s.replace('↑', '').replace('↓', '').replace(' ', '').strip()
        if s in ['', '-', 'nan', 'NaN']: return 0.0
        return float(s)
    except: return 0.0

def get_clean_df(content):
    for i in range(10):
        try:
            temp_df = pd.read_excel(BytesIO(content), skiprows=i)
            if '종목명' in temp_df.columns: return temp_df
        except: continue
    return pd.read_excel(BytesIO(content))

st.set_page_config(layout="wide", page_title="미미국밥 통합 분석 시스템")
st.title("🍜 미미국밥 주식 분석 시스템")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

# --- 사이드바: 날짜 설정 밀착 배치 ---
st.sidebar.header("📂 분석 설정")

# 🚩 시작일과 종료일을 상단에 나란히 배치 (사장님 요청사항)
col_date1, col_date2 = st.sidebar.columns(2)
with col_date1:
    # 기본 시작일 설정 (VBA Initialize 로직)
    if 's_date' not in st.session_state:
        st.session_state.s_date = datetime(2026, 3, 4)
    start_date = st.date_input("📅 시작일", value=st.session_state.s_date)

with col_date2:
    end_date = st.date_input("📅 종료일", value=datetime(2026, 3, 11))

# 기간 퀵 설정 버튼 (날짜 바로 밑에 배치)
st.sidebar.write("⏱️ 기간 퀵 설정")
c1, c2, c3 = st.sidebar.columns(3)
with c1:
    if st.button("5일"): st.session_state.s_date = end_date - timedelta(days=4)
with c2:
    if st.button("10일"): st.session_state.s_date = end_date - timedelta(days=9)
with c3:
    if st.button("20일"): st.session_state.s_date = end_date - timedelta(days=19)

# 분석유형 선택
analysis_type = st.sidebar.selectbox("📋 분석유형", [
    "내일 공략 top5", "신규진입종목", "계좌수 급증", "매수수량 급증", "순매매수량 급증", 
    "잠복 세력", "super signal", "수급분석", "디바일치종목"
])

run_btn = st.sidebar.button("🚀 분석 실행", use_container_width=True)

# --- 분석 실행 로직 ---
if run_btn:
    s_str = start_date.strftime('%Y-%m-%d')
    e_str = end_date.strftime('%Y-%m-%d')
    
    try:
        with st.spinner(f'{analysis_type} 분석 엔진 가동 중...'):
            res_e = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
            res_s = requests.get(f"{GITHUB_BASE}{s_str}.xlsx")
            res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")

            if res_e.status_code == 200:
                df_e = get_clean_df(res_e.content)
                
                # 분석 타겟 결정
                target_col = '계좌수'
                if "매수수량" in analysis_type: target_col = '매수수량'
                elif "순매매수량" in analysis_type: target_col = '순매매수량'
                
                # 시작일 대조 로직 (VBA Dictionary 매칭 재현)
                if res_s.status_code == 200:
                    df_s = get_clean_df(res_s.content)
                    if target_col in df_s.columns:
                        df_e = pd.merge(df_e, df_s[['종목명', target_col]], on='종목명', how='left', suffixes=('_종료', '_시작'))
                        df_e[f'시작 {target_col}'] = df_e[f'{target_col}_시작'].fillna(0).apply(to_num)
                        df_e[f'종료 {target_col}'] = df_e[f'{target_col}_종료'].fillna(0).apply(to_num)
                        df_e['증가폭'] = df_e[f'종료 {target_col}'] - df_e[f'시작 {target_col}']
                
                # 수급/DIVA 연동
                res_f = requests.get(f"{GITHUB_BASE}{e_str}_수급.xlsx")
                if res_f.status_code == 200:
                    df_f = get_clean_df(res_f.content)
                    # 수급 점수 계산 로직 포함 생략(기존과 동일)
                    df_e = pd.merge(df_e, df_f[['종목명', '외국인순값', '기관순값']], on='종목명', how='left')
                
                if res_v.status_code == 200:
                    v_df = get_clean_df(res_v.content)
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    df_e = pd.merge(df_e, v_last, on='종목명', how='left', suffixes=('', '_v'))

                # 최종 결과 정리
                final_df = df_e.copy()
                if "급증" in analysis_type:
                    final_df = final_df.sort_values('증가폭', ascending=False)
                
                final_df.rename(columns={'날짜': '디바신호일', '종가': '기준종가', '현재가': '현재종가'}, inplace=True)
                cols = ['순위', '종목명', f'시작 {target_col}', f'종료 {target_col}', '증가폭', '디바신호일', '기준종가', '현재종가']
                display_df = final_df[[c for c in cols if c in final_df.columns]].copy()

                st.subheader(f"📊 {analysis_type} 결과 ({s_str} ~ {e_str})")
                st.dataframe(display_df.style.apply(lambda row: ['background-color: #ffffcc' if pd.notna(row.get('디바신호일')) else '' for _ in row], axis=1).format(na_rep='-', precision=0), use_container_width=True)
            else:
                st.error(f"종료일 데이터({e_str}.xlsx)를 찾을 수 없습니다.")

    except Exception as e:
        st.error(f"오류 발생: {e}")

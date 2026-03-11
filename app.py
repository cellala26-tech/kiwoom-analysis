import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime

# --- 숫자 변환 및 계산 함수 ---
def safe_to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan'] else 0.0
    except: return 0.0

def calc_flow_score(row):
    s = 0
    f_net = safe_to_num(row.get('외국인순값', 0))
    i_net = safe_to_num(row.get('기관순값', 0))
    if f_net > 0: s += 40
    if i_net > 0: s += 40
    if f_net > 0 and i_net > 0: s += 60
    return s

# --- 화면 설정 (사장님 스타일) ---
st.set_page_config(layout="wide", page_title="키움 TOP200 분석기")
st.title("🍜 미미국밥 주식 분석 시스템")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

# --- 사이드바: VBA UserForm 디자인 재현 ---
st.sidebar.header("📂 키움 TOP200 분석")

# 1. 시작일/종료일 선택
start_date = st.sidebar.date_input("📅 시작일", value=datetime(2026, 1, 28))
end_date = st.sidebar.date_input("📅 종료일", value=datetime(2026, 3, 11))

# 2. 분석유형 드롭다운 (사장님 사진 속 리스트 그대로!)
analysis_type = st.sidebar.selectbox("📋 분석유형", [
    "계좌수 급증", 
    "매수수량 급증", 
    "순매매수량 급증", 
    "잠복 세력", 
    "Super Signal", 
    "내일 공략 TOP5", 
    "수급 분석", 
    "디바 일치 종목"
])

# --- 분석 실행 로직 ---
if st.sidebar.button("🚀 분석 실행"):
    try:
        s_str = start_date.strftime('%Y-%m-%d')
        e_str = end_date.strftime('%Y-%m-%d')
        
        with st.spinner(f'{analysis_type} 로직으로 분석 중...'):
            # 기본 데이터 로드
            res_s = requests.get(f"{GITHUB_BASE}{s_str}.xlsx")
            res_e = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
            res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")
            res_f = requests.get(f"{GITHUB_BASE}{e_str}_수급.xlsx")

            if res_e.status_code != 200:
                st.error(f"종료일({e_str}) 데이터가 깃허브에 없습니다.")
            else:
                df_e = pd.read_excel(BytesIO(res_e.content))
                # 헤더 보정
                if '종목명' not in df_e.columns:
                    df_e = pd.read_excel(BytesIO(res_e.content), skiprows=3)
                
                # 시작일 데이터가 있을 경우 비교 분석
                if res_s.status_code == 200:
                    df_s = pd.read_excel(BytesIO(res_s.content))
                    if '종목명' not in df_s.columns:
                        df_s = pd.read_excel(BytesIO(res_s.content), skiprows=3)
                    
                    df_e = pd.merge(df_e, df_s[['종목명', '계좌수', '거래량']], on='종목명', how='left', suffixes=('_종료', '_시작'))
                    df_e['증가폭(계좌)'] = df_e['계좌수_종료'].apply(safe_to_num) - df_e['계좌수_시작'].apply(safe_to_num).fillna(0)
                
                # --- 분석유형별 필터 로직 ---
                result_df = df_e.copy()
                
                if analysis_type == "계좌수 급증":
                    result_df = result_df.sort_values(by='증가폭(계좌)', ascending=False)
                
                elif analysis_type == "잠복 세력":
                    # 예: 거래량은 적은데 계좌수는 늘어난 종목 (사장님 로직 대입 가능)
                    result_df = result_df[result_df['거래량'] < result_df['거래량'].median()]
                    result_df = result_df.sort_values(by='계좌수_종료', ascending=False)

                elif analysis_type == "수급 분석" and res_f.status_code == 200:
                    f_df = pd.read_excel(BytesIO(res_f.content))
                    f_df['수급점수'] = f_df.apply(calc_flow_score, axis=1)
                    result_df = pd.merge(result_df, f_df[['종목명', '수급점수']], on='종목명', how='left')
                    result_df = result_df.sort_values(by='수급점수', ascending=False)

                # DIVA 연동 (노란색 하이라이트)
                if res_v.status_code == 200:
                    v_df = pd.read_excel(BytesIO(res_v.content))
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    result_df = pd.merge(result_df, v_last, on='종목명', how='left', suffixes=('', '_v'))

                # --- 결과 출력 ---
                st.subheader(f"📊 {analysis_type} 분석 리포트 ({s_str} ~ {e_str})")
                
                def style_diva(row):
                    # DIVA 신호가 있으면 엑셀처럼 노란색 하이라이트
                    is_v = any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c) or '날짜' == str(c))
                    return ['background-color: #ffffcc' if is_v else '' for _ in row]

                st.dataframe(result_df.style.apply(style_diva, axis=1).format(na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")

# --- 하단 버튼 디자인 (VBA와 동일) ---
col1, col2 = st.columns(2)
with col1:
    if st.button("종목이력검색"):
        st.write("🔍 종목 이력 검색 기능을 준비 중입니다.")

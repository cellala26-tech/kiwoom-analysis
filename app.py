import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta

# 숫자 변환 보조 함수
def safe_to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan'] else 0.0
    except: return 0.0

st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 주식 분석 시스템")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

# --- 사이드바 설정 ---
st.sidebar.header("📂 분석 설정")
end_date = st.sidebar.date_input("기준일(종료일)", value=datetime(2026, 3, 11))
analysis_type = st.sidebar.selectbox("📋 분석유형", [
    "계좌수 급증", "매수수량 급증", "순매매수량 급증", 
    "잠복 세력", "Super Signal", "내일 공략 TOP5", 
    "수급 분석", "디바 일치 종목"
])

# --- 메인 화면: 기간 선택 탭 (사장님 요청사항) ---
st.write("### 📅 분석 기간 선택")
tab5, tab10, tab20 = st.tabs(["최근 5일", "최근 10일", "최근 20일"])

def run_analysis(days):
    try:
        e_str = end_date.strftime('%Y-%m-%d')
        # 기준일로부터 n일 전 날짜 계산
        s_date = end_date - timedelta(days=days)
        s_str = s_date.strftime('%Y-%m-%d')
        
        with st.spinner(f'최근 {days}일 데이터 분석 중...'):
            res_e = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
            res_s = requests.get(f"{GITHUB_BASE}{s_str}.xlsx")
            res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")

            if res_e.status_code != 200:
                st.warning(f"{e_str} 데이터가 없습니다.")
                return

            df_e = pd.read_excel(BytesIO(res_e.content))
            if '종목명' not in df_e.columns: df_e = pd.read_excel(BytesIO(res_e.content), skiprows=3)

            # 시작일 데이터와 대조
            if res_s.status_code == 200:
                df_s = pd.read_excel(BytesIO(res_s.content))
                if '종목명' not in df_s.columns: df_s = pd.read_excel(BytesIO(res_s.content), skiprows=3)
                
                df_merged = pd.merge(df_e, df_s[['종목명', '계좌수']], on='종목명', how='left', suffixes=('_종료', '_시작'))
                df_merged['증가폭(계좌)'] = df_merged['계좌수_종료'].apply(safe_to_num) - df_merged['계좌수_시작'].apply(safe_to_num).fillna(0)
            else:
                df_merged = df_e.copy()
                df_merged['증가폭(계좌)'] = 0
                st.info(f"{s_str}({days}일 전) 데이터가 없어 증감폭 계산이 제한됩니다.")

            # DIVA 연동
            if res_v.status_code == 200:
                v_df = pd.read_excel(BytesIO(res_v.content))
                v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                df_merged = pd.merge(df_merged, v_last, on='종목명', how='left', suffixes=('', '_v'))

            # 결과 출력
            st.write(f"#### 📊 {days}일 분석 결과 ({s_str} ~ {e_str})")
            
            def style_diva(row):
                is_v = any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c) or '날짜' == str(c))
                return ['background-color: #ffffcc' if is_v else '' for _ in row]

            st.dataframe(df_merged.style.apply(style_diva, axis=1).format(na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류: {e}")

# 각 탭 클릭 시 해당 기간 분석 실행
with tab5:
    run_analysis(5)
with tab10:
    run_analysis(10)
with tab20:
    run_analysis(20)

# --- 하단 버튼 (VBA 스타일) ---
st.divider()
if st.button("🚀 전체 데이터 다시 읽기"):
    st.cache_data.clear()
    st.rerun()

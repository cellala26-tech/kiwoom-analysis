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

# --- CSS로 버튼 디자인 살짝 변경 (VBA 느낌) ---
st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: #f0f2f6;
        border: 1px solid #d1d1d1;
        width: 100%;
        height: 3em;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🍜 미미국밥 주식 분석 시스템")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

# --- 사이드바: VBA UserForm 구성 ---
st.sidebar.header("📂 분석 설정")
end_date = st.sidebar.date_input("기준일(종료일)", value=datetime(2026, 3, 11))
analysis_type = st.sidebar.selectbox("📋 분석유형", [
    "계좌수 급증", "매수수량 급증", "순매매수량 급증", 
    "잠복 세력", "Super Signal", "내일 공략 TOP5", 
    "수급 분석", "디바 일치 종목"
])

period_option = st.sidebar.selectbox("📅 분석 기간", ["최근 5일", "최근 10일", "최근 20일"])

# 드디어 부활한 [분석 실행] 버튼!
run_btn = st.sidebar.button("🔍 분석 실행")

# --- 메인 화면 결과 출력 ---
if run_btn:
    # 선택된 기간 계산
    days = int(period_option.replace("최근 ", "").replace("일", ""))
    s_date = end_date - timedelta(days=days)
    
    e_str = end_date.strftime('%Y-%m-%d')
    s_str = s_date.strftime('%Y-%m-%d')
    
    try:
        with st.spinner(f'{period_option} 데이터를 분석 중입니다...'):
            res_e = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
            res_s = requests.get(f"{GITHUB_BASE}{s_str}.xlsx")
            res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")

            if res_e.status_code != 200:
                st.error(f"기준일({e_str}) 데이터가 깃허브에 없습니다.")
            else:
                df_e = pd.read_excel(BytesIO(res_e.content))
                if '종목명' not in df_e.columns: df_e = pd.read_excel(BytesIO(res_e.content), skiprows=3)

                # 시작일 대조 및 증감 계산
                if res_s.status_code == 200:
                    df_s = pd.read_excel(BytesIO(res_s.content))
                    if '종목명' not in df_s.columns: df_s = pd.read_excel(BytesIO(res_s.content), skiprows=3)
                    
                    df_merged = pd.merge(df_e, df_s[['종목명', '계좌수']], on='종목명', how='left', suffixes=('_종료', '_시작'))
                    df_merged['증가폭(계좌)'] = df_merged['계좌수_종료'].apply(safe_to_num) - df_merged['계좌수_시작'].apply(safe_to_num).fillna(0)
                else:
                    df_merged = df_e.copy()
                    st.warning(f"{s_str}({days}일 전) 데이터가 없어 비교 분석이 제외되었습니다.")

                # DIVA 연동 (노란색 하이라이트)
                if res_v.status_code == 200:
                    v_df = pd.read_excel(BytesIO(res_v.content))
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    df_merged = pd.merge(df_merged, v_last, on='종목명', how='left', suffixes=('', '_v'))

                st.subheader(f"📊 {period_option} {analysis_type} 결과 ({s_str} ~ {e_str})")
                
                def style_diva(row):
                    is_v = any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c) or '날짜' == str(c))
                    return ['background-color: #ffffcc' if is_v else '' for _ in row]

                st.dataframe(df_merged.style.apply(style_diva, axis=1).format(na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")

else:
    st.info("왼쪽 설정에서 날짜와 분석 유형을 선택한 후 [분석 실행] 버튼을 눌러주세요.")

# --- 하단 버튼 공간 ---
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("닫기"):
        st.write("화면을 새로고침 하시면 초기화됩니다.")
with col2:
    if st.button("종목이력검색"):
        st.write("🔍 검색 기능을 준비 중입니다.")

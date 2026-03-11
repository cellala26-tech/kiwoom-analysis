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

# 수급 점수 계산 (VBA 로직)
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

st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 주식 분석 시스템")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

# --- 사이드바 설정 ---
st.sidebar.header("📂 분석 설정")
end_date = st.sidebar.date_input("기준일(종료일)", value=datetime(2026, 3, 11))
analysis_type = st.sidebar.selectbox("📋 분석유형", [
    "수급 분석", "계좌수 급증", "신규진입 종목", "잠복 세력"
])
period_option = st.sidebar.selectbox("📅 분석 기간", ["최근 5일", "최근 10일", "최근 20일"])

run_btn = st.sidebar.button("🔍 분석 실행")

if run_btn:
    days = int(period_option.replace("최근 ", "").replace("일", ""))
    e_str = end_date.strftime('%Y-%m-%d')
    s_date = end_date - timedelta(days=days)
    s_str = s_date.strftime('%Y-%m-%d')
    
    try:
        with st.spinner(f'{analysis_type} 분석 중...'):
            # 데이터 로드
            res_e = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")       # TOP200 파일
            res_f = requests.get(f"{GITHUB_BASE}{e_str}_수급.xlsx")  # 수급 파일
            res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")        # DIVA 파일
            
            if res_e.status_code != 200:
                st.error(f"기준일 데이터({e_str}.xlsx)가 없습니다.")
            else:
                # 1. 기본 TOP200 데이터 읽기
                df_e = pd.read_excel(BytesIO(res_e.content))
                if '종목명' not in df_e.columns: df_e = pd.read_excel(BytesIO(res_e.content), skiprows=3)
                
                # --- 수급 분석 모드일 때 ---
                if analysis_type == "수급 분석":
                    if res_f.status_code == 200:
                        df_f = pd.read_excel(BytesIO(res_f.content))
                        if '종목명' not in df_f.columns: df_f = pd.read_excel(BytesIO(res_f.content), skiprows=1)
                        
                        # 점수 계산 및 TOP200 여부 표시
                        df_f['수급점수'] = df_f.apply(calc_flow_score, axis=1)
                        df_e['TOP200등장'] = "180 YES"
                        
                        # 병합 (수급 데이터 기준)
                        final_df = pd.merge(df_f, df_e[['종목명', '순위', 'TOP200등장']], on='종목명', how='left')
                        
                        # 사장님 엑셀과 동일한 컬럼 순서
                        cols = ['순위', '종목코드', '종목명', '외국인순값', '기관순값', '수급점수', 'TOP200등장']
                        final_df = final_df[[c for c in cols if c in final_df.columns]].sort_values('수급점수', ascending=False)
                    else:
                        st.warning("수급 파일이 없어 일반 조회를 실행합니다.")
                        final_df = df_e
                
                # --- 계좌수 급증 등 다른 분석 모드 ---
                else:
                    res_s = requests.get(f"{GITHUB_BASE}{s_str}.xlsx")
                    if res_s.status_code == 200:
                        df_s = pd.read_excel(BytesIO(res_s.content))
                        if '종목명' not in df_s.columns: df_s = pd.read_excel(BytesIO(res_s.content), skiprows=3)
                        
                        df_e['시작계좌수'] = pd.merge(df_e, df_s[['종목명', '계좌수']], on='종목명', how='left')['계좌수_y'].apply(safe_to_num)
                        df_e['증가폭'] = df_e['계좌수'].apply(safe_to_num) - df_e['시작계좌수']
                        final_df = df_e.sort_values('증가폭', ascending=False)
                    else:
                        final_df = df_e
                
                # 2. DIVA 하이라이트 연동
                if res_v.status_code == 200:
                    v_df = pd.read_excel(BytesIO(res_v.content))
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    final_df = pd.merge(final_df, v_last, on='종목명', how='left', suffixes=('', '_v'))

                st.subheader(f"📊 {period_option} {analysis_type} 결과")
                
                def style_diva(row):
                    is_v = any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c) or '날짜' == str(c))
                    return ['background-color: #ffffcc' if is_v else '' for _ in row]

                st.dataframe(final_df.style.apply(style_diva, axis=1).format({
                    '현재가': '{:,.0f}', '외국인순값': '{:.1f}', '기관순값': '{:.1f}', '수급점수': '{:.0f}'
                }, na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류: {e}")

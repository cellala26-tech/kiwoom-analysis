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

# 수급 점수 계산 로직
def calc_flow_score(row):
    s = 0
    f_net = safe_to_num(row.get('외국인순값', 0))
    i_net = safe_to_num(row.get('기관순값', 0))
    if f_net > 0: s += 40
    if i_net > 0: s += 40
    if f_net > 0 and i_net > 0: s += 60
    return s

st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 주식 분석 시스템")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

# --- 사이드바: VBA UserForm 완벽 재현 ---
st.sidebar.header("📂 분석 설정")

# 1. 종료일(기준일) 설정
end_date = st.sidebar.date_input("📅 종료일(기준일)", value=datetime(2026, 3, 11))

# 2. 최근 기간 퀵 선택 버튼 (사장님 요청사항 부활!)
st.sidebar.write("⏱️ 기간 퀵 설정")
col_a, col_b, col_c = st.sidebar.columns(3)
with col_a:
    if st.button("5일"):
        st.session_state.start_date = end_date - timedelta(days=5)
with col_b:
    if st.button("10일"):
        st.session_state.start_date = end_date - timedelta(days=10)
with col_c:
    if st.button("20일"):
        st.session_state.start_date = end_date - timedelta(days=20)

# 세션 상태를 이용한 시작일 동기화
if 'start_date' not in st.session_state:
    st.session_state.start_date = end_date - timedelta(days=5)

start_date = st.sidebar.date_input("📅 시작일", value=st.session_state.start_date)

# 3. 분석 유형 및 실행
analysis_type = st.sidebar.selectbox("📋 분석유형", [
    "수급 분석", "계좌수 급증", "신규진입 종목", "잠복 세력", "Super Signal"
])

run_btn = st.sidebar.button("🚀 분석 실행", use_container_width=True)

# --- 분석 로직 (이전과 동일하게 정밀 유지) ---
if run_btn:
    s_str = start_date.strftime('%Y-%m-%d')
    e_str = end_date.strftime('%Y-%m-%d')
    
    try:
        with st.spinner(f'{s_str} ~ {e_str} 분석 중...'):
            res_e = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
            res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")
            
            if res_e.status_code != 200:
                st.error(f"종료일 데이터({e_str}.xlsx)가 없습니다.")
            else:
                df_e = pd.read_excel(BytesIO(res_e.content))
                if '종목명' not in df_e.columns: df_e = pd.read_excel(BytesIO(res_e.content), skiprows=3)

                # 수급 분석 로직
                if analysis_type == "수급 분석":
                    all_flow_dfs = []
                    curr = start_date
                    while curr <= end_date:
                        d_str = curr.strftime('%Y-%m-%d')
                        res_f = requests.get(f"{GITHUB_BASE}{d_str}_수급.xlsx")
                        if res_f.status_code == 200:
                            tmp = pd.read_excel(BytesIO(res_f.content))
                            if '종목명' not in tmp.columns: tmp = pd.read_excel(BytesIO(res_f.content), skiprows=1)
                            all_flow_dfs.append(tmp[['종목명', '외국인순값', '기관순값']])
                        curr += timedelta(days=1)
                    
                    if all_flow_dfs:
                        df_flow_sum = pd.concat(all_flow_dfs).groupby('종목명').sum().reset_index()
                        df_flow_sum['수급점수'] = df_flow_sum.apply(calc_flow_score, axis=1)
                        df_e['TOP200등장'] = "180 YES"
                        final_df = pd.merge(df_flow_sum, df_e[['종목명', '순위', 'TOP200등장']], on='종목명', how='left')
                        final_df = final_df.sort_values('수급점수', ascending=False)
                    else:
                        st.error("해당 기간의 수급 파일이 없습니다.")
                        final_df = df_e

                # 계좌수 급증 로직
                elif analysis_type == "계좌수 급증":
                    res_s = requests.get(f"{GITHUB_BASE}{s_str}.xlsx")
                    if res_s.status_code == 200:
                        df_s = pd.read_excel(BytesIO(res_s.content))
                        if '종목명' not in df_s.columns: df_s = pd.read_excel(BytesIO(res_s.content), skiprows=3)
                        df_merged = pd.merge(df_e, df_s[['종목명', '계좌수']], on='종목명', how='left', suffixes=('_종료', '_시작'))
                        df_merged['증가폭'] = df_merged['계좌수_종료'].apply(safe_to_num) - df_merged['계좌수_시작'].apply(safe_to_num).fillna(0)
                        final_df = df_merged.sort_values('증가폭', ascending=False)
                    else:
                        final_df = df_e

                # DIVA 연동
                if res_v.status_code == 200:
                    v_df = pd.read_excel(BytesIO(res_v.content))
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    final_df = pd.merge(final_df, v_last, on='종목명', how='left', suffixes=('', '_v'))

                st.subheader(f"📊 {analysis_type} 결과 ({s_str} ~ {e_str})")
                
                def style_diva(row):
                    is_v = any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c) or '날짜' == str(c))
                    return ['background-color: #ffffcc' if is_v else '' for _ in row]

                st.dataframe(final_df.style.apply(style_diva, axis=1).format({
                    '외국인순값': '{:.1f}', '기관순값': '{:.1f}', '수급점수': '{:.0f}'
                }, na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")

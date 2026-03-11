import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta

# 숫자 변환 보조 함수 (정수로 깔끔하게 변환)
def safe_to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        # 콤마, 특수문자 제거 후 실수로 먼저 변환
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        if s in ['', '-', 'nan', 'NaN']: return 0.0
        return float(s)
    except:
        return 0.0

# 수급 점수 계산 로직 (VBA 일치)
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

# --- 사이드바: VBA UserForm 디자인 ---
st.sidebar.header("📂 분석 설정")

# 종료일(기준일) 설정
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
    st.session_state.s_date = datetime(2026, 1, 28) # 사장님 엑셀 기준일

start_date = st.sidebar.date_input("📅 시작일", value=st.session_state.s_date)

analysis_type = st.sidebar.selectbox("📋 분석유형", ["계좌수 급증", "수급 분석", "신규진입 종목", "잠복 세력"])
run_btn = st.sidebar.button("🚀 분석 실행", use_container_width=True)

if run_btn:
    s_str = start_date.strftime('%Y-%m-%d')
    e_str = end_date.strftime('%Y-%m-%d')
    
    try:
        with st.spinner(f'데이터 분석 중...'):
            res_s = requests.get(f"{GITHUB_BASE}{s_str}.xlsx")
            res_e = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
            res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")

            if res_s.status_code != 200 or res_e.status_code != 200:
                st.error(f"데이터를 찾을 수 없습니다. (시작:{s_str}, 종료:{e_str})")
            else:
                df_s = pd.read_excel(BytesIO(res_s.content), skiprows=3)
                df_e = pd.read_excel(BytesIO(res_e.content), skiprows=3)

                # 1. 계좌수 급증 로직
                df_merged = pd.merge(df_e, df_s[['종목명', '계좌수']], on='종목명', how='left', suffixes=('_종료', '_시작'))
                
                df_merged['시작 계좌수'] = df_merged['계좌수_시작'].fillna(0).apply(safe_to_num)
                df_merged['종료 계좌수'] = df_merged['계좌수_종료'].fillna(0).apply(safe_to_num)
                df_merged['증가폭'] = df_merged['종료 계좌수'] - df_merged['시작 계좌수']
                
                # 2. 수급점수 (종료일 파일 기준 우선 계산)
                res_f = requests.get(f"{GITHUB_BASE}{e_str}_수급.xlsx")
                if res_f.status_code == 200:
                    df_f = pd.read_excel(BytesIO(res_f.content), skiprows=1)
                    df_f['수급점수'] = df_f.apply(calc_flow_score, axis=1)
                    df_merged = pd.merge(df_merged, df_f[['종목명', '수급점수']], on='종목명', how='left')

                # 3. DIVA 연동
                if res_v.status_code == 200:
                    v_df = pd.read_excel(BytesIO(res_v.content))
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    df_merged = pd.merge(df_merged, v_last, on='종목명', how='left', suffixes=('', '_v'))

                # 분석 유형별 정렬
                if analysis_type == "계좌수 급증":
                    final_df = df_merged.sort_values('증가폭', ascending=False)
                elif analysis_type == "수급 분석":
                    final_df = df_merged.sort_values('수급점수', ascending=False)
                else:
                    final_df = df_merged

                # 컬럼 및 포맷팅 정리
                # 엑셀 화면 컬럼: 순위, 종목코드, 종목명, 시작 계좌수, 종료 계좌수, 증가폭, 디바신호일, 기준종가, 현재종가, 상승률, 수급점수
                final_df.rename(columns={'날짜': '디바신호일', '종가': '기준종가', '현재가': '현재종가'}, inplace=True)
                
                # 상승률 계산
                final_df['현재종가'] = final_df['현재종가'].apply(safe_to_num)
                final_df['기준종가'] = final_df['기준종가'].apply(safe_to_num)
                final_df['상승률'] = np.where(final_df['기준종가'] > 0, 
                                          ((final_df['현재종가'] - final_df['기준종가']) / final_df['기준종가'] * 100).round(2), 0.0)

                output_cols = ['순위', '종목코드', '종목명', '시작 계좌수', '종료 계좌수', '증가폭', '디바신호일', '기준종가', '현재종가', '상승률', '수급점수']
                display_df = final_df[[c for c in output_cols if c in final_df.columns]].copy()

                st.subheader(f"📊 {analysis_type} 분석 결과")
                
                def style_diva(row):
                    # 디바신호일이 있으면 노란색
                    return ['background-color: #ffffcc' if pd.notna(row.get('디바신호일')) else '' for _ in row]

                # 🚩 모든 수치에서 소수점 제거 ({:,.0f} 적용)
                st.dataframe(display_df.style.apply(style_diva, axis=1).format({
                    '시작 계좌수': '{:,.0f}', 
                    '종료 계좌수': '{:,.0f}', 
                    '증가폭': '{:,.0f}', 
                    '기준종가': '{:,.0f}', 
                    '현재종가': '{:,.0f}', 
                    '수급점수': '{:,.0f}',
                    '상승률': '{:.2f}%' # 상승률만 소수점 2자리 유지
                }, na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")

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
        if s in ['', '-', 'nan', 'NaN']: return 0.0
        return float(s)
    except:
        return 0.0

# 🚩 제목 줄을 자동으로 찾아내는 마법의 함수
def get_clean_df(content):
    # 일단 읽어보고 '종목명'이 없으면 한 줄씩 건너뛰며 시도
    for i in range(10):  # 상단 10줄까지 뒤져봅니다
        try:
            temp_df = pd.read_excel(BytesIO(content), skiprows=i)
            if '종목명' in temp_df.columns:
                return temp_df
        except:
            continue
    # 그래도 못 찾으면 그냥 첫 줄부터 읽음
    return pd.read_excel(BytesIO(content))

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

# --- 사이드바 설정 ---
st.sidebar.header("📂 분석 설정")
end_date = st.sidebar.date_input("📅 종료일(기준일)", value=datetime(2026, 3, 11))

# 기간 퀵 설정
st.sidebar.write("⏱️ 기간 퀵 설정")
c1, c2, c3 = st.sidebar.columns(3)
with c1:
    if st.button("5일"): st.session_state.s_date = end_date - timedelta(days=5)
with c2:
    if st.button("10일"): st.session_state.s_date = end_date - timedelta(days=10)
with c3:
    if st.button("20일"): st.session_state.s_date = end_date - timedelta(days=20)

if 's_date' not in st.session_state:
    st.session_state.s_date = datetime(2026, 3, 6)

start_date = st.sidebar.date_input("📅 시작일", value=st.session_state.s_date)
analysis_type = st.sidebar.selectbox("📋 분석유형", ["계좌수 급증", "수급 분석", "신규진입 종목"])
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
                # 🚩 마법의 함수로 깨끗한 데이터프레임 획득
                df_s = get_clean_df(res_s.content)
                df_e = get_clean_df(res_e.content)

                # 계좌수 데이터 병합
                df_merged = pd.merge(df_e, df_s[['종목명', '계좌수']], on='종목명', how='left', suffixes=('_종료', '_시작'))
                
                df_merged['시작 계좌수'] = df_merged['계좌수_시작'].fillna(0).apply(safe_to_num)
                df_merged['종료 계좌수'] = df_merged['계좌수_종료'].fillna(0).apply(safe_to_num)
                df_merged['증가폭'] = df_merged['종료 계좌수'] - df_merged['시작 계좌수']
                
                # 수급 데이터 (파일명에 날짜 포함 확인)
                res_f = requests.get(f"{GITHUB_BASE}{e_str}_수급.xlsx")
                if res_f.status_code == 200:
                    df_f = get_clean_df(res_f.content)
                    df_f['수급점수'] = df_f.apply(calc_flow_score, axis=1)
                    df_merged = pd.merge(df_merged, df_f[['종목명', '수급점수']], on='종목명', how='left')

                # DIVA 연동
                if res_v.status_code == 200:
                    v_df = get_clean_df(res_v.content)
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    df_merged = pd.merge(df_merged, v_last, on='종목명', how='left', suffixes=('', '_v'))

                # 분석 정렬
                if analysis_type == "계좌수 급증":
                    final_df = df_merged.sort_values('증가폭', ascending=False)
                elif analysis_type == "수급 분석":
                    final_df = df_merged.sort_values('수급점수', ascending=False)
                else:
                    final_df = df_merged

                # 엑셀과 동일한 컬럼 세팅
                final_df.rename(columns={'날짜': '디바신호일', '종가': '기준종가', '현재가': '현재종가'}, inplace=True)
                
                output_cols = ['순위', '종목코드', '종목명', '시작 계좌수', '종료 계좌수', '증가폭', '디바신호일', '기준종가', '현재종가', '수급점수']
                display_df = final_df[[c for c in output_cols if c in final_df.columns]].copy()

                st.subheader(f"📊 {analysis_type} 결과 ({s_str} ~ {e_str})")
                
                # 정수 포맷팅 및 스타일링
                st.dataframe(display_df.style.apply(lambda row: ['background-color: #ffffcc' if pd.notna(row.get('디바신호일')) else '' for _ in row], axis=1).format({
                    '시작 계좌수': '{:,.0f}', '종료 계좌수': '{:,.0f}', '증가폭': '{:,.0f}', 
                    '기준종가': '{:,.0f}', '현재종가': '{:,.0f}', '수급점수': '{:,.0f}'
                }, na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")

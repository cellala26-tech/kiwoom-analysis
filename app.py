import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime

# --- 숫자 변환 함수 (VBA ToNum 재현) ---
def to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan', 'NaN'] else 0.0
    except: return 0.0

# --- 엑셀 로드 및 클리닝 ---
def get_clean_df(content, target_keyword='종목명'):
    for i in range(15):
        try:
            temp_df = pd.read_excel(BytesIO(content), skiprows=i)
            matches = [col for col in temp_df.columns if target_keyword in str(col)]
            if matches:
                temp_df = temp_df.loc[:, ~temp_df.columns.duplicated()]
                return temp_df.rename(columns={matches[0]: target_keyword})
        except: continue
    return pd.DataFrame()

st.set_page_config(layout="wide", page_title="키움 VBA 웹 시스템")
st.title("🖥️ 키움 통합 분석 시스템 (VBA 로직 완벽 이식)")

# --- 사이드바 설정 ---
st.sidebar.header("📂 분석 설정")
col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.sidebar.date_input("📅 시작일", value=datetime(2026, 3, 5))
with col2:
    end_date = st.sidebar.date_input("📅 종료일", value=datetime(2026, 3, 11))

run_btn = st.sidebar.button("🚀 내일 공략 TOP5 분석 실행", use_container_width=True)

if run_btn:
    try:
        GITHUB_BASE = "https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/"
        e_str = end_date.strftime('%Y-%m-%d')
        s_str = start_date.strftime('%Y-%m-%d')
        
        with st.spinner('VBA 분석 엔진 가동 중...'):
            # 1. 🚩 FLOW.xlsx (정답지) 로드
            res_flow = requests.get(f"{GITHUB_BASE}FLOW.xlsx")
            if res_flow.status_code != 200:
                st.error("FLOW.xlsx 파일을 찾을 수 없습니다.")
            else:
                flow_df = get_clean_df(res_flow.content, '종목명')
                date_col = flow_df.columns[0]
                flow_df[date_col] = pd.to_datetime(flow_df[date_col]).dt.strftime('%Y-%m-%d')
                
                # 기간 필터링
                mask = (flow_df[date_col] >= s_str) & (flow_df[date_col] <= e_str)
                period_data = flow_df.loc[mask].copy()

                if period_data.empty:
                    st.warning("선택 기간의 데이터가 없습니다.")
                else:
                    # 2. 🚩 VBA 핵심 로직: 등장횟수 및 수급점수 집계
                    stats = period_data.groupby('종목명').size().reset_index(name='등장횟수')
                    
                    # 종료일 기준 수급 점수 및 데이터
                    today_data = period_data[period_data[date_col] == e_str].copy()
                    score_col = [c for c in today_data.columns if '점수' in str(c)][0]
                    
                    # 데이터 병합
                    final_df = pd.merge(today_data, stats, on='종목명', how='left')
                    
                    # 3. 🚩 TOP200 파일에서 종목 정보 가져오기
                    res_top = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
                    if res_top.status_code == 200:
                        top_df = get_clean_df(res_top.content, '종목명')
                        # 현재가 -> 현재종가
                        price_col = [c for c in top_df.columns if '현재' in str(c) or '종가' in str(c)]
                        if price_col: top_df.rename(columns={price_col[0]: '현재종가'}, inplace=True)
                        
                        final_df = pd.merge(final_df, top_df[['종목명', '순위', '종목코드', '계좌수', '현재종가']], on='종목명', how='left')

                    # 4. 🚩 [내일 공략 TOP5] 정렬 기준 (VBA와 동일)
                    # 기준: 등장횟수(내림) -> 수급점수(내림) -> 순위(오름)
                    final_df = final_df.sort_values(
                        by=['등장횟수', score_col, '순위'], 
                        ascending=[False, False, True]
                    )

                    # 5. 출력 컬럼 및 포맷 (사장님 RESULT 시트 재현)
                    cols = ['순위', '종목코드', '종목명', '등장횟수', score_col, '계좌수', '현재종가']
                    result_top5 = final_df[cols].head(5)

                    st.subheader(f"📊 내일 공략 TOP 5 ({e_str})")
                    st.table(result_top5.style.format(precision=0, na_rep='-')) # 표 형식으로 깔끔하게

                    with st.expander("🔍 전체 분석 리스트 보기"):
                        st.dataframe(final_df[cols].style.format(precision=0), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")

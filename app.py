import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime

# --- 숫자 및 종목코드 변환 ---
def to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan', 'NaN'] else 0.0
    except: return 0.0

def format_code(v):
    if pd.isna(v) or v is None: return ""
    try: return str(int(to_num(v))).zfill(6)
    except: return str(v).strip()

# --- 엑셀 파일 읽기 보조 함수 ---
def get_clean_df(content, target_keyword='종목명'):
    for i in range(15):
        try:
            temp_df = pd.read_excel(BytesIO(content), skiprows=i)
            matches = [col for col in temp_df.columns if target_keyword in str(col)]
            if matches:
                temp_df = temp_df.loc[:, ~temp_df.columns.duplicated()]
                df = temp_df.rename(columns={matches[0]: target_keyword})
                if '종목코드' in df.columns: df['종목코드'] = df['종목코드'].apply(format_code)
                return df
        except: continue
    return pd.DataFrame()

st.set_page_config(layout="wide", page_title="키움 FLOW 분석기")
st.title("📊 사장님 FLOW 시트 기반 데이터 추출 시스템")

# --- 사이드바 설정 ---
st.sidebar.header("📂 분석 설정")
col_date1, col_date2 = st.sidebar.columns(2)
with col_date1:
    start_date = st.sidebar.date_input("📅 시작일", value=datetime(2026, 3, 5))
with col_date2:
    end_date = st.sidebar.date_input("📅 종료일", value=datetime(2026, 3, 11))

run_btn = st.sidebar.button("🚀 데이터 추출 및 결과 출력", use_container_width=True)

if run_btn:
    try:
        GITHUB_DATA = "https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/"
        s_str = start_date.strftime('%Y-%m-%d')
        e_str = end_date.strftime('%Y-%m-%d')
        
        with st.spinner('FLOW.xlsx 파일을 읽어 결과값을 추출 중입니다...'):
            # 1. 사장님의 FLOW 엑셀 파일 로드
            res_flow = requests.get(f"{GITHUB_DATA}FLOW.xlsx")
            if res_flow.status_code != 200:
                st.error("깃허브 'data' 폴더에 'FLOW.xlsx' 파일이 있는지 확인해 주세요.")
            else:
                # FLOW 시트 읽기
                df_flow = get_clean_df(res_flow.content, '종목명')
                
                # 날짜 컬럼(첫 번째 컬럼)을 기준으로 기간 필터링
                date_col = df_flow.columns[0]
                df_flow[date_col] = pd.to_datetime(df_flow[date_col]).dt.strftime('%Y-%m-%d')
                
                # 설정한 시작일~종료일 사이의 데이터만 추출
                mask = (df_flow[date_col] >= s_str) & (df_flow[date_col] <= e_str)
                filtered_flow = df_flow.loc[mask].copy()

                if filtered_flow.empty:
                    st.warning(f"{s_str}부터 {e_str} 사이의 데이터가 FLOW 파일에 없습니다.")
                else:
                    # 2. 엑셀 로직 그대로: 종목별로 묶어서 결과값 정리
                    # 등장횟수(등장날짜 수) 계산
                    counts = filtered_flow.groupby('종목명').size().reset_index(name='등장횟수')
                    
                    # 가장 최근(종료일 기준) 수급 정보 매칭
                    latest_data = filtered_flow[filtered_flow[date_col] == e_str].copy()
                    final_result = pd.merge(latest_data, counts, on='종목명', how='left')
                    
                    # 3. 추가 정보 병합 (TOP200 계좌수 등)
                    res_top = requests.get(f"{GITHUB_DATA}{e_str}.xlsx")
                    if res_top.status_code == 200:
                        df_top = get_clean_df(res_top.content)
                        if '현재가' in df_top.columns: df_top.rename(columns={'현재가': '현재종가'}, inplace=True)
                        final_result = pd.merge(final_result, df_top[['종목명', '순위', '종목코드', '계좌수', '현재종가']], on='종목명', how='left')

                    # 4. 정렬 및 화면 출력
                    # 사장님 엑셀처럼 등장횟수 순으로 먼저 정렬
                    if '등장횟수' in final_result.columns:
                        final_result = final_result.sort_values('등장횟수', ascending=False)

                    st.subheader(f"✅ {e_str} 기준 FLOW 분석 결과값")
                    
                    # 필요한 컬럼만 추려서 사장님 엑셀 순서로 배치
                    cols = ['순위', '종목코드', '종목명', '등장횟수', '계좌수', '현재종가']
                    # 사장님 FLOW 엑셀에 있는 추가 컬럼(수급점수 등)도 있으면 포함
                    for c in ['수급점수', '외국인순매수수량', '기관순매수수량']:
                        if c in final_result.columns: cols.append(c)
                        
                    display_df = final_result[[c for c in cols if c in final_result.columns]]
                    st.dataframe(display_df.style.format(precision=0, na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")

import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO

# 1. 숫자 변환 보조 함수
def safe_to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        if s in ['', '-', 'nan', 'NaN']: return 0.0
        return float(s)
    except:
        return 0.0

# 2. 수급 점수 계산
def calc_flow_score(row):
    s = 0
    f_net = safe_to_num(row.get('외국인순값', 0))
    i_net = safe_to_num(row.get('기관순값', 0))
    if f_net > 0: s += 40
    if i_net > 0: s += 40
    if f_net > 0 and i_net > 0: s += 60
    return s

# --- 화면 설정 ---
st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 자동 분석 시스템")

# 🚩 [중요] 사장님 저장소 이름을 확인하고 싶어요! 
# 만약 여전히 안 된다면 저장소 이름을 'kiwoom-analysis'가 아닌 실제 이름으로 바꿔야 합니다.
USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis"  # <--- 이 부분이 실제 깃허브 저장소 이름과 똑같아야 합니다!

GITHUB_BASE_URL = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

@st.cache_data
def load_data_from_github(date_str):
    try:
        # 1. 메인 데이터 로드
        data_url = f"{GITHUB_BASE_URL}{date_str}.xlsx"
        resp_data = requests.get(data_url)
        if resp_data.status_code != 200: return None, None, None
        df_data = pd.read_excel(BytesIO(resp_data.content))
        
        # 2. 수급 데이터 로드
        flow_url = f"{GITHUB_BASE_URL}{date_str}_수급.xlsx"
        resp_flow = requests.get(flow_url)
        df_flow = pd.read_excel(BytesIO(resp_flow.content)) if resp_flow.status_code == 200 else pd.DataFrame()
        
        # 3. DIVA 데이터 로드 (파일명이 'DIVA.xlsx'라고 가정)
        diva_url = f"{GITHUB_BASE_URL}DIVA.xlsx"
        resp_diva = requests.get(diva_url)
        df_diva = pd.read_excel(BytesIO(resp_diva.content)) if resp_diva.status_code == 200 else pd.DataFrame()
        
        return df_data, df_flow, df_diva
    except:
        return None, None, None

st.sidebar.header("🗓️ 날짜 설정")
# 기본 날짜를 오늘 날짜인 2026-03-11로 바꿔두었습니다.
target_date = st.sidebar.text_input("분석 날짜 입력 (예: 2026-03-11)", value="2026-03-11")

if st.sidebar.button("데이터 불러오기"):
    df_data, df_flow, df_diva = load_data_from_github(target_date)
    
    if df_data is not None:
        result = df_data.copy()
        
        # DIVA 연동
        if not df_diva.empty:
            # 첫 번째 컬럼(보통 날짜) 기준으로 정렬 후 마지막 신호 추출
            diva_latest = df_diva.sort_values(by=df_diva.columns[0]).groupby('종목명').last().reset_index()
            result = pd.merge(result, diva_latest, on='종목명', how='left', suffixes=('', '_diva'))
        
        # 수급 점수
        if not df_flow.empty:
            df_flow['수급점수'] = df_flow.apply(calc_flow_score, axis=1)
            result = pd.merge(result, df_flow[['종목명', '수급점수']], on='종목명', how='left')
        
        result['현재가'] = result['현재가'].apply(safe_to_num)
        
        st.subheader(f"📊 {target_date} 분석 결과")
        
        def style_rows(row):
            # DIVA 시트 데이터가 연결되면 노란색 하이라이트
            is_diva = any(pd.notna(row.get(c)) for c in row.index if '신호' in str(c) or 'diva' in str(c))
            return ['background-color: #ffffcc' if is_diva else '' for _ in row]

        st.dataframe(result.style.apply(style_rows, axis=1).format({
            '현재가': '{:,.0f}', '수급점수': '{:.0f}'
        }, na_rep='-'), use_container_width=True)
    else:
        st.error(f"'{target_date}.xlsx'를 찾지 못했습니다. 깃허브 주소를 확인해주세요: {GITHUB_BASE_URL}{target_date}.xlsx")
else:
    st.info("날짜를 입력하고 버튼을 누르면 깃허브에서 데이터를 가져옵니다.")
    

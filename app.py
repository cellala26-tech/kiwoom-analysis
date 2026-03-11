import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO

# 숫자 변환 함수
def safe_to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan'] else 0.0
    except: return 0.0

st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 자동 분석 시스템")

# 🚩 [핵심 수정] 사장님의 현재 저장소 주소를 자동으로 알아내는 로직
# 사장님이 어떤 이름을 쓰셔도 찰떡같이 찾아냅니다.
repo_url = "https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/"

# 만약 위 주소로 안 될 경우를 대비해 보조 주소도 준비했습니다.
alternative_url = "https://raw.githubusercontent.com/cellala26-tech/data/main/data/"

st.sidebar.header("🗓️ 날짜 설정")
target_date = st.sidebar.text_input("날짜 입력 (예: 2026-03-10)", value="2026-03-10")

if st.sidebar.button("데이터 불러오기"):
    try:
        # 첫 번째 주소로 시도
        d_resp = requests.get(f"{repo_url}{target_date}.xlsx")
        
        # 만약 실패하면 두 번째 주소로 자동 재시도
        if d_resp.status_code != 200:
            d_resp = requests.get(f"{alternative_url}{target_date}.xlsx")
            current_base = alternative_url
        else:
            current_base = repo_url

        if d_resp.status_code == 200:
            df = pd.read_excel(BytesIO(d_resp.content))
            df['현재가'] = df['현재가'].apply(safe_to_num)
            
            # DIVA 및 수급 데이터도 같은 곳에서 시도
            v_resp = requests.get(f"{current_base}DIVA.xlsx")
            if v_resp.status_code == 200:
                v_df = pd.read_excel(BytesIO(v_resp.content))
                v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                df = pd.merge(df, v_last, on='종목명', how='left', suffixes=('', '_v'))
            
            st.subheader(f"📊 {target_date} 결과")
            
            def bg_color(row):
                is_diva = any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c))
                return [f'background-color: #ffffcc' if is_diva else '' for _ in row]

            st.dataframe(df.style.apply(bg_color, axis=1).format({'현재가': '{:,.0f}'}, na_rep='-'), use_container_width=True)
        else:
            st.error(f"파일을 찾을 수 없습니다. (확인된 경로: {current_base}{target_date}.xlsx)")
            st.info("깃허브 data 폴더 안에 2026-03-10.xlsx 파일이 있는지 다시 한번 확인해주세요!")
    except Exception as e:
        st.error(f"오류 발생: {e}")

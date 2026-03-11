import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO

def safe_to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan'] else 0.0
    except: return 0.0

st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 자동 분석 시스템")

# 🚩 [범인 검거 및 수정] 주소에서 중복된 /data/ 를 하나 제거했습니다.
USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

st.sidebar.header("🗓️ 날짜 설정")
target_date = st.sidebar.text_input("날짜 입력 (예: 2026-03-10)", value="2026-03-10")

if st.sidebar.button("데이터 불러오기"):
    try:
        # 1. 엑셀 데이터 가져오기
        file_url = f"{GITHUB_BASE}{target_date}.xlsx"
        resp = requests.get(file_url)
        
        if resp.status_code == 200:
            df = pd.read_excel(BytesIO(resp.content))
            df['현재가'] = df['현재가'].apply(safe_to_num)
            
            # 2. DIVA 매칭 (파일명이 'DIVA.xlsx'인 경우)
            v_resp = requests.get(f"{GITHUB_BASE}DIVA.xlsx")
            if v_resp.status_code == 200:
                v_df = pd.read_excel(BytesIO(v_resp.content))
                v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                df = pd.merge(df, v_last, on='종목명', how='left', suffixes=('', '_v'))
            
            st.subheader(f"📊 {target_date} 분석 결과")
            
            # 노란색 하이라이트 스타일
            def bg_color(row):
                is_diva = any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c))
                return [f'background-color: #ffffcc' if is_diva else '' for _ in row]

            st.dataframe(df.style.apply(bg_color, axis=1).format({'현재가': '{:,.0f}'}, na_rep='-'), use_container_width=True)
        else:
            # 실패 시 주소를 다시 보여주어 확인 사살
            st.error(f"파일을 찾을 수 없습니다.")
            st.info(f"확인된 경로: {file_url}")
            st.warning("혹시 깃허브 'data' 폴더 안에 파일이 들어있는 게 맞는지 다시 한번 확인해주세요!")
            
    except Exception as e:
        st.error(f"오류 발생: {e}")

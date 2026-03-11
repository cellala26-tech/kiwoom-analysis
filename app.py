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

# 사장님 저장소 주소 고정
BASE_URL = "https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/"

st.sidebar.header("🗓️ 날짜 설정")
target_date = st.sidebar.text_input("날짜 입력 (예: 2026-03-10)", value="2026-03-10")

if st.sidebar.button("데이터 불러오기"):
    try:
        # 데이터 가져오기 시도
        d_resp = requests.get(f"{BASE_URL}{target_date}.xlsx")
        f_resp = requests.get(f"{BASE_URL}{target_date}_수급.xlsx")
        v_resp = requests.get(f"{BASE_URL}DIVA.xlsx")

        if d_resp.status_code == 200:
            df = pd.read_excel(BytesIO(d_resp.content))
            df['현재가'] = df['현재가'].apply(safe_to_num)
            
            # DIVA 매칭
            if v_resp.status_code == 200:
                v_df = pd.read_excel(BytesIO(v_resp.content))
                v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                df = pd.merge(df, v_last, on='종목명', how='left', suffixes=('', '_v'))
            
            st.subheader(f"📊 {target_date} 결과")
            
            # 하이라이트 스타일
            def bg_color(row):
                # DIVA 데이터가 있으면 노란색 (VBA와 동일)
                color = '#ffffcc' if any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c)) else ''
                return [f'background-color: {color}' for _ in row]

            st.dataframe(df.style.apply(bg_color, axis=1).format({'현재가': '{:,.0f}'}, na_rep='-'), use_container_width=True)
        else:
            st.error(f"{target_date}.xlsx 파일을 찾지 못했습니다.")
    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")

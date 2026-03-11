import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO

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
st.title("🍜 미미국밥 주식 분석 시스템 (통합 Ver.)")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

st.sidebar.header("🗓️ 날짜 설정")
target_date = st.sidebar.text_input("날짜 입력 (예: 2026-03-10)", value="2026-03-10")

if st.sidebar.button("데이터 불러오기"):
    try:
        # 파일 요청
        d_res = requests.get(f"{GITHUB_BASE}{target_date}.xlsx")
        f_res = requests.get(f"{GITHUB_BASE}{target_date}_수급.xlsx")
        v_res = requests.get(f"{GITHUB_BASE}DIVA.xlsx")

        if d_res.status_code == 200:
            df = pd.read_excel(BytesIO(d_res.content))
            
            # 🚩 [보정] 종목명 컬럼이 없으면 찾아내기
            if '종목명' not in df.columns:
                # 첫 번째 줄이 비어있는 경우 대비
                df = pd.read_excel(BytesIO(d_res.content), skiprows=1)
            
            # 수급 데이터 통합
            if f_res.status_code == 200:
                f_df = pd.read_excel(BytesIO(f_res.content))
                # 수급 시트도 헤더 확인
                if '종목명' not in f_df.columns:
                    f_df = pd.read_excel(BytesIO(f_res.content), skiprows=1)
                
                if '종목명' in f_df.columns:
                    f_df['수급점수'] = f_df.apply(calc_flow_score, axis=1)
                    df = pd.merge(df, f_df[['종목명', '수급점수']], on='종목명', how='left')
            
            # DIVA 데이터 통합
            if v_res.status_code == 200:
                v_df = pd.read_excel(BytesIO(v_res.content))
                if '종목명' not in v_df.columns:
                    v_df = pd.read_excel(BytesIO(v_res.content), skiprows=1)
                
                if '종목명' in v_df.columns:
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    df = pd.merge(df, v_last, on='종목명', how='left', suffixes=('', '_v'))

            # 컬럼 정리
            df['현재가'] = df['현재가'].apply(safe_to_num)
            
            st.subheader(f"📊 {target_date} 분석 결과")
            
            # 스타일 함수
            def bg_color(row):
                # DIVA 연동 컬럼(보통 마지막 쪽에 생김)이 비어있지 않으면 노란색
                is_diva = any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c))
                return ['background-color: #ffffcc' if is_diva else '' for _ in row]

            st.dataframe(df.style.apply(bg_color, axis=1).format({'현재가': '{:,.0f}'}, na_rep='-'), use_container_width=True)
            
        else:
            st.error(f"{target_date}.xlsx 파일을 깃허브에서 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")
        st.info("팁: 엑셀 파일의 첫 번째 줄에 제목(종목명, 현재가 등)이 있는지 확인해주세요.")

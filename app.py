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

def calc_flow_score(row):
    s = 0
    f_net = safe_to_num(row.get('외국인순값', 0))
    i_net = safe_to_num(row.get('기관순값', 0))
    if f_net > 0: s += 40
    if i_net > 0: s += 40
    if f_net > 0 and i_net > 0: s += 60
    return s

st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 주식 분석기 (최종 진화형)")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

st.sidebar.header("🗓️ 날짜 설정")
target_date = st.sidebar.text_input("날짜 입력 (예: 2026-03-10)", value="2026-03-10")

if st.sidebar.button("데이터 불러오기"):
    try:
        # 1. 파일들 가져오기
        d_resp = requests.get(f"{GITHUB_BASE}{target_date}.xlsx")
        f_resp = requests.get(f"{GITHUB_BASE}{target_date}_수급.xlsx")
        v_resp = requests.get(f"{GITHUB_BASE}DIVA.xlsx")

        if d_resp.status_code == 200:
            df = pd.read_excel(BytesIO(d_resp.content))
            
            # 2. 수급 데이터가 있으면 점수 계산
            if f_resp.status_code == 200:
                f_df = pd.read_excel(BytesIO(f_resp.content))
                f_df['수급점수'] = f_df.apply(calc_flow_score, axis=1)
                df = pd.merge(df, f_df[['종목명', '수급점수']], on='종목명', how='left')
            
            # 3. DIVA 매칭
            if v_resp.status_code == 200:
                v_df = pd.read_excel(BytesIO(v_resp.content))
                v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                df = pd.merge(df, v_last[['종목명', '날짜', '종가']], on='종목명', how='left', suffixes=('', '_v'))

            # 데이터 정제 (불필요한 컬럼 제거)
            cols_to_keep = ['순위', '종목코드', '종목명', '현재가', '등락률', '거래량', '수급점수', '날짜_v', '종가_v']
            # 실제로 존재하는 컬럼만 선택
            existing_cols = [c for c in cols_to_keep if c in df.columns]
            final_df = df[existing_cols].copy()
            
            # 상승률 계산
            final_df['현재가'] = final_df['현재가'].apply(safe_to_num)
            if '종가_v' in final_df.columns:
                final_df['상승률(%)'] = np.where(final_df['종가_v'] > 0, 
                                            ((final_df['현재가'] - final_df['종가_v']) / final_df['종가_v'] * 100).round(2), 0.0)

            st.subheader(f"📊 {target_date} 분석 리포트")
            
            def bg_color(row):
                # DIVA 날짜(날짜_v)가 있으면 노란색 하이라이트
                color = '#ffffcc' if pd.notna(row.get('날짜_v')) else ''
                return [f'background-color: {color}' for _ in row]

            st.dataframe(final_df.style.apply(bg_color, axis=1).format({
                '현재가': '{:,.0f}', '종가_v': '{:,.0f}', '수급점수': '{:.0f}', '상승률(%)': '{:.2f}%'
            }, na_rep='-'), use_container_width=True)
            
        else:
            st.error(f"{target_date}.xlsx 파일을 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"오류 발생: {e}")

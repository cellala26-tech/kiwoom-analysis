import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta

# --- 1. VBA의 ToNum 함수 재현 (숫자 변환) ---
def to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan', 'NaN'] else 0.0
    except: return 0.0

# --- 2. VBA의 종목코드 포맷 재현 (000250 형태) ---
def format_code(v):
    if pd.isna(v) or v is None: return ""
    try: return str(int(to_num(v))).zfill(6)
    except: return str(v).strip()

# --- 3. 엑셀 제목 줄 자동 찾기 (VBA의 Range 찾기 로직) ---
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

# --- 4. VBA의 수급 점수 계산 로직 (40/40/60) ---
def calc_vba_score(row):
    f_val = to_num(row.get('외국인순매수수량', 0))
    i_val = to_num(row.get('기관순매수수량', 0))
    score = 0
    if f_val > 0: score += 40
    if i_val > 0: score += 40
    if f_val > 0 and i_val > 0: score += 60
    return score

st.set_page_config(layout="wide", page_title="키움 VBA 웹 이식 시스템")
st.title("🖥️ 키움 통합 분석 시스템 (VBA 엔진)")

# --- 사이드바 설정 (VBA UserForm 구성과 동일하게) ---
st.sidebar.header("📂 분석 설정")
start_date = st.sidebar.date_input("📅 시작일", value=datetime(2026, 3, 5))
end_date = st.sidebar.date_input("📅 종료일", value=datetime(2026, 3, 11))

analysis_type = st.sidebar.selectbox("📋 분석유형", [
    "내일 공략 TOP5", "신규진입 종목", "계좌수 급증", "매수수량 급증", "순매매수량 급증", "수급 분석"
])

run_btn = st.sidebar.button("🚀 분석 실행 (VBA 로직 가동)", use_container_width=True)

if run_btn:
    try:
        GITHUB_BASE = "https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/"
        e_str = end_date.strftime('%Y-%m-%d')
        date_list = pd.date_range(start_date, end_date).strftime('%Y-%m-%d').tolist()
        
        with st.spinner('VBA 로직으로 데이터를 정밀 분석 중...'):
            # [Step 1] 기간 내 모든 수급 파일 읽기 (등장횟수 계산용)
            flow_data_list = []
            for d in date_list:
                res = requests.get(f"{GITHUB_BASE}{d}_수급.xlsx")
                if res.status_code == 200:
                    df = get_clean_df(res.content, '종목명')
                    if not df.empty:
                        df['분석날짜'] = d
                        flow_data_list.append(df)
            
            if not flow_data_list:
                st.error("분석할 수급 데이터가 기간 내에 없습니다.")
            else:
                # [Step 2] VBA의 FLOW 집계 로직 재현
                all_flow = pd.concat(flow_data_list)
                counts = all_flow.groupby('종목명').size().reset_index(name='등장횟수')
                
                # 오늘(종료일) 데이터 추출
                today_df = all_flow[all_flow['분석날짜'] == e_str].copy()
                today_df['수급점수'] = today_df.apply(calc_vba_score, axis=1)
                
                # [Step 3] TOP200 파일과 매칭 (순위, 계좌수 등)
                res_top = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
                if res_top.status_code == 200:
                    top_df = get_clean_df(res_top.content, '종목명')
                    if '현재가' in top_df.columns: top_df.rename(columns={'현재가': '현재종가'}, inplace=True)
                    today_df = pd.merge(today_df, top_df[['종목명', '순위', '종목코드', '계좌수', '현재종가']], on='종목명', how='left')

                # [Step 4] DIVA 연동 (상승률 계산용)
                res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")
                if res_v.status_code == 200:
                    v_df = get_clean_df(res_v.content, '종목명')
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    v_last.rename(columns={'날짜': '디바신호일', '종가': '기준종가'}, inplace=True)
                    today_df = pd.merge(today_df, v_last[['종목명', '디바신호일', '기준종가']], on='종목명', how='left')

                # [Step 5] 최종 수치 계산 및 등장횟수 병합
                today_df = pd.merge(today_df, counts, on='종목명', how='left')
                today_df['연속등장'] = today_df['등장횟수'].apply(lambda x: f"{len(flow_data_list)} YES" if x >= len(flow_data_list) else "NO")
                today_df['상승률'] = np.where(today_df['기준종가'] > 0, 
                                           ((today_df['현재종가'].apply(to_num) - today_df['기준종가'].apply(to_num)) / today_df['기준종가'].apply(to_num) * 100).round(2), 0.0)

                # [Step 6] VBA의 정렬 로직 (등장횟수 -> 수급점수)
                final = today_df.sort_values(['등장횟수', '수급점수'], ascending=[False, False])
                
                # [Step 7] 화면 출력
                cols = ['순위', '종목코드', '종목명', '등장횟수', '연속등장', '계좌수', '현재종가', '상승률', '수급점수']
                display = final[[c for c in cols if c in final.columns]].head(5 if "TOP5" in analysis_type else 100)

                st.subheader(f"✅ {analysis_type} 분석 결과 (웹 실행 모드)")
                st.dataframe(display.style.apply(lambda row: ['background-color: #ffffcc' if pd.notna(row.get('디바신호일')) else '' for _ in row], axis=1).format(precision=0, na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")

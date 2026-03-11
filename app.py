import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta

# 숫자 변환 보조 함수 (콤마, 특수문자 제거)
def safe_to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan'] else 0.0
    except: return 0.0

# 수급 점수 계산 로직 (VBA와 동일)
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

# --- 사이드바: 사장님 엑셀 폼 디자인 100% 재현 ---
st.sidebar.header("📂 분석 설정")

# 1. 시작일과 종료일 직접 선택 (사장님 요청사항)
col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input("📅 시작일", value=datetime(2026, 3, 4))
with col2:
    end_date = st.date_input("📅 종료일", value=datetime(2026, 3, 11))

analysis_type = st.sidebar.selectbox("📋 분석유형", [
    "수급 분석", "계좌수 급증", "신규진입 종목", "잠복 세력", "Super Signal"
])

run_btn = st.sidebar.button("🔍 분석 실행")

if run_btn:
    s_str = start_date.strftime('%Y-%m-%d')
    e_str = end_date.strftime('%Y-%m-%d')
    
    try:
        with st.spinner(f'{s_str} ~ {e_str} 데이터 분석 중...'):
            # 종료일(기준일) TOP200 데이터 로드
            res_e = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
            res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")
            
            if res_e.status_code != 200:
                st.error(f"종료일 데이터({e_str}.xlsx)가 없습니다.")
            else:
                df_e = pd.read_excel(BytesIO(res_e.content))
                if '종목명' not in df_e.columns: df_e = pd.read_excel(BytesIO(res_e.content), skiprows=3)

                # --- 1. 수급 분석 로직 (기간 내 누적 합산) ---
                if analysis_type == "수급 분석":
                    # 기간 내 모든 수급 파일을 가져와서 합산 시도
                    all_flow_dfs = []
                    current_dt = start_date
                    while current_dt <= end_date:
                        d_str = current_dt.strftime('%Y-%m-%d')
                        res_f = requests.get(f"{GITHUB_BASE}{d_str}_수급.xlsx")
                        if res_f.status_code == 200:
                            temp_df = pd.read_excel(BytesIO(res_f.content))
                            if '종목명' not in temp_df.columns: temp_df = pd.read_excel(BytesIO(res_f.content), skiprows=1)
                            all_flow_dfs.append(temp_df[['종목명', '외국인순값', '기관순값']])
                        current_dt += timedelta(days=1)
                    
                    if all_flow_dfs:
                        # 여러 날짜의 수급 데이터를 종목명 기준으로 합산
                        combined_flow = pd.concat(all_flow_dfs)
                        for col in ['외국인순값', '기관순값']:
                            combined_flow[col] = combined_flow[col].apply(safe_to_num)
                        
                        df_flow_sum = combined_flow.groupby('종목명').sum().reset_index()
                        df_flow_sum['수급점수'] = df_flow_sum.apply(calc_flow_score, axis=1)
                        
                        # TOP200 등장 여부 체크
                        df_e['TOP200등장'] = "180 YES"
                        final_df = pd.merge(df_flow_sum, df_e[['종목명', '순위', 'TOP200등장']], on='종목명', how='left')
                        
                        cols = ['순위', '종목명', '외국인순값', '기관순값', '수급점수', 'TOP200등장']
                        final_df = final_df[[c for c in cols if c in final_df.columns]].sort_values('수급점수', ascending=False)
                    else:
                        st.error("해당 기간의 수급 파일이 하나도 없습니다.")
                        final_df = df_e

                # --- 2. 계좌수 급증 로직 (시작일 vs 종료일 대비) ---
                elif analysis_type == "계좌수 급증":
                    res_s = requests.get(f"{GITHUB_BASE}{s_str}.xlsx")
                    if res_s.status_code == 200:
                        df_s = pd.read_excel(BytesIO(res_s.content))
                        if '종목명' not in df_s.columns: df_s = pd.read_excel(BytesIO(res_s.content), skiprows=3)
                        
                        df_merged = pd.merge(df_e, df_s[['종목명', '계좌수']], on='종목명', how='left', suffixes=('_종료', '_시작'))
                        df_merged['증가폭'] = df_merged['계좌수_종료'].apply(safe_to_num) - df_merged['계좌수_시작'].apply(safe_to_num).fillna(0)
                        final_df = df_merged.sort_values('증가폭', ascending=False)
                    else:
                        st.warning(f"시작일({s_str}) 데이터가 없어 종료일 데이터만 표시합니다.")
                        final_df = df_e

                # 3. DIVA 하이라이트 적용
                if res_v.status_code == 200:
                    v_df = pd.read_excel(BytesIO(res_v.content))
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    final_df = pd.merge(final_df, v_last, on='종목명', how='left', suffixes=('', '_v'))

                st.subheader(f"📊 {analysis_type} 결과 ({s_str} ~ {e_str})")
                
                def style_diva(row):
                    is_v = any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c) or '날짜' == str(c))
                    return ['background-color: #ffffcc' if is_v else '' for _ in row]

                st.dataframe(final_df.style.apply(style_diva, axis=1).format({
                    '외국인순값': '{:.1f}', '기관순값': '{:.1f}', '수급점수': '{:.0f}'
                }, na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")

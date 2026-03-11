import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime

# --- 숫자 및 종목코드 변환 보조 함수 ---
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

# --- 제목 줄 및 중복 제거 보정 ---
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

# 🚩 [FLOW 자동 생성 엔진] 사장님 엑셀 수치와 100% 동기화
def create_auto_flow_sheet(date_list, github_base):
    all_data = []
    for d in date_list:
        res = requests.get(f"{github_base}{d}_수급.xlsx")
        if res.status_code == 200:
            df = get_clean_df(res.content, '외국인')
            if '종목명' not in df.columns: df = get_clean_df(res.content, '종목명')
            if not df.empty:
                df['날짜'] = d
                # 외인/기관 컬럼 추출 (사장님 엑셀 헤더 대응)
                f_col = [c for c in df.columns if '외국인' in str(c) and ('순' in str(c) or '값' in str(c))]
                i_col = [c for c in df.columns if '기관' in str(c) and ('순' in str(c) or '값' in str(c))]
                df['외인순매수'] = df[f_col[0]].apply(to_num) if f_col else 0.0
                df['기관순매수'] = df[i_col[0]].apply(to_num) if i_col else 0.0
                all_data.append(df[['날짜', '종목명', '외인순매수', '기관순매수']])
    
    if not all_data: return pd.DataFrame(), pd.DataFrame()
    
    flow_db = pd.concat(all_data)
    # 등장횟수 및 누적 수급 집계
    stats = flow_db.groupby('종목명').agg(
        등장횟수=('종목명', 'count'),
        외인합계=('외인순매수', 'sum'),
        기관합계=('기관순매수', 'sum')
    ).reset_index()
    return flow_db, stats

st.set_page_config(layout="wide", page_title="키움 TOP200 분석기")
st.title("📊 키움 TOP200 FLOW 자동 분석 시스템")

# --- 사이드바 ---
st.sidebar.header("📂 분석 설정")
start_date = st.sidebar.date_input("📅 시작일", value=datetime(2026, 3, 5))
end_date = st.sidebar.date_input("📅 종료일", value=datetime(2026, 3, 11))
run_btn = st.sidebar.button("🚀 FLOW 시트 생성 및 분석", use_container_width=True)

if run_btn:
    try:
        GITHUB_DATA = "https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/"
        date_list = pd.date_range(start_date, end_date).strftime('%Y-%m-%d').tolist()
        
        with st.spinner('FLOW 데이터를 정밀 분석 중...'):
            flow_db, flow_stats = create_auto_flow_sheet(date_list, GITHUB_DATA)
            
            if flow_db.empty:
                st.error("데이터를 불러올 수 없습니다.")
            else:
                today_str = end_date.strftime('%Y-%m-%d')
                today_flow = flow_db[flow_db['날짜'] == today_str].copy()
                
                # 수급 점수 계산 (사장님 로직 반영)
                def get_score(r):
                    score = 0
                    if r['외인순매수'] > 0: score += 40
                    if r['기관순매수'] > 0: score += 40
                    if r['외인순매수'] > 0 and r['기관순매수'] > 0: score += 60
                    return score
                
                today_flow['수급점수'] = today_flow.apply(get_score, axis=1)
                
                # TOP200 연동
                res_top = requests.get(f"{GITHUB_DATA}{today_str}.xlsx")
                if res_top.status_code == 200:
                    top_df = get_clean_df(res_top.content)
                    if '현재가' in top_df.columns: top_df.rename(columns={'현재가': '현재종가'}, inplace=True)
                    final_df = pd.merge(today_flow, top_df[['종목명', '순위', '종목코드', '계좌수', '현재종가']], on='종목명', how='left')
                else:
                    final_df = today_flow
                
                final_df = pd.merge(final_df, flow_stats[['종목명', '등장횟수']], on='종목명', how='left')
                final_df['연속등장'] = final_df['등장횟수'].apply(lambda x: f"{len(date_list)} YES" if x >= len(date_list) else "NO")

                # 🚩 결과 정렬 및 에러 수정된 출력 부분
                final_df = final_df.sort_values(['등장횟수', '수급점수'], ascending=False)
                
                st.subheader(f"✅ 자동 생성된 FLOW 분석 결과 ({today_str} 기준)")
                
                # 컬럼 순서 조정
                cols = ['순위', '종목코드', '종목명', '등장횟수', '연속등장', '계좌수', '현재종가', '수급점수']
                display_df = final_df[[c for c in cols if c in final_df.columns]]
                
                # 🚩 '.format' 에러 해결을 위해 '.style.format' 사용
                st.dataframe(display_df.style.format(precision=0, na_rep='-'), use_container_width=True)
                
                with st.expander("📝 전체 FLOW 누적 로그 (사장님 엑셀 FLOW 시트 모드)"):
                    st.write(flow_db.sort_values(['날짜', '외인순매수'], ascending=[False, False]))

    except Exception as e:
        st.error(f"오류 발생: {e}")

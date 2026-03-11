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

# 🚩 [핵심 기능] 사장님의 FLOW 시트를 자동으로 만드는 함수
def create_auto_flow_sheet(date_list, github_base):
    all_data = []
    for d in date_list:
        res = requests.get(f"{github_base}{d}_수급.xlsx")
        if res.status_code == 200:
            df = get_clean_df(res.content, '외국인')
            if '종목명' not in df.columns: df = get_clean_df(res.content, '종목명')
            if not df.empty:
                df['날짜'] = d
                # 외인/기관 컬럼 추출
                f_col = [c for c in df.columns if '외국인' in str(c) and ('순' in str(c) or '값' in str(c))]
                i_col = [c for c in df.columns if '기관' in str(c) and ('순' in str(c) or '값' in str(c))]
                df['외인순매수'] = df[f_col[0]].apply(to_num) if f_col else 0.0
                df['기관순매수'] = df[i_col[0]].apply(to_num) if i_col else 0.0
                all_data.append(df[['날짜', '종목명', '외인순매수', '기관순매수']])
    
    if not all_data: return pd.DataFrame()
    
    # 1. 모든 날짜 데이터 합치기 (FLOW 시트 기본 데이터)
    flow_db = pd.concat(all_data)
    
    # 2. 종목별 집계 (등장횟수, 수급점수 합계 등)
    stats = flow_db.groupby('종목명').agg(
        등장횟수=('종목명', 'count'),
        외인합계=('외인순매수', 'sum'),
        기관합계=('기관순매수', 'sum')
    ).reset_index()
    
    # 3. 수급 점수 계산 (사장님 로직: 외인>0(+40), 기관>0(+40), 양매수(+60))
    # 여기서는 '전체 기간 합계'가 아닌 '최종일(오늘)' 기준 수급 점수를 보여주는 것이 정확하므로 종료일 데이터를 다시 씁니다.
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
        
        with st.spinner('수급 엑셀들을 읽어 FLOW 데이터를 자동 정렬 중...'):
            # 1. FLOW 시트 자동 생성
            flow_db, flow_stats = create_auto_flow_sheet(date_list, GITHUB_DATA)
            
            if flow_db.empty:
                st.error("데이터를 불러올 수 없습니다.")
            else:
                # 2. 종료일(오늘) 수급 데이터와 매칭
                today_str = end_date.strftime('%Y-%m-%d')
                today_flow = flow_db[flow_db['날짜'] == today_str].copy()
                
                # 수급 점수 계산 (오늘 기준)
                today_flow['수급점수'] = today_flow.apply(lambda r: (40 if r['외인순매수']>0 else 0) + (40 if r['기관순매수']>0 else 0) + (60 if r['외인순매수']>0 and r['기관순매수']>0 else 0), axis=1)
                
                # 3. TOP200 및 부가 정보 병합
                res_top = requests.get(f"{GITHUB_DATA}{today_str}.xlsx")
                if res_top.status_code == 200:
                    top_df = get_clean_df(res_top.content)
                    final_df = pd.merge(today_flow, top_df[['종목명', '순위', '종목코드', '계좌수', '현재가']], on='종목명', how='left')
                else:
                    final_df = today_flow
                
                # 통계 데이터(등장횟수 등) 합치기
                final_df = pd.merge(final_df, flow_stats[['종목명', '등장횟수']], on='종목명', how='left')
                final_df['연속등장'] = final_df['등장횟수'].apply(lambda x: f"{len(date_list)} YES" if x >= len(date_list) else "NO")

                # 4. 정렬 (등장횟수 -> 수급점수 내림차순)
                final_df = final_df.sort_values(['등장횟수', '수급점수'], ascending=False)

                # 결과 출력
                st.subheader(f"✅ 자동 생성된 FLOW 분석 결과 ({today_str} 기준)")
                st.dataframe(final_df[['순위', '종목코드', '종목명', '등장횟수', '연속등장', '계좌수', '현재가', '수급점수']].format(precision=0, na_rep='-'), use_container_width=True)
                
                # 하단에 전체 FLOW 로그 표시 (사장님 엑셀 시트처럼)
                with st.expander("📝 전체 FLOW 누적 로그 보기"):
                    st.write(flow_db.sort_values(['날짜', '외인순매수'], ascending=[False, False]))

    except Exception as e:
        st.error(f"오류 발생: {e}")

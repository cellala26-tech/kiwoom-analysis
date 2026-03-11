import streamlit as st
import pandas as pd
import numpy as np
import os
import re

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

# 🚩 경로 수정 부분: 서버 환경에서도 절대 경로로 인식하게 함
DATA_DIR = os.path.join(os.getcwd(), "data")

@st.cache_data
def load_all_data():
    data_list = []
    flow_list = []
    diva_df = pd.DataFrame()

    # 폴더가 없으면 생성 시도 (에러 방지)
    if not os.path.exists(DATA_DIR):
        return None, None, None

    files = os.listdir(DATA_DIR)
    for fname in files:
        fpath = os.path.join(DATA_DIR, fname)
        if not fname.endswith('.xlsx'): continue

        try:
            if 'DIVA' in fname.upper():
                diva_df = pd.read_excel(fpath)
            elif '수급' in fname:
                temp = pd.read_excel(fpath)
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
                if date_match: temp['날짜'] = date_match.group()
                flow_list.append(temp)
            else:
                temp = pd.read_excel(fpath)
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
                if date_match: temp['날짜'] = date_match.group()
                data_list.append(temp)
        except:
            continue

    full_data = pd.concat(data_list, ignore_index=True) if data_list else pd.DataFrame()
    full_flow = pd.concat(flow_list, ignore_index=True) if flow_list else pd.DataFrame()
    
    return full_data, full_flow, diva_df

# 데이터 로딩
df_all_data, df_all_flow, df_diva = load_all_data()

if df_all_data is not None and not df_all_data.empty:
    # 날짜 선택
    all_dates = sorted(df_all_data['날짜'].unique(), reverse=True)
    target_date = st.sidebar.selectbox("📅 분석 날짜 선택", all_dates)
    
    # 분석 로직
    current_data = df_all_data[df_all_data['날짜'] == target_date].copy()
    
    # DIVA 연동
    if not df_diva.empty:
        diva_latest = df_diva.sort_values(by=df_diva.columns[0]).groupby('종목명').last().reset_index()
        result = pd.merge(current_data, diva_latest, on='종목명', how='left', suffixes=('', '_diva'))
    else:
        result = current_data
        result['디바신호일'] = np.nan

    # 수급점수 합산
    if not df_all_flow.empty:
        flow_day = df_all_flow[df_all_flow['날짜'] == target_date].copy()
        if not flow_day.empty:
            flow_day['수급점수'] = flow_day.apply(calc_flow_score, axis=1)
            result = pd.merge(result, flow_day[['종목명', '수급점수']], on='종목명', how='left')

    # 상승률 및 포맷팅
    result['현재가'] = result['현재가'].apply(safe_to_num)
    
    # 화면 출력
    st.subheader(f"📊 {target_date} 분석 결과")
    
    def style_rows(row):
        # DIVA 시트에서 넘어온 신호가 있는지 확인 (컬럼명은 엑셀에 따라 다를 수 있음)
        is_diva = any(pd.notna(row.get(c)) for c in row.index if '신호' in str(c) or '날짜_diva' in str(c))
        return ['background-color: #ffffcc' if is_diva else '' for _ in row]

    st.dataframe(result.style.apply(style_rows, axis=1).format({
        '현재가': '{:,.0f}', '수급점수': '{:.0f}'
    }, na_rep='-'), use_container_width=True)

    # 종목 이력 검색
    st.divider()
    search_stock = st.text_input("🔎 종목 이력 검색")
    if search_stock:
        history = df_all_data[df_all_data['종목명'].str.contains(search_stock.upper(), na=False)].sort_values('날짜')
        if not history.empty:
            st.line_chart(history.set_index('날짜')['현재가'])
else:
    st.warning("data 폴더 내의 파일을 불러올 수 없습니다. 파일명에 날짜(2026-03-06)가 포함되어 있는지 확인해주세요.")

import streamlit as st
import pandas as pd
import numpy as np
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

# 2. 수급 점수 계산 함수
def calc_flow_score(row):
    s = 0
    f_net = safe_to_num(row.get('외국인순값', 0))
    i_net = safe_to_num(row.get('기관순값', 0))
    if f_net > 0: s += 40
    if i_net > 0: s += 40
    if f_net > 0 and i_net > 0: s += 60
    return s

# --- 웹 화면 설정 ---
st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 통합 분석 시스템 (DIVA 연동)")

st.sidebar.header("📂 데이터 일괄 업로드")
st.sidebar.info("키움 파일, 수급 파일, 그리고 [DIVA 파일]을 함께 올려주세요.")

uploaded_files = st.sidebar.file_uploader(
    "엑셀 파일들을 선택하세요 (여러 개 가능)", 
    type=['xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    data_list = []
    flow_list = []
    diva_df = pd.DataFrame()

    with st.spinner('모든 데이터를 통합 중...'):
        for file in uploaded_files:
            fname = file.name
            # DIVA 파일 인식
            if 'DIVA' in fname.upper():
                diva_df = pd.read_excel(file)
            # 수급 파일 인식
            elif '수급' in fname:
                temp_df = pd.read_excel(file)
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
                if date_match: temp_df['날짜'] = date_match.group()
                flow_list.append(temp_df)
            # 일반 키움 데이터 인식
            else:
                temp_df = pd.read_excel(file)
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
                if date_match: temp_df['날짜'] = date_match.group()
                data_list.append(temp_df)

    if data_list:
        all_data = pd.concat(data_list, ignore_index=True)
        all_flow = pd.concat(flow_list, ignore_index=True) if flow_list else pd.DataFrame()
        
        all_dates = sorted(all_data['날짜'].unique(), reverse=True)
        target_date = st.sidebar.selectbox("분석 기준일 선택", all_dates)
        
        current_data = all_data[all_data['날짜'] == target_date].copy()
        
        # --- DIVA 연동 로직 ---
        if not diva_df.empty:
            # 종목별 가장 최근 DIVA 신호 추출
            diva_latest = diva_df.sort_values(by='날짜').groupby('종목명').last().reset_index()
            # 데이터 병합
            result = pd.merge(current_data, diva_latest[['종목명', '날짜', '종가']], on='종목명', how='left')
            result.rename(columns={'날짜_y': '디바신호일', '종가': '기준종가', '날짜_x': '날짜'}, inplace=True)
        else:
            result = current_data
            result['디바신호일'] = np.nan
            result['기준종가'] = 0

        # 수급 점수 합산
        if not all_flow.empty:
            flow_day = all_flow[all_flow['날짜'] == target_date].copy()
            if not flow_day.empty:
                flow_day['수급점수'] = flow_day.apply(calc_flow_score, axis=1)
                result = pd.merge(result, flow_day[['종목명', '수급점수']], on='종목명', how='left')

        # 상승률 계산 (기준종가 대비 현재가)
        result['현재가'] = result['현재가'].apply(safe_to_num)
        result['기준종가'] = result['기준종가'].apply(safe_to_num)
        result['상승률(%)'] = np.where(result['기준종가'] > 0, 
                                   ((result['현재가'] - result['기준종가']) / result['기준종가'] * 100).round(2), 0)

        # 표 출력 및 하이라이트
        st.subheader(f"📊 {target_date} 분석 결과 (DIVA 신호 포함)")
        
        def style_rows(row):
            # DIVA 신호가 있으면 노란색
            return ['background-color: #ffffcc' if pd.notna(row['디바신호일']) else '' for _ in row]

        st.dataframe(result.style.apply(style_rows, axis=1).format({
            '현재가': '{:,.0f}', '기준종가': '{:,.0f}', '상승률(%)': '{:.2f}%'
        }, na_rep='-'), use_container_width=True)

    else:
        st.warning("파일을 인식하지 못했습니다. 파일명에 날짜(2026-03-06 등)가 있는지 확인해주세요.")
else:
    st.info("사이드바에서 [키움 데이터, 수급 파일, DIVA 파일]을 한꺼번에 마우스로 끌어다 넣어주세요!")

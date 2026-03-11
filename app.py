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
    f_qty = safe_to_num(row.get('외국인수량순값', 0))
    i_qty = safe_to_num(row.get('기관수량순값', 0))
    if f_net > 0: s += 40
    if i_net > 0: s += 40
    if f_net > 0 and i_net > 0: s += 60
    if f_qty > 0: s += 20
    if i_qty > 0: s += 20
    return s

# --- 웹 화면 설정 ---
st.set_page_config(layout="wide", page_title="미미국밥 주식 분석기")
st.title("🍜 미미국밥 통합 주식 분석기")

# 사이드바 설정
st.sidebar.header("📂 데이터 일괄 업로드")
uploaded_files = st.sidebar.file_uploader(
    "엑셀 파일들을 선택하세요", 
    type=['xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    data_list = []
    flow_list = []
    diva_df = pd.DataFrame()

    with st.spinner('파일을 읽어오는 중...'):
        for file in uploaded_files:
            fname = file.name
            # 1. DIVA 파일 처리
            if 'DIVA' in fname.upper():
                diva_df = pd.read_excel(file)
            # 2. 수급 파일 처리 (파일명에 '수급' 포함)
            elif '수급' in fname:
                temp_df = pd.read_excel(file)
                # 헤더가 3행부터 있을 경우를 대비해 컬럼 재설정
                if '종목명' not in temp_df.columns:
                    temp_df = pd.read_excel(file, skiprows=1) # 한 줄 건너뛰고 다시 읽기
                
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
                if date_match: temp_df['날짜'] = date_match.group()
                flow_list.append(temp_df)
            # 3. 일반 키움 TOP200 파일
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
        
        # DIVA 매칭
        if not diva_df.empty:
            diva_latest = diva_df.sort_values(by=diva_df.columns[0]).groupby('종목명').last().reset_index()
            result = pd.merge(current_data, diva_latest, on='종목명', how='left')
        else:
            result = current_data

        # 수급점수 계산 및 안전한 병합
        if not all_flow.empty:
            flow_day = all_flow[all_flow['날짜'] == target_date].copy()
            if not flow_day.empty:
                # 수급 점수 계산
                flow_day['수급점수'] = flow_day.apply(calc_flow_score, axis=1)
                
                # '종목코드' 컬럼이 없을 경우 첫 번째 컬럼을 코드로 간주
                code_col = '종목코드' if '종목코드' in flow_day.columns else flow_day.columns[0]
                
                # 병합
                result = pd.merge(result, flow_day[[code_col, '수급점수']], 
                                  left_on='종목코드', right_on=code_col, how='left')

        # 상승률 계산
        result['현재가'] = result['현재가'].apply(safe_to_num)
        result['상승률(%)'] = 0.0 # 기본값
        
        # 결과 출력
        st.subheader(f"📊 {target_date} 분석 결과")
        st.dataframe(result, use_container_width=True)

        st.divider()
        search_q = st.text_input("🔎 종목 검색")
        if search_q:
            history = all_data[all_data['종목명'].str.contains(search_q.upper(), na=False)]
            if not history.empty:
                st.line_chart(history.set_index('날짜')['현재가'])
    else:
        st.warning("파일을 인식하지 못했습니다. 파일명을 확인해주세요.")
else:
    st.info("왼쪽에서 파일을 선택해 주세요.")

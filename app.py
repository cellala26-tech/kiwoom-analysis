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
st.title("🍜 미미국밥 통합 주식 분석기 (다중 파일 지원)")

# 사이드바 설정
st.sidebar.header("📂 데이터 일괄 업로드")
st.sidebar.info("키움TOP200 파일과 수급 파일을 한꺼번에 선택해서 올려주세요.")

uploaded_files = st.sidebar.file_uploader(
    "여러 개의 엑셀 파일을 선택하세요", 
    type=['xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    data_list = []
    flow_list = []
    diva_df = pd.DataFrame()

    with st.spinner('파일들을 통합 분석 중입니다...'):
        for file in uploaded_files:
            fname = file.name
            # DIVA 파일 처리
            if 'DIVA' in fname.upper():
                diva_df = pd.read_excel(file)
            # 수급 파일 처리
            elif '수급' in fname:
                temp_df = pd.read_excel(file)
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
                if date_match: temp_df['날짜'] = date_match.group()
                flow_list.append(temp_df)
            # 일반 키움 TOP200 파일
            else:
                temp_df = pd.read_excel(file)
                date_match = re.search(r'\d{4}-\d{2}-\d{2}', fname)
                if date_match: temp_df['날짜'] = date_match.group()
                data_list.append(temp_df)

    # 데이터 통합 및 분석
    if data_list:
        all_data = pd.concat(data_list, ignore_index=True)
        all_flow = pd.concat(flow_list, ignore_index=True) if flow_list else pd.DataFrame()
        
        all_dates = sorted(all_data['날짜'].unique(), reverse=True)
        target_date = st.sidebar.selectbox("분석 기준일 선택", all_dates)
        
        current_data = all_data[all_data['날짜'] == target_date].copy()
        
        # DIVA 신호 매칭
        if not diva_df.empty:
            diva_latest = diva_df.sort_values(by='날짜').groupby('종목명').last().reset_index()
            result = pd.merge(current_data, diva_latest[['종목명', '날짜', '종가']], on='종목명', how='left')
            result.rename(columns={'날짜_y': '디바신호일', '종가': '기준종가', '날짜_x': '날짜'}, inplace=True)
        else:
            result = current_data
            result['디바신호일'] = np.nan
            result['기준종가'] = 0

        # 수급점수 병합
        if not all_flow.empty:
            flow_day = all_flow[all_flow['날짜'] == target_date].copy()
            if not flow_day.empty:
                flow_day['수급점수'] = flow_day.apply(calc_flow_score, axis=1)
                result = pd.merge(result, flow_day[['종목코드', '수급점수']], on='종목코드', how='left')

        result['현재가'] = result['현재가'].apply(safe_to_num)
        result['상승률(%)'] = np.where(result.get('기준종가', 0) > 0, 
                                   ((result['현재가'] - result['기준종가']) / result['기준종가'] * 100).round(2), 0)

        st.subheader(f"📊 {target_date} 통합 분석 결과")
        
        def highlight_diva(row):
            return ['background-color: #ffffcc' if pd.notna(row.get('디바신호일')) else '' for _ in row]

        st.dataframe(result.style.apply(highlight_diva, axis=1).format({
            '현재가': '{:,.0f}', '기준종가': '{:,.0f}', '상승률(%)': '{:.2f}%', '수급점수': '{:.0f}'
        }, na_rep='-'), use_container_width=True)

        st.divider()
        search_q = st.text_input("🔎 종목명/코드로 과거 이력 전체 검색")
        if search_q:
            history = all_data[all_data['종목명'].str.contains(search_q.upper(), na=False)].sort_values('날짜')
            if not history.empty:
                st.line_chart(history.set_index('날짜')['현재가'])
                st.write(f"최초 등장: {history['날짜'].min()} | 누적 등장 횟수: {len(history)}회")
    else:
        st.warning("파일을 업로드하면 분석이 시작됩니다.")
else:
    st.info("사이드바에서 분석할 파일들을 선택해 주세요 (키움 파일 + 수급 파일)")

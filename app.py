import streamlit as st
import pandas as pd
import numpy as np

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
st.title("🍜 미미국밥 주식 분석 시스템")

st.sidebar.header("📂 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("엑셀 파일을 업로드하세요", type=['xlsx'])

if uploaded_file:
    try:
        # 데이터 읽기
        df_data = pd.read_excel(uploaded_file, sheet_name='DATA')
        df_diva = pd.read_excel(uploaded_file, sheet_name='DIVA')
        
        # 날짜 선택
        all_dates = sorted(df_data['날짜'].unique(), reverse=True)
        target_date = st.sidebar.selectbox("분석 기준일 선택", all_dates)
        
        # 데이터 처리
        day_data = df_data[df_data['날짜'] == target_date].copy()
        
        # DIVA 신호 매칭 (VBA 모듈 3 로직)
        diva_summary = df_diva.sort_values(by='날짜').groupby('종목명').last().reset_index()
        result = pd.merge(day_data, diva_summary[['종목명', '날짜', '종가']], on='종목명', how='left')
        result.rename(columns={'날짜_y': '디바신호일', '종가': '기준종가', '날짜_x': '날짜'}, inplace=True)
        
        # 수급점수 처리 (FLOW 시트가 있는 경우)
        try:
            df_flow = pd.read_excel(uploaded_file, sheet_name='FLOW')
            flow_day = df_flow[df_flow['날짜'] == target_date].copy()
            if not flow_day.empty:
                flow_day['수급점수'] = flow_day.apply(calc_flow_score, axis=1)
                result = pd.merge(result, flow_day[['종목코드', '수급점수']], on='종목코드', how='left')
        except:
            pass

        # 결과 가공
        result['현재가'] = result['현재가'].apply(safe_to_num)
        result['기준종가'] = result['기준종가'].apply(safe_to_num)
        result['상승률(%)'] = np.where(result['기준종가'] > 0, 
                                   ((result['현재가'] - result['기준종가']) / result['기준종가'] * 100).round(2), 0)

        # 테이블 출력 (하이라이트)
        st.subheader(f"📊 {target_date} 분석 결과")
        
        def highlight_diva(row):
            return ['background-color: #ffffcc' if pd.notna(row['디바신호일']) else '' for _ in row]

        st.dataframe(result.style.apply(highlight_diva, axis=1).format({
            '현재가': '{:,.0f}', '기준종가': '{:,.0f}', '상승률(%)': '{:.2f}%'
        }), use_container_width=True)

        # 종목 검색 (SearchHistory)
        st.divider()
        search_q = st.text_input("🔎 종목명 이력 검색 (ex: 삼성전자)")
        if search_q:
            history = df_data[df_data['종목명'].str.contains(search_q.upper(), na=False)].sort_values('날짜')
            if not history.empty:
                st.line_chart(history.set_index('날짜')['현재가'])
                st.write(f"최초 진입: {history['날짜'].min()} | 누적 등장: {len(history)}회")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
else:
    st.info("왼쪽 사이드바에서 엑셀 파일을 업로드해주세요.")

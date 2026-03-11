import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta

# --- 숫자 및 종목코드 변환 보조 함수 ---
def to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan', 'NaN'] else 0.0
    except: return 0.0

def format_code(v):
    if pd.isna(v) or v is None: return ""
    try:
        return str(int(to_num(v))).zfill(6)
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

# --- 수급 점수 계산 로직 ---
def calc_flow_data(row):
    try:
        f_cols = [c for c in row.index if '외국인' in str(c) and ('순' in str(c) or '값' in str(c))]
        i_cols = [c for c in row.index if '기관' in str(c) and ('순' in str(c) or '값' in str(c))]
        f_val = to_num(row[f_cols[0]]) if f_cols else 0.0
        i_val = to_num(row[i_cols[0]]) if i_cols else 0.0
        score = 0
        if f_val > 0: score += 40
        if i_val > 0: score += 40
        if f_val > 0 and i_val > 0: score += 60
        return f_val, i_val, score
    except: return 0.0, 0.0, 0.0

st.set_page_config(layout="wide", page_title="키움 TOP200 분석기")
st.title("📊 키움 TOP200 통합 분석 시스템")

# --- 사이드바 설정 ---
st.sidebar.header("📂 분석 설정")
col_date1, col_date2 = st.sidebar.columns(2)
with col_date1:
    start_date = st.date_input("📅 시작일", value=datetime(2026, 3, 5))
with col_date2:
    end_date = st.date_input("📅 종료일", value=datetime(2026, 3, 11))

analysis_type = st.sidebar.selectbox("📋 분석유형", ["내일 공략 top5", "계좌수 급증", "수급분석"])
run_btn = st.sidebar.button("🚀 분석 실행", use_container_width=True)

if run_btn:
    try:
        e_str = end_date.strftime('%Y-%m-%d')
        date_list = pd.date_range(start_date, end_date).strftime('%Y-%m-%d').tolist()
        
        with st.spinner('엑셀 데이터 정밀 분석 중...'):
            # 1. 수급(FLOW) 파일 로드
            res_f_end = requests.get(f"https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/{e_str}_수급.xlsx")
            if res_f_end.status_code != 200:
                st.error(f"종료일 수급 데이터({e_str}_수급.xlsx)가 없습니다.")
            else:
                flow_df = get_clean_df(res_f_end.content, '외국인')
                if '종목명' not in flow_df.columns: flow_df = get_clean_df(res_f_end.content, '종목명')
                
                # 수급 점수 계산
                flow_res = flow_df.apply(calc_flow_data, axis=1, result_type='expand')
                flow_df['외국인순값'], flow_df['기관순값'], flow_df['수급점수'] = flow_res[0], flow_res[1], flow_res[2]

                # 2. 등장횟수 및 연속등장 전수 조사
                all_flow_names = []
                for d in date_list:
                    rf = requests.get(f"https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/{d}_수급.xlsx")
                    if rf.status_code == 200:
                        tdf = get_clean_df(rf.content, '종목명')
                        if not tdf.empty: all_flow_names.append(set(tdf['종목명'].unique()))

                def get_stats(name):
                    count = sum(1 for s in all_flow_names if name in s)
                    continuous = f"{len(all_flow_names)} YES" if count == len(all_flow_names) else "NO"
                    return count, continuous

                stats = flow_df['종목명'].apply(lambda x: pd.Series(get_stats(x)))
                flow_df['등장횟수'], flow_df['연속등장'] = stats[0], stats[1]

                # 3. TOP200 및 계좌수 대조 (이름 보정 포함)
                res_top_e = requests.get(f"https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/{e_str}.xlsx")
                if res_top_e.status_code == 200:
                    top_df = get_clean_df(res_top_e.content, '종목명')
                    # 🚩 현재종가 에러 방지를 위한 컬럼명 표준화
                    if '현재가' in top_df.columns: top_df = top_df.rename(columns={'현재가': '현재종가'})
                    if '종가' in top_df.columns: top_df = top_df.rename(columns={'종가': '기준종가'})
                    
                    flow_df = pd.merge(flow_df, top_df[['종목명', '순위', '종목코드', '계좌수', '현재종가']], on='종목명', how='left')

                # 4. 계좌수 증가 계산
                s_str = start_date.strftime('%Y-%m-%d')
                res_top_s = requests.get(f"https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/{s_str}.xlsx")
                if res_top_s.status_code == 200:
                    start_df = get_clean_df(res_top_s.content, '종목명')
                    flow_df = pd.merge(flow_df, start_df[['종목명', '계좌수']], on='종목명', how='left', suffixes=('', '_시작'))
                    flow_df['계좌수 증가'] = flow_df['계좌수'].apply(to_num) - flow_df['계좌수_시작'].apply(to_num).fillna(0)

                # 5. DIVA 및 상승률
                res_v = requests.get("https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/DIVA.xlsx")
                if res_v.status_code == 200:
                    v_df = get_clean_df(res_v.content, '종목명')
                    if not v_df.empty:
                        v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                        # 🚩 디바신호일 날짜 컬럼명 표준화
                        if '날짜' in v_last.columns: v_last = v_last.rename(columns={'날짜': '디바신호일'})
                        if '종가' in v_last.columns: v_last = v_last.rename(columns={'종가': '기준종가'})
                        flow_df = pd.merge(flow_df, v_last, on='종목명', how='left', suffixes=('', '_v'))

                # 상승률 계산 (안전한 수치 변환)
                flow_df['기준종가'] = flow_df['기준종가'].apply(to_num)
                flow_df['현재종가'] = flow_df['현재종가'].apply(to_num)
                flow_df['상승률'] = np.where(flow_df['기준종가'] > 0, 
                                          ((flow_df['현재종가'] - flow_df['기준종가']) / flow_df['기준종가'] * 100).round(2), 0.0)

                # 🚩 최종 결과 정렬 및 출력
                final = flow_df.sort_values(['등장횟수', '수급점수'], ascending=False)
                cols = ['순위', '종목코드', '종목명', '등장횟수', '연속등장', '계좌수 증가', '디바신호일', '기준종가', '현재종가', '상승률', '수급점수']
                display = final[[c for c in cols if c in final.columns]].head(5 if analysis_type == "내일 공략 top5" else 100)

                st.subheader(f"✅ {analysis_type} 분석 리포트")
                # 노란색 하이라이트 스타일 적용
                st.dataframe(display.style.apply(lambda row: ['background-color: #ffffcc' if pd.notna(row.get('디바신호일')) else '' for _ in row], axis=1).format({
                    '현재종가': '{:,.0f}', '기준종가': '{:,.0f}', '계좌수 증가': '{:,.0f}', '상승률': '{:.2f}%', '수급점수': '{:,.0f}'
                }, na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")

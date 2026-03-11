import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta

# --- 숫자 변환 보조 함수 ---
def to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        if s in ['', '-', 'nan', 'NaN']: return 0.0
        return float(s)
    except: return 0.0

# --- 🚩 중복 제목 및 제목 찾기 보정 함수 (에러 방지 핵심) ---
def get_clean_df(content, target_keyword='종목명'):
    for i in range(15):
        try:
            temp_df = pd.read_excel(BytesIO(content), skiprows=i)
            # 컬럼명 중에 키워드가 포함되어 있는지 확인
            matches = [col for col in temp_df.columns if target_keyword in str(col)]
            if matches:
                # 🚩 중복된 제목이 있을 경우 첫 번째 것만 유지하고 나머지는 제거
                temp_df = temp_df.loc[:, ~temp_df.columns.duplicated()]
                # 키워드가 포함된 컬럼명을 표준화 (예: ' 종목명.1' -> '종목명')
                new_cols = {matches[0]: target_keyword}
                return temp_df.rename(columns=new_cols)
        except: continue
    return pd.DataFrame()

# --- 수급 데이터 추출 로직 ---
def get_flow_data(row):
    f_cols = [c for c in row.index if '외국인' in str(c) and ('순' in str(c) or '값' in str(c))]
    i_cols = [c for c in row.index if '기관' in str(c) and ('순' in str(c) or '값' in str(c))]
    f_val = to_num(row[f_cols[0]]) if f_cols else 0.0
    i_val = to_num(row[i_cols[0]]) if i_cols else 0.0
    
    score = 0
    if f_val > 0: score += 40
    if i_val > 0: score += 40
    if f_val > 0 and i_val > 0: score += 60
    return f_val, i_val, score

st.set_page_config(layout="wide", page_title="키움 TOP200 분석기")
st.title("📊 키움 TOP200 통합 분석 시스템")

# --- 사이드바 설정 ---
st.sidebar.header("📂 분석 설정")
col_date1, col_date2 = st.sidebar.columns(2)
with col_date1:
    if 's_date' not in st.session_state: st.session_state.s_date = datetime(2026, 3, 5)
    start_date = st.date_input("📅 시작일", value=st.session_state.s_date)
with col_date2:
    end_date = st.date_input("📅 종료일", value=datetime(2026, 3, 11))

st.sidebar.write("⏱️ 기간 퀵 설정")
c1, c2, c3 = st.sidebar.columns(3)
with c1:
    if st.button("5일"): st.session_state.s_date = end_date - timedelta(days=4)
with c2:
    if st.button("10일"): st.session_state.s_date = end_date - timedelta(days=9)
with c3:
    if st.button("20일"): st.session_state.s_date = end_date - timedelta(days=19)

analysis_type = st.sidebar.selectbox("📋 분석유형", ["내일 공략 top5", "계좌수 급증", "수급분석", "신규진입종목"])
run_btn = st.sidebar.button("🚀 분석 실행", use_container_width=True)

if run_btn:
    try:
        e_str = end_date.strftime('%Y-%m-%d')
        date_list = pd.date_range(start_date, end_date).strftime('%Y-%m-%d').tolist()
        
        with st.spinner('데이터 전수 조사 및 분석 중...'):
            all_dfs = {}
            for d in date_list:
                res = requests.get(f"https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/{d}.xlsx")
                if res.status_code == 200:
                    clean_df = get_clean_df(res.content)
                    if not clean_df.empty: all_dfs[d] = clean_df

            if e_str not in all_dfs:
                st.error(f"종료일({e_str}) 또는 기간 내 유효한 데이터가 없습니다.")
            else:
                main_df = all_dfs[e_str].copy()
                
                # 1. 수급 데이터 연동
                res_f = requests.get(f"https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/{e_str}_수급.xlsx")
                if res_f.status_code == 200:
                    df_f = get_clean_df(res_f.content, target_keyword='외국인')
                    if '종목명' not in df_f.columns: df_f = get_clean_df(res_f.content, target_keyword='종목명')
                    
                    if '종목명' in df_f.columns:
                        # 🚩 수급 파일도 제목 중복 제거 적용
                        df_f = df_f.loc[:, ~df_f.columns.duplicated()]
                        flow_res = df_f.apply(get_flow_data, axis=1, result_type='expand')
                        df_f['외국인순값'], df_f['기관순값'], df_f['수급점수'] = flow_res[0], flow_res[1], flow_res[2]
                        main_df = pd.merge(main_df, df_f[['종목명', '외국인순값', '기관순값', '수급점수']], on='종목명', how='left')

                # 2. 등장횟수 / 연속등장 / 계좌증가 계산
                valid_dfs = [df[['종목명']] for df in all_dfs.values() if '종목명' in df.columns]
                if valid_dfs:
                    counts = pd.concat(valid_dfs).groupby('종목명').size().to_dict()
                    main_df['등장횟수'] = main_df['종목명'].map(counts)
                
                con_dict = {}
                for name in main_df['종목명'].unique():
                    status = f"{len(all_dfs)} YES"
                    for d in reversed(date_list):
                        if d in all_dfs and name not in all_dfs[d]['종목명'].values:
                            status = "NO"; break
                    con_dict[name] = status
                main_df['연속등장'] = main_df['종목명'].map(con_dict)

                s_str = start_date.strftime('%Y-%m-%d')
                if s_str in all_dfs:
                    main_df = pd.merge(main_df, all_dfs[s_str][['종목명', '계좌수']], on='종목명', how='left', suffixes=('', '_시작'))
                    main_df['계좌수 증가'] = main_df['계좌수'].apply(to_num) - main_df['계좌수_시작'].apply(to_num).fillna(0)

                # 3. DIVA 연동 및 상승률
                res_v = requests.get("https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/DIVA.xlsx")
                if res_v.status_code == 200:
                    v_df = get_clean_df(res_v.content)
                    if not v_df.empty:
                        v_df = v_df.loc[:, ~v_df.columns.duplicated()]
                        v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                        main_df = pd.merge(main_df, v_last, on='종목명', how='left', suffixes=('', '_v'))

                main_df.rename(columns={'날짜': '디바신호일', '종가': '기준종가', '현재가': '현재종가'}, inplace=True)
                
                # 결과 컬럼 구성
                cols = ['순위', '종목코드', '종목명', '등장횟수', '연속등장', '계좌수 증가', '디바신호일', '기준종가', '현재종가', '수급점수']
                result_display = main_df[[c for c in cols if c in main_df.columns]].copy()
                
                if analysis_type == "내일 공략 top5":
                    result_display = result_display.sort_values(['등장횟수', '연속등장', '수급점수'], ascending=False).head(5)

                st.subheader(f"✅ {analysis_type} 분석 리포트")
                st.dataframe(result_display.style.apply(lambda row: ['background-color: #ffffcc' if pd.notna(row.get('디바신호일')) else '' for _ in row], axis=1).format(precision=0, na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")

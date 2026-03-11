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

# --- 사이드바 설정 (사장님 VBA UserForm 구성 재현) ---
st.sidebar.header("📂 분석 설정")
col_date1, col_date2 = st.sidebar.columns(2)
with col_date1:
    start_date = st.date_input("📅 시작일", value=datetime(2026, 3, 5))
with col_date2:
    end_date = st.date_input("📅 종료일", value=datetime(2026, 3, 11))

# 🚩 분석유형 리스트 완벽 복구
analysis_type = st.sidebar.selectbox("📋 분석유형", [
    "내일 공략 TOP5", 
    "신규진입 종목", 
    "계좌수 급증", 
    "매수수량 급증", 
    "순매매수량 급증", 
    "잠복 세력", 
    "Super Signal", 
    "수급 분석"
])

run_btn = st.sidebar.button("🚀 분석 실행", use_container_width=True)

if run_btn:
    try:
        e_str = end_date.strftime('%Y-%m-%d')
        s_str = start_date.strftime('%Y-%m-%d')
        date_list = pd.date_range(start_date, end_date).strftime('%Y-%m-%d').tolist()
        
        with st.spinner(f'{analysis_type} 데이터 정밀 분석 중...'):
            # 1. 기간 내 모든 TOP200 파일 로드
            period_dfs = {}
            for d in date_list:
                res = requests.get(f"https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/{d}.xlsx")
                if res.status_code == 200:
                    df = get_clean_df(res.content)
                    if not df.empty: period_dfs[d] = df

            if e_str not in period_dfs:
                st.error(f"종료일({e_str}) 데이터가 없습니다.")
            else:
                main_df = period_dfs[e_str].copy()
                
                # 2. 분석 타겟 컬럼 자동 결정
                target_col = '계좌수'
                if "매수수량" in analysis_type: target_col = '매수수량'
                elif "순매매수량" in analysis_type: target_col = '순매매수량'

                # 3. 등장횟수 및 연속등장 계산 (TOP200 기준)
                counts = pd.concat([df[['종목명']] for df in period_dfs.values()]).groupby('종목명').size().to_dict()
                main_df['등장횟수'] = main_df['종목명'].map(counts)
                
                con_dict = {}
                for name in main_df['종목명'].unique():
                    status = f"{len(period_dfs)} YES"
                    for d in reversed(date_list):
                        if d in period_dfs and name not in period_dfs[d]['종목명'].values:
                            status = "NO"; break
                    con_dict[name] = status
                main_df['연속등장'] = main_df['종목명'].map(con_dict)

                # 4. 수급 점수 (종료일 기준)
                res_f = requests.get(f"https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/{e_str}_수급.xlsx")
                if res_f.status_code == 200:
                    df_f = get_clean_df(res_f.content, '외국인')
                    if '종목명' not in df_f.columns: df_f = get_clean_df(res_f.content, '종목명')
                    flow_res = df_f.apply(calc_flow_data, axis=1, result_type='expand')
                    df_f['수급점수'] = flow_res[2]
                    main_df = pd.merge(main_df, df_f[['종목명', '수급점수']], on='종목명', how='left')

                # 5. 증가폭 계산 (시작일 대비)
                if s_str in period_dfs:
                    main_df = pd.merge(main_df, period_dfs[s_str][['종목명', target_col]], on='종목명', how='left', suffixes=('', '_시작'))
                    main_df['증가폭'] = main_df[target_col].apply(to_num) - main_df[f'{target_col}_시작'].apply(to_num).fillna(0)

                # 6. DIVA 및 상승률
                res_v = requests.get("https://raw.githubusercontent.com/cellala26-tech/kiwoom-analysis/main/data/DIVA.xlsx")
                if res_v.status_code == 200:
                    v_df = get_clean_df(res_v.content)
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    if '날짜' in v_last.columns: v_last = v_last.rename(columns={'날짜': '디바신호일'})
                    if '종가' in v_last.columns: v_last = v_last.rename(columns={'종가': '기준종가'})
                    main_df = pd.merge(main_df, v_last, on='종목명', how='left', suffixes=('', '_v'))

                if '현재가' in main_df.columns: main_df = main_df.rename(columns={'현재가': '현재종가'})
                main_df['상승률'] = np.where(main_df['기준종가'] > 0, 
                                          ((main_df['현재종가'].apply(to_num) - main_df['기준종가'].apply(to_num)) / main_df['기준종가'].apply(to_num) * 100).round(2), 0.0)

                # 7. 분석 유형별 정렬 및 필터링
                final = main_df.copy()
                if analysis_type == "내일 공략 TOP5":
                    final = final.sort_values(['등장횟수', '연속등장', '수급점수'], ascending=False).head(5)
                elif "급증" in analysis_type:
                    final = final.sort_values('증가폭', ascending=False)
                elif analysis_type == "신규진입 종목":
                    final = final[final[f'{target_col}_시작'].isna()]
                elif analysis_type == "Super Signal":
                    final = final[(final['등장횟수'] >= 3) & (final['수급점수'] >= 100)].sort_values('수급점수', ascending=False)

                cols = ['순위', '종목코드', '종목명', '등장횟수', '연속등장', '증가폭', '디바신호일', '기준종가', '현재종가', '상승률', '수급점수']
                display = final[[c for c in cols if c in final.columns]]

                st.subheader(f"✅ {analysis_type} 분석 리포트")
                st.dataframe(display.style.apply(lambda row: ['background-color: #ffffcc' if pd.notna(row.get('디바신호일')) else '' for _ in row], axis=1).format(precision=0, na_rep='-'), use_container_width=True)

    except Exception as e:
        st.error(f"오류 발생: {e}")

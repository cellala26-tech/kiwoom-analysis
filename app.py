import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime, timedelta

# --- VBA의 ToNum 함수 완벽 재현 ---
def to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '')
        s = s.replace('↑', '').replace('↓', '').replace(' ', '').strip()
        if s in ['', '-', 'nan', 'NaN']: return 0.0
        return float(s)
    except:
        return 0.0

# --- VBA의 CalcFlowScoreFromRow 로직 ---
def calc_flow_score(row):
    s = 0
    # 외국인/기관 순값 컬럼 찾기 (VBA의 컬럼 위치 기반 로직 반영)
    f_val = to_num(row.get('외국인순값', 0))
    i_val = to_num(row.get('기관순값', 0))
    if f_val > 0: s += 40
    if i_val > 0: s += 40
    if f_val > 0 and i_val > 0: s += 60
    return s

st.set_page_config(layout="wide", page_title="미미국밥 통합 분석 시스템")
st.title("🍜 미미국밥 주식 분석 시스템 (VBA 엔진 v1.0)")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

# --- 사이드바: VBA UserForm 인터페이스 그대로 ---
st.sidebar.header("📂 분석 설정 (UserForm)")
end_date = st.sidebar.date_input("📅 종료일 (cmbEndDate)", value=datetime(2026, 3, 11))

# cmbPeriod 구현
period_val = st.sidebar.selectbox("⏱️ 최근기간 (cmbPeriod)", ["최근5일", "최근10일", "최근20일"], index=1)
period_days = int(period_val.replace("최근", "").replace("일", ""))

# cmbAnalysisType 목록 (VBA와 100% 일치)
analysis_type = st.sidebar.selectbox("📋 분석유형 (cmbAnalysisType)", [
    "신규진입 종목", "계좌수 급증", "매수수량 급증", "순매매수량 급증", 
    "잠복 세력", "Super Signal", "내일 공략 TOP5", "수급 분석", "디바 일치 종목"
])

# 시작일 자동 계산 (VBA Initialize 로직)
start_date = st.sidebar.date_input("📅 시작일 (cmbStartDate)", value=end_date - timedelta(days=period_days))

run_btn = st.sidebar.button("🚀 분석 실행 (cmdRun_Click)", use_container_width=True)

# --- 분석 실행 (VBA cmdRun_Click 로직) ---
if run_btn:
    try:
        e_str = end_date.strftime('%Y-%m-%d')
        s_str = start_date.strftime('%Y-%m-%d')
        date_range = pd.date_range(start_date, end_date).strftime('%Y-%m-%d').tolist()

        with st.spinner('VBA 엔진 가동 중...'):
            # 데이터 로드 (VBA의 DATA 시트 역할)
            res_e = requests.get(f"{GITHUB_BASE}{e_str}.xlsx")
            res_s = requests.get(f"{GITHUB_BASE}{s_str}.xlsx")
            res_v = requests.get(f"{GITHUB_BASE}DIVA.xlsx")

            if res_e.status_code != 200:
                st.error(f"종료일 데이터({e_str})가 없습니다.")
            else:
                # 엑셀 읽기 보정 (VBA의 skiprows 로직 반영)
                df_e = pd.read_excel(BytesIO(res_e.content))
                if '종목명' not in df_e.columns: df_e = pd.read_excel(BytesIO(res_e.content), skiprows=3)
                
                # --- Select Case analysisType 구현 ---
                if analysis_type == "계좌수 급증":
                    if res_s.status_code == 200:
                        df_s = pd.read_excel(BytesIO(res_s.content))
                        if '종목명' not in df_s.columns: df_s = pd.read_excel(BytesIO(res_s.content), skiprows=3)
                        
                        merged = pd.merge(df_e, df_s[['종목명', '계좌수']], on='종목명', how='left', suffixes=('_종료', '_시작'))
                        merged['증가폭'] = merged['계좌수_종료'].apply(to_num) - merged['계좌수_시작'].apply(to_num).fillna(0)
                        final_df = merged[merged['증가폭'] > 0].sort_values('증가폭', ascending=False)
                        cols = ['순위', '종목코드', '종목명', '계좌수_시작', '계좌수_종료', '증가폭']
                    else:
                        st.error("시작일 데이터가 없습니다.")
                        final_df = pd.DataFrame()

                elif analysis_type == "잠복 세력":
                    # VBA 로직: accDiff * 1 + (netDiff / 1000) + positiveDays * 50
                    # 이 기능은 기간 내 전수 조사가 필요하므로 루프 가동
                    all_data = []
                    for d in date_range:
                        r = requests.get(f"{GITHUB_BASE}{d}.xlsx")
                        if r.status_code == 200:
                            tdf = pd.read_excel(BytesIO(r.content))
                            if '종목명' not in tdf.columns: tdf = pd.read_excel(BytesIO(r.content), skiprows=3)
                            tdf['날짜'] = d
                            all_data.append(tdf)
                    
                    if all_data:
                        full_df = pd.concat(all_data)
                        res_list = []
                        for name, group in full_df.groupby('종목명'):
                            if len(group) >= (period_days // 2): # 어느 정도 포착된 종목
                                acc_diff = to_num(group.iloc[-1]['계좌수']) - to_num(group.iloc[0]['계좌수'])
                                net_diff = to_num(group.iloc[-1]['순매매수량']) - to_num(group.iloc[0]['순매매수량'])
                                pos_days = len(group[group['순매매수량'].apply(to_num) > 0])
                                score = acc_diff + (net_diff / 1000) + (pos_days * 50)
                                if acc_diff > 0:
                                    res_list.append({'종목명': name, '계좌수 증가': acc_diff, '순매매 증가': net_diff, '양수일수': pos_days, '점수': score})
                        final_df = pd.DataFrame(res_list).sort_values('점수', ascending=False)
                        cols = ['종목명', '계좌수 증가', '순매매 증가', '양수일수', '점수']

                elif analysis_type == "수급 분석":
                    res_f = requests.get(f"{GITHUB_BASE}{e_str}_수급.xlsx")
                    if res_f.status_code == 200:
                        df_f = pd.read_excel(BytesIO(res_f.content))
                        if '종목명' not in df_f.columns: df_f = pd.read_excel(BytesIO(res_f.content), skiprows=1)
                        df_f['수급점수'] = df_f.apply(calc_flow_score, axis=1)
                        final_df = df_f.sort_values('수급점수', ascending=False)
                        cols = ['순위', '종목코드', '종목명', '외국인순값', '기관순값', '수급점수']
                    else:
                        st.error("수급 파일이 없습니다.")
                        final_df = pd.DataFrame()

                # --- 공통 DIVA 연동 및 하이라이트 (VBA HighlightDivaByName) ---
                if res_v.status_code == 200:
                    v_df = pd.read_excel(BytesIO(res_v.content))
                    v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                    final_df = pd.merge(final_df, v_last, on='종목명', how='left', suffixes=('', '_v'))

                # --- 결과 출력 (VBA WriteSortedResult 포맷) ---
                st.subheader(f"📊 {analysis_type} 결과 리포트")
                
                # VBA의 5개/10개 제한 로직 반영
                limit = 5 if analysis_type == "내일 공략 TOP5" else 100 
                display_df = final_df.head(limit)

                def style_vba(row):
                    # DIVA 신호가 있으면 엑셀처럼 노란색 하이라이트
                    is_diva = any(pd.notna(row.get(c)) for c in row.index if '_v' in str(c) or '날짜' == str(c))
                    return ['background-color: #ffffcc' if is_diva else '' for _ in row]

                st.dataframe(display_df.style.apply(style_vba, axis=1).format(precision=0, na_rep='-'), use_container_width=True)
                st.success("✅ VBA 엔진 분석 완료")

    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")

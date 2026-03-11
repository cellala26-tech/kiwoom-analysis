import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import BytesIO
from datetime import datetime

# 숫자 변환 함수
def safe_to_num(v):
    if pd.isna(v) or v is None: return 0.0
    try:
        s = str(v).replace(',', '').replace('%', '').replace('▲', '').replace('▼', '').strip()
        return float(s) if s not in ['', '-', 'nan'] else 0.0
    except: return 0.0

st.set_page_config(layout="wide", page_title="미미국밥 통합 분석 시스템")
st.title("🍜 미미국밥 주식 분석기 (신규진입/유지 분석)")

USER_ID = "cellala26-tech"
REPO_NAME = "kiwoom-analysis" 
GITHUB_BASE = f"https://raw.githubusercontent.com/{USER_ID}/{REPO_NAME}/main/data/"

# 1. 파일 목록 (사장님이 data 폴더에 넣은 파일명들 - 실제 날짜 관리가 필요합니다)
# 웹에서는 폴더를 뒤지기 어려우니 사장님이 분석할 기간을 직접 입력하면 해당 파일들을 긁어옵니다.
st.sidebar.header("⚙️ 분석 설정")
start_date = st.sidebar.date_input("시작일", value=datetime(2026, 3, 6))
end_date = st.sidebar.date_input("종료일", value=datetime(2026, 3, 11))
analysis_type = st.sidebar.selectbox("분석유형", ["신규진입 종목", "전체 유지 분석"])

if st.sidebar.button("분석 실행"):
    try:
        # 설정된 기간 내의 날짜 리스트 생성
        date_range = pd.date_range(start_date, end_date).strftime('%Y-%m-%d').tolist()
        
        all_dfs = {}
        with st.spinner('데이터를 불러오고 분석 중입니다...'):
            for d in date_range:
                res = requests.get(f"{GITHUB_BASE}{d}.xlsx")
                if res.status_code == 200:
                    temp_df = pd.read_excel(BytesIO(res.content))
                    # 제목줄이 4행인 경우 처리
                    if '종목명' not in temp_df.columns:
                        temp_df = pd.read_excel(BytesIO(res.content), skiprows=3)
                    all_dfs[d] = temp_df

        if not all_dfs:
            st.error("해당 기간의 데이터를 찾을 수 없습니다.")
        else:
            # --- VBA 로직 구현 ---
            last_date = date_range[-1]
            if last_date not in all_dfs:
                last_date = list(all_dfs.keys())[-1]
                
            current_df = all_dfs[last_date].copy()
            
            # 분석용 결과 데이터프레임 생성
            results = []
            for _, row in current_df.iterrows():
                name = row['종목명']
                
                # 진입날짜 및 유지일수 계산
                entry_date = last_date
                stay_days = 0
                first_acc_count = row.get('계좌수', 0)
                
                # 거꾸로 거슬러 올라가며 진입일 찾기
                for d in reversed(date_range):
                    if d in all_dfs and name in all_dfs[d]['종목명'].values:
                        entry_date = d
                        stay_days += 1
                        first_acc_count = all_dfs[d][all_dfs[d]['종목명'] == name]['계좌수'].values[0]
                    elif d < last_date: # 중간에 끊기면 그게 진입일
                        break
                
                # 신규진입 필터링 (시작일 이후에 처음 나타난 종목)
                is_new = entry_date > date_range[0]
                
                if analysis_type == "신규진입 종목" and not is_new:
                    continue
                
                results.append({
                    '순위': row.get('순위', 0),
                    '종목코드': row.get('종목코드', ''),
                    '종목명': name,
                    '진입날짜': entry_date,
                    '유지일수': stay_days,
                    '최초계좌수': first_acc_count,
                    '현재종가': safe_to_num(row.get('현재가', 0))
                })

            res_df = pd.DataFrame(results)

            # DIVA 시트 연동 (디바신호일, 기준종가 등)
            v_res = requests.get(f"{GITHUB_BASE}DIVA.xlsx")
            if v_res.status_code == 200:
                v_df = pd.read_excel(BytesIO(v_res.content))
                v_last = v_df.sort_values(by=v_df.columns[0]).groupby('종목명').last().reset_index()
                res_df = pd.merge(res_df, v_last, on='종목명', how='left', suffixes=('', '_v'))

            # 최종 출력
            st.subheader(f"✅ 분석 결과: {analysis_type}")
            st.info(f"비교기간: {start_date} → {end_date} ({len(all_dfs)}일치 데이터 확인)")
            
            def bg_color(row):
                # DIVA 날짜가 있으면 노란색 하이라이트 (엑셀 화면과 동일)
                color = '#ffffcc' if pd.notna(row.get('날짜')) else ''
                return [f'background-color: {color}' for _ in row]

            st.dataframe(res_df.style.apply(bg_color, axis=1).format({
                '현재종가': '{:,.0f}', '기준종가': '{:,.0f}', '상승률': '{:.2f}%'
            }, na_rep=''), use_container_width=True)

    except Exception as e:
        st.error(f"분석 중 오류 발생: {e}")

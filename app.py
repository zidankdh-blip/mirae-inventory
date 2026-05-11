import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from pyzbar.pyzbar import decode
from PIL import Image

# 1. 화면 설정 및 제목
st.set_page_config(page_title="미래약국 재고관리", layout="wide")
st.title("💊 미래약국 스마트 재고관리 (통합본)")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        inv = conn.read(worksheet="재고현황", ttl="0")
        log = conn.read(worksheet="기록장", ttl="0")
        
        # [해결 1] 바코드 소수점(.0) 제거 및 문자열 강제 변환
        for df in [inv, log]:
            if not df.empty and '바코드' in df.columns:
                df['바코드'] = df['바코드'].astype(str).str.replace(r'\.0$', '', regex=True)
                df['바코드'] = df['바코드'].replace('nan', '')
        return inv, log
    except:
        st.error("⚠️ 구글 시트 연동 실패! 시트 이름(재고현황, 기록장)을 확인해주세요.")
        return pd.DataFrame(), pd.DataFrame()

inventory_df, log_df = load_data()

# [해결 2] 검색창 초기화를 위한 세션 상태 관리
if 'search_box' not in st.session_state:
    st.session_state.search_box = ""

def clear_search():
    st.session_state.search_box = ""

# 3개의 탭 구성
tab1, tab2, tab3 = st.tabs(["🚀 입출고/스캔", "📜 입출고 기록장", "⚙️ 데이터 관리"])

with tab1:
    with st.expander("📸 카메라 바코드 스캔"):
        img_file = st.camera_input("바코드를 찍어주세요")
        if img_file:
            img = Image.open(img_file)
            decoded = decode(img)
            if decoded:
                barcode = decoded[0].data.decode('utf-8')
                st.session_state.search_box = barcode
                st.rerun()
            else:
                st.warning("바코드를 인식하지 못했습니다.")

    # 검색창 (작업 완료 후 자동으로 비워짐)
    search_query = st.text_input("바코드 또는 제품명 입력", 
                                 key="search_input_box",
                                 value=st.session_state.search_box,
                                 placeholder="여기에 입력하거나 위 카메라를 쓰세요")

    if search_query:
        if st.button("❌ 검색어 지우기"):
            clear_search()
            st.rerun()

        match = inventory_df[
            (inventory_df['바코드'].astype(str) == search_query) | 
            (inventory_df['제품명'].astype(str).str.contains(search_query, na=False))
        ]
        
        if not match.empty:
            idx = match.index[0]
            row = match.iloc[0]
            st.info(f"📦 **{row['제품명']}** | 현재: **{row['현재수량']}**개")
            
            c1, c2 = st.columns(2)
            qty = c1.number_input("수량", min_value=1, value=1)
            user = c2.text_input("담당자", value="약사")
            
            b1, b2 = st.columns(2)
            if b1.button("🟢 입고 (+)", use_container_width=True):
                new_q = row['현재수량'] + qty
                inventory_df.at[idx, '현재수량'] = new_q
                # 로그 추가
                new_log = pd.DataFrame([{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "바코드": search_query, "제품명": row['제품명'], "작업": "입고(+)", "수량": qty, "잔여재고": new_q, "담당자": user}])
                conn.update(worksheet="재고현황", data=inventory_df)
                conn.update(worksheet="기록장", data=pd.concat([log_df, new_log], ignore_index=True))
                st.success("입고 완료!")
                clear_search() # [해결 3] 검색창 비우기
                st.rerun()
                
            if b2.button("🔴 출고 (-)", use_container_width=True):
                if row['현재수량'] < qty:
                    st.error("재고가 부족합니다!")
                else:
                    new_q = row['현재수량'] - qty
                    inventory_df.at[idx, '현재수량'] = new_q
                    new_log = pd.DataFrame([{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "바코드": search_query, "제품명": row['제품명'], "작업": "출고(-)", "수량": qty, "잔여재고": new_q, "담당자": user}])
                    conn.update(worksheet="재고현황", data=inventory_df)
                    conn.update(worksheet="기록장", data=pd.concat([log_df, new_log], ignore_index=True))
                    st.success("출고 완료!")
                    clear_search()
                    st.rerun()
        else:
            st.warning("신규 등록이 필요합니다.")
            with st.form("new_item"):
                n_name = st.text_input("새 제품명", value=search_query)
                n_qty = st.number_input("초기 수량", min_value=0)
                if st.form_submit_button("신규 등록"):
                    new_row = pd.DataFrame([{"바코드": search_query, "제품명": n_name, "현재수량": n_qty}])
                    conn.update(worksheet="재고현황", data=pd.concat([inventory_df, new_row], ignore_index=True))
                    st.success("등록 완료!")
                    clear_search()
                    st.rerun()

    st.divider()
    st.subheader("📊 실시간 재고 현황 (5개 미만 빨간색)")
    if not inventory_df.empty:
        def alert(r): return ['color:red; font-weight:bold' if r['현재수량'] < 5 else '' for _ in r]
        st.dataframe(inventory_df.style.apply(alert, axis=1), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("📑 최근 기록 (최신순)")
    if not log_df.empty:
        st.dataframe(log_df.iloc[::-1], use_container_width=True, hide_index=True)

with tab3:
    st.subheader("⚙️ 데이터 삭제 관리")
    # [해결 4] 삭제 시 연동 오류 방지를 위한 정밀 로직
    col_del1, col_del2 = st.columns(2)
    
    with col_del1:
        st.write("🗑️ 제품 삭제")
        if not inventory_df.empty:
            target_inv = st.selectbox("삭제할 제품", inventory_df['제품명'].tolist())
            if st.button("제품 완전 삭제"):
                updated_inv = inventory_df[inventory_df['제품명'] != target_inv].reset_index(drop=True)
                conn.update(worksheet="재고현황", data=updated_inv)
                st.success("제품 삭제 완료")
                st.rerun()

    with col_del2:
        st.write("🗑️ 기록 삭제")
        if not log_df.empty:
            log_idx = st.number_input("삭제할 기록 번호(Index)", min_value=0, max_value=len(log_df)-1)
            if st.button("기록 삭제"):
                updated_log = log_df.drop(index=log_idx).reset_index(drop=True)
                conn.update(worksheet="기록장", data=updated_log)
                st.success("기록 삭제 완료")
                st.rerun()
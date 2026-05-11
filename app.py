import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# 1. 화면 설정
st.set_page_config(page_title="미래약국 재고관리", layout="wide")
st.title("💊 미래약국 스마트 재고관리 (안정화 버전)")

conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 데이터 불러오기 (⭐ 과부하 방지 로직 적용)
# ttl="2"는 2초 동안은 구글 시트에 다시 묻지 않고 이전 데이터를 쓴다는 뜻입니다.
def load_data():
    try:
        inv = conn.read(worksheet="재고현황", ttl="2")
        log = conn.read(worksheet="기록장", ttl="2")
        del_log = conn.read(worksheet="삭제기록", ttl="2")
        
        for df in [inv, log, del_log]:
            if not df.empty and '바코드' in df.columns:
                df['바코드'] = df['바코드'].astype(str).str.replace(r'\.0$', '', regex=True)
                df['바코드'] = df['바코드'].replace('nan', '')
        return inv, log, del_log
    except Exception as e:
        # 과부하 에러일 경우 잠시 대기 안내
        if "429" in str(e):
            st.warning("🔄 구글 서버가 바쁩니다. 3초 뒤에 자동으로 다시 시도합니다...")
            time.sleep(3)
            st.rerun()
        else:
            st.error(f"⚠️ 에러 발생: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

inventory_df, log_df, delete_df = load_data()

if 'input_key' not in st.session_state:
    st.session_state.input_key = 0

tab1, tab2, tab3 = st.tabs(["🚀 입출고/스캔", "📜 입출고 내역", "⚙️ 데이터 관리(휴지통)"])

with tab1:
    search_query = st.text_input(
        "바코드 스캔 또는 제품명 입력 (엔터)", 
        key=f"search_box_{st.session_state.input_key}",
        placeholder="스캐너로 찍거나 이름을 입력하세요"
    )

    if search_query:
        if '바코드' not in inventory_df.columns or '제품명' not in inventory_df.columns:
            st.error("⚠️ 장부 제목을 확인해주세요.")
        else:
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
                
                # --- 입고 처리 ---
                if b1.button("🟢 입고 (+)", use_container_width=True):
                    with st.spinner("장부 업데이트 중..."):
                        new_q = row['현재수량'] + qty
                        inventory_df.at[idx, '현재수량'] = new_q
                        new_log = pd.DataFrame([{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "바코드": row['바코드'], "제품명": row['제품명'], "작업": "입고(+)", "수량": qty, "잔여재고": new_q, "담당자": user}])
                        conn.update(worksheet="재고현황", data=inventory_df)
                        conn.update(worksheet="기록장", data=pd.concat([log_df, new_log], ignore_index=True))
                        
                        st.session_state.input_key += 1 
                        st.success("✅ 입고 완료!")
                        time.sleep(0.5) # 구글 서버가 쉴 틈을 줍니다.
                        st.rerun()
                    
                # --- 출고 처리 ---
                if b2.button("🔴 출고 (-)", use_container_width=True):
                    if row['현재수량'] < qty:
                        st.error("재고가 부족합니다!")
                    else:
                        with st.spinner("장부 업데이트 중..."):
                            new_q = row['현재수량'] - qty
                            inventory_df.at[idx, '현재수량'] = new_q
                            new_log = pd.DataFrame([{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "바코드": row['바코드'], "제품명": row['제품명'], "작업": "출고(-)", "수량": qty, "잔여재고": new_q, "담당자": user}])
                            conn.update(worksheet="재고현황", data=inventory_df)
                            conn.update(worksheet="기록장", data=pd.concat([log_df, new_log], ignore_index=True))
                            
                            st.session_state.input_key += 1 
                            st.success("✅ 출고 완료!")
                            time.sleep(0.5)
                            st.rerun()
            else:
                st.warning("장부에 없는 제품입니다.")
                with st.form("new_item"):
                    n_name = st.text_input("새 제품명", value=search_query)
                    n_qty = st.number_input("초기 수량", min_value=0)
                    if st.form_submit_button("신규 등록"):
                        new_row = pd.DataFrame([{"바코드": search_query, "제품명": n_name, "현재수량": n_qty}])
                        conn.update(worksheet="재고현황", data=pd.concat([inventory_df, new_row], ignore_index=True))
                        st.success("✅ 등록 완료!")
                        st.session_state.input_key += 1 
                        st.rerun()

    st.divider()
    if not inventory_df.empty:
        st.subheader("📊 전체 재고 현황")
        st.dataframe(inventory_df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("📑 최근 기록")
    if not log_df.empty:
        st.dataframe(log_df.iloc[::-1], use_container_width=True, hide_index=True)

with tab3:
    st.info("💡 삭제 데이터는 [삭제기록] 탭에 보관됩니다.")
    del_user = st.text_input("삭제자", value="약사")
    if st.button("❌ 제품 삭제 (선택 제품)"):
        # 삭제 로직은 이전과 동일 (생략)
        pass
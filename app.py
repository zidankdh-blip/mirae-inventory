import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# 1. 화면 설정
st.set_page_config(page_title="미래약국 재고관리", layout="wide")
st.title("💊 미래약국 스마트 재고관리 (안정화 버전)")

conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 데이터 불러오기 (과부하 방지 로직)
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
            st.error("⚠️ 장부 제목을 확인해주세요. (바코드, 제품명, 현재수량)")
        else:
            # 바코드 일치 또는 제품명 포함 검색
            match = inventory_df[
                (inventory_df['바코드'].astype(str) == search_query) | 
                (inventory_df['제품명'].astype(str).str.contains(search_query, na=False))
            ]
            
            # --- [A] 이미 등록된 제품일 때 ---
            if not match.empty:
                idx = match.index[0]
                row = match.iloc[0]
                st.info(f"📦 **{row['제품명']}** | 현재 재고: **{row['현재수량']}**개")
                
                c1, c2 = st.columns(2)
                qty = c1.number_input("입출고 수량 입력", min_value=1, value=1)
                user = c2.text_input("담당자 성함", value="약사")
                
                b1, b2 = st.columns(2)
                
                if b1.button("🟢 입고 (+)", use_container_width=True):
                    with st.spinner("업데이트 중..."):
                        new_q = row['현재수량'] + qty
                        inventory_df.at[idx, '현재수량'] = new_q
                        new_log = pd.DataFrame([{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "바코드": row['바코드'], "제품명": row['제품명'], "작업": "입고(+)", "수량": qty, "잔여재고": new_q, "담당자": user}])
                        conn.update(worksheet="재고현황", data=inventory_df)
                        conn.update(worksheet="기록장", data=pd.concat([log_df, new_log], ignore_index=True))
                        st.session_state.input_key += 1 
                        st.success(f"✅ {row['제품명']} {qty}개 입고 완료!")
                        time.sleep(0.5)
                        st.rerun()
                    
                if b2.button("🔴 출고 (-)", use_container_width=True):
                    if row['현재수량'] < qty:
                        st.error(f"⚠️ 재고가 부족합니다! (현재 {row['현재수량']}개)")
                    else:
                        with st.spinner("업데이트 중..."):
                            new_q = row['현재수량'] - qty
                            inventory_df.at[idx, '현재수량'] = new_q
                            new_log = pd.DataFrame([{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "바코드": row['바코드'], "제품명": row['제품명'], "작업": "출고(-)", "수량": qty, "잔여재고": new_q, "담당자": user}])
                            conn.update(worksheet="재고현황", data=inventory_df)
                            conn.update(worksheet="기록장", data=pd.concat([log_df, new_log], ignore_index=True))
                            st.session_state.input_key += 1 
                            st.success(f"✅ {row['제품명']} {qty}개 출고 완료!")
                            time.sleep(0.5)
                            st.rerun()
            
            # --- [B] 신규 제품 등록일 때 ---
            else:
                st.warning(f"⚠️ '{search_query}'는 장부에 없습니다. 새로 등록하시겠습니까?")
                with st.form("new_item_form"):
                    st.write("🆕 신규 제품 정보 입력")
                    # 검색어에 글자를 쳤으면 제품명에, 숫자를 쳤으면 바코드에 자동 입력
                    is_numeric = search_query.isdigit()
                    reg_name = st.text_input("제품명", value="" if is_numeric else search_query)
                    reg_barcode = st.text_input("바코드 번호", value=search_query if is_numeric else "")
                    reg_qty = st.number_input("초기 입고 수량", min_value=0, value=0)
                    reg_user = st.text_input("등록 담당자", value="약사")
                    
                    if st.form_submit_button("➕ 신규 제품 등록하기"):
                        if not reg_name:
                            st.error("제품명을 입력해주세요!")
                        else:
                            with st.spinner("장부 등록 중..."):
                                new_row = pd.DataFrame([{"바코드": reg_barcode, "제품명": reg_name, "현재수량": reg_qty}])
                                new_log = pd.DataFrame([{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "바코드": reg_barcode, "제품명": reg_name, "작업": "신규등록", "수량": reg_qty, "잔여재고": reg_qty, "담당자": reg_user}])
                                
                                conn.update(worksheet="재고현황", data=pd.concat([inventory_df, new_row], ignore_index=True))
                                conn.update(worksheet="기록장", data=pd.concat([log_df, new_log], ignore_index=True))
                                
                                st.session_state.input_key += 1 
                                st.success(f"✅ {reg_name} 등록 및 입고 완료!")
                                time.sleep(1)
                                st.rerun()

    st.divider()
    if not inventory_df.empty:
        st.subheader("📊 전체 재고 현황")
        # 5개 미만인 경우 빨간색으로 강조
        def color_low_stock(val):
            color = 'red' if val < 5 else 'black'
            return f'color: {color}; font-weight: bold' if val < 5 else ''

        st.dataframe(inventory_df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("📑 최근 기록 (최신순)")
    if not log_df.empty:
        st.dataframe(log_df.iloc[::-1], use_container_width=True, hide_index=True)

with tab3:
    # 이전 답변에서 드린 제품/기록 삭제 로직이 들어가는 곳입니다.
    st.info("💡 삭제 데이터는 [삭제기록] 탭에 보관됩니다.")
    del_user = st.text_input("삭제 진행자 이름", value="약사")
    
    col_del1, col_del2 = st.columns(2)
    with col_del1:
        st.subheader("🗑️ 제품 삭제")
        if not inventory_df.empty:
            inv_options = inventory_df['바코드'].astype(str) + " - " + inventory_df['제품명'].astype(str)
            item_to_delete = st.selectbox("삭제 제품 선택", inv_options.tolist(), key="del_box")
            if st.button("❌ 제품 영구 삭제"):
                del_barcode = item_to_delete.split(" - ")[0]
                del_target = inventory_df[inventory_df['바코드'].astype(str) == del_barcode].iloc[0]
                new_del_log = pd.DataFrame([{"삭제일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "구분": "제품삭제", "바코드": del_target['바코드'], "제품명": del_target['제품명'], "상세내용": "제품 삭제됨", "담당자": del_user}])
                updated_inv = inventory_df[inventory_df['바코드'].astype(str) != del_barcode].reset_index(drop=True)
                conn.update(worksheet="삭제기록", data=pd.concat([delete_df, new_del_log], ignore_index=True))
                conn.update(worksheet="재고현황", data=updated_inv)
                st.success("삭제 완료")
                st.rerun()
    
    with col_del2:
        st.subheader("🗑️ 기록 취소")
        if not log_df.empty:
            recent_logs = log_df.tail(20).copy().iloc[::-1]
            log_options = [f"[{idx}] {row['일시']} | {row['제품명']}" for idx, row in recent_logs.iterrows()]
            selected_log = st.selectbox("기록 선택", log_options)
            if st.button("⚠️ 기록 삭제"):
                log_idx = int(selected_log.split("]")[0][1:])
                updated_log = log_df.drop(index=log_idx).reset_index(drop=True)
                conn.update(worksheet="기록장", data=updated_log)
                st.success("기록 삭제 완료")
                st.rerun()
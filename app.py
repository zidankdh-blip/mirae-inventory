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
    st.info("💡 여기서 삭제한 데이터는 구글 시트의 [삭제기록] 탭에 안전하게 보관됩니다.")
    del_user = st.text_input("삭제 진행자 이름 (기록용)", value="약사")
    
    col_del1, col_del2 = st.columns(2)
    
    with col_del1:
        st.subheader("🗑️ 제품 삭제")
        if not inventory_df.empty and '바코드' in inventory_df.columns:
            # 선택하기 편하게 [바코드 - 제품명] 형식으로 보여줍니다.
            inv_options = inventory_df['바코드'].astype(str) + " - " + inventory_df['제품명'].astype(str)
            item_to_delete = st.selectbox("삭제할 제품 선택", inv_options.tolist(), key="del_inv_box")
            
            if st.button("❌ 선택한 제품 영구 삭제", use_container_width=True):
                with st.spinner("삭제 중..."):
                    del_barcode = item_to_delete.split(" - ")[0]
                    # 삭제할 데이터 백업용 추출
                    del_target = inventory_df[inventory_df['바코드'].astype(str) == del_barcode].iloc[0]
                    
                    # 1. 삭제기록(휴지통)에 저장
                    new_del_log = pd.DataFrame([{
                        "삭제일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "구분": "제품삭제",
                        "바코드": del_target['바코드'],
                        "제품명": del_target['제품명'],
                        "상세내용": f"잔여재고 {del_target['현재수량']}개 상태에서 삭제됨",
                        "담당자": del_user
                    }])
                    
                    # 2. 실제 재고현황에서 제외
                    updated_inv = inventory_df[inventory_df['바코드'].astype(str) != del_barcode].reset_index(drop=True)
                    
                    # 3. 구글 시트 업데이트
                    conn.update(worksheet="삭제기록", data=pd.concat([delete_df, new_del_log], ignore_index=True))
                    conn.update(worksheet="재고현황", data=updated_inv)
                    
                    st.success(f"✅ {del_target['제품명']} 삭제 완료!")
                    time.sleep(1)
                    st.rerun()
        else:
            st.write("삭제할 제품이 없습니다.")

    with col_del2:
        st.subheader("🗑️ 입출고 기록 취소")
        if not log_df.empty:
            # 최근 기록 20개만 보여주기
            recent_logs = log_df.tail(20).copy().iloc[::-1]
            log_options = [f"[{idx}] {row['일시']} | {row['제품명']} | {row['작업']}" for idx, row in recent_logs.iterrows()]
            
            selected_log = st.selectbox("취소(삭제)할 기록 선택", log_options)
            
            if st.button("⚠️ 기록 취소", use_container_width=True):
                with st.spinner("기록 삭제 중..."):
                    log_idx = int(selected_log.split("]")[0][1:])
                    del_log_target = log_df.loc[log_idx]
                    
                    # 삭제기록 백업
                    new_del_log = pd.DataFrame([{
                        "삭제일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "구분": "기록취소",
                        "바코드": del_log_target['바코드'],
                        "제품명": del_log_target['제품명'],
                        "상세내용": f"[{del_log_target['작업']} {del_log_target['수량']}개] 기록 삭제됨",
                        "담당자": del_user
                    }])
                    
                    # 기록장에서 삭제
                    updated_log = log_df.drop(index=log_idx).reset_index(drop=True)
                    
                    conn.update(worksheet="삭제기록", data=pd.concat([delete_df, new_del_log], ignore_index=True))
                    conn.update(worksheet="기록장", data=updated_log)
                    
                    st.success("✅ 기록이 취소되었습니다.")
                    time.sleep(1)
                    st.rerun()
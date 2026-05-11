import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from pyzbar.pyzbar import decode
from PIL import Image

# 1. 화면 설정
st.set_page_config(page_title="미래약국 재고관리", layout="wide")
st.title("💊 미래약국 스마트 재고관리 (자동 초기화)")

conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        inv = conn.read(worksheet="재고현황", ttl="0")
        log = conn.read(worksheet="기록장", ttl="0")
        del_log = conn.read(worksheet="삭제기록", ttl="0")
        
        for df in [inv, log, del_log]:
            if not df.empty and '바코드' in df.columns:
                df['바코드'] = df['바코드'].astype(str).str.replace(r'\.0$', '', regex=True)
                df['바코드'] = df['바코드'].replace('nan', '')
        return inv, log, del_log
    except:
        st.error("⚠️ 구글 시트에 [재고현황, 기록장, 삭제기록] 탭이 모두 있는지 확인해주세요.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

inventory_df, log_df, delete_df = load_data()

# ⭐ 검색창 자동 초기화를 위한 핵심 세팅
if 'search_box' not in st.session_state:
    st.session_state.search_box = ""

tab1, tab2, tab3 = st.tabs(["🚀 입출고/스캔", "📜 입출고 내역", "⚙️ 데이터 관리(휴지통)"])

with tab1:
    with st.expander("📸 카메라 바코드 스캔"):
        img_file = st.camera_input("바코드를 찍어주세요")
        if img_file:
            img = Image.open(img_file)
            decoded = decode(img)
            if decoded:
                barcode = decoded[0].data.decode('utf-8')
                if st.session_state.search_box != barcode:
                    st.session_state.search_box = barcode
                    st.rerun()
            else:
                st.warning("바코드 인식 실패. 더 밝은 곳에서 찍어주세요.")

    # ⭐ 지우기 버튼 없앰 & key="search_box"로 직접 연결
    search_query = st.text_input("바코드 또는 제품명 입력 (엔터)", 
                                 key="search_box",
                                 placeholder="여기에 입력하거나 위 카메라를 쓰세요")

    if search_query:
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
                new_q = row['현재수량'] + qty
                inventory_df.at[idx, '현재수량'] = new_q
                new_log = pd.DataFrame([{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "바코드": row['바코드'], "제품명": row['제품명'], "작업": "입고(+)", "수량": qty, "잔여재고": new_q, "담당자": user}])
                conn.update(worksheet="재고현황", data=inventory_df)
                conn.update(worksheet="기록장", data=pd.concat([log_df, new_log], ignore_index=True))
                st.success("✅ 입고 완료!")
                
                # ⭐ 작업 완료 즉시 검색창 빈칸으로 싹 지우기 ⭐
                st.session_state.search_box = ""
                st.rerun()
                
            # --- 출고 처리 ---
            if b2.button("🔴 출고 (-)", use_container_width=True):
                if row['현재수량'] < qty:
                    st.error("재고가 부족합니다!")
                else:
                    new_q = row['현재수량'] - qty
                    inventory_df.at[idx, '현재수량'] = new_q
                    new_log = pd.DataFrame([{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "바코드": row['바코드'], "제품명": row['제품명'], "작업": "출고(-)", "수량": qty, "잔여재고": new_q, "담당자": user}])
                    conn.update(worksheet="재고현황", data=inventory_df)
                    conn.update(worksheet="기록장", data=pd.concat([log_df, new_log], ignore_index=True))
                    st.success("✅ 출고 완료!")
                    
                    # ⭐ 작업 완료 즉시 검색창 빈칸으로 싹 지우기 ⭐
                    st.session_state.search_box = ""
                    st.rerun()
                    
        # --- 신규 등록 처리 ---
        else:
            st.warning("장부에 없는 제품입니다. 신규 등록할까요?")
            with st.form("new_item"):
                n_name = st.text_input("새 제품명", value=search_query)
                n_qty = st.number_input("초기 수량", min_value=0)
                n_user = st.text_input("등록자", value="약사")
                if st.form_submit_button("신규 등록"):
                    new_row = pd.DataFrame([{"바코드": search_query, "제품명": n_name, "현재수량": n_qty}])
                    conn.update(worksheet="재고현황", data=pd.concat([inventory_df, new_row], ignore_index=True))
                    new_log = pd.DataFrame([{"일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "바코드": search_query, "제품명": n_name, "작업": "신규등록", "수량": n_qty, "잔여재고": n_qty, "담당자": n_user}])
                    conn.update(worksheet="기록장", data=pd.concat([log_df, new_log], ignore_index=True))
                    st.success("✅ 신규 등록 완료!")
                    
                    # ⭐ 작업 완료 즉시 검색창 빈칸으로 싹 지우기 ⭐
                    st.session_state.search_box = ""
                    st.rerun()

    st.divider()
    st.subheader("📊 재고 부족 현황 (5개 미만)")
    if not inventory_df.empty:
        def alert(r): return ['color:red; font-weight:bold' if r['현재수량'] < 5 else '' for _ in r]
        st.dataframe(inventory_df.style.apply(alert, axis=1), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("📑 최근 기록 (최신순)")
    if not log_df.empty:
        st.dataframe(log_df.iloc[::-1], use_container_width=True, hide_index=True)

with tab3:
    st.info("💡 여기서 삭제한 모든 데이터는 구글 시트의 [삭제기록] 탭에 안전하게 보관됩니다.")
    del_user = st.text_input("삭제 진행자 이름 (기록용)", value="약사")
    
    col_del1, col_del2 = st.columns(2)
    
    with col_del1:
        st.subheader("🗑️ 제품 삭제")
        if not inventory_df.empty:
            inv_options = inventory_df['바코드'].astype(str) + " - " + inventory_df['제품명'].astype(str)
            item_to_delete = st.selectbox("삭제할 제품 선택", inv_options.tolist(), key="del_inv")
            
            if st.button("❌ 제품 통째로 삭제"):
                del_barcode = item_to_delete.split(" - ")[0]
                del_target = inventory_df[inventory_df['바코드'].astype(str) == del_barcode].iloc[0]
                
                new_del_log = pd.DataFrame([{
                    "삭제일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "구분": "제품통째로삭제", "바코드": del_target['바코드'], "제품명": del_target['제품명'],
                    "상세내용": f"잔여재고 {del_target['현재수량']}개 삭제됨", "담당자": del_user
                }])
                conn.update(worksheet="삭제기록", data=pd.concat([delete_df, new_del_log], ignore_index=True))
                
                updated_inv = inventory_df[inventory_df['바코드'].astype(str) != del_barcode].reset_index(drop=True)
                conn.update(worksheet="재고현황", data=updated_inv)
                st.success("✅ 삭제 완료 및 휴지통 보관!")
                st.rerun()

    with col_del2:
        st.subheader("🗑️ 기록 삭제")
        if not log_df.empty:
            recent_logs = log_df.copy().iloc[::-1]
            log_options = [f"[{idx}] {row['일시']} | {row['제품명']} | {row['작업']} {row['수량']}개" for idx, row in recent_logs.iterrows()]
            
            log_to_delete = st.selectbox("취소할 기록 선택", log_options, key="del_log")
            
            if st.button("❌ 선택한 기록 삭제"):
                idx_to_drop = int(log_to_delete.split("]")[0][1:])
                del_target_log = log_df.iloc[idx_to_drop]
                
                new_del_log = pd.DataFrame([{
                    "삭제일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "구분": "입출고기록삭제", "바코드": del_target_log['바코드'], "제품명": del_target_log['제품명'],
                    "상세내용": f"[{del_target_log['작업']} {del_target_log['수량']}개] 삭제됨", "담당자": del_user
                }])
                conn.update(worksheet="삭제기록", data=pd.concat([delete_df, new_del_log], ignore_index=True))
                
                updated_log = log_df.drop(index=idx_to_drop).reset_index(drop=True)
                conn.update(worksheet="기록장", data=updated_log)
                st.success("✅ 삭제 완료 및 휴지통 보관!")
                st.rerun()
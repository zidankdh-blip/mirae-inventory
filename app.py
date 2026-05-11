import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from pyzbar.pyzbar import decode
from PIL import Image

st.set_page_config(page_title="미래약국 재고관리 프로", layout="wide")
st.title("💊 미래약국 스마트 재고관리 시스템")

conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    inventory = conn.read(worksheet="재고현황", ttl="0")
    logs = conn.read(worksheet="기록장", ttl="0")
    return inventory, logs

inventory_df, log_df = load_data()

tab1, tab2 = st.tabs(["🚀 입출고 처리", "📜 입출고 기록장"])

with tab1:
    # --- [카메라 스캐너 기능] ---
    with st.expander("📸 카메라로 바코드 찍기 (클릭해서 열기)"):
        img_file = st.camera_input("바코드를 화면 중앙에 비추고 촬영하세요")
        if img_file:
            img = Image.open(img_file)
            decoded_objs = decode(img)
            if decoded_objs:
                barcode_data = decoded_objs[0].data.decode('utf-8')
                st.success(f"인식 성공: {barcode_data}")
                st.session_state['search_query'] = barcode_data
            else:
                st.warning("바코드를 인식하지 못했습니다. 다시 선명하게 찍어주세요.")

    # 검색어 입력창 (카메라로 찍으면 자동으로 숫자가 들어갑니다)
    search_query = st.text_input("바코드 스캔 또는 제품명 직접 입력", 
                                 value=st.session_state.get('search_query', ""),
                                 placeholder="예: 8801234... 또는 박카스")

    if search_query:
        if '바코드' not in inventory_df.columns:
            st.error("⚠️ 시트 제목에 '바코드'가 없습니다.")
        else:
            match_barcode = inventory_df['바코드'].astype(str) == search_query
            match_name = inventory_df['제품명'].astype(str).str.contains(search_query, na=False)
            result = inventory_df[match_barcode | match_name]
            
            if not result.empty:
                idx = result.index[0]
                name = result.iloc[0]['제품명']
                current_qty = result.iloc[0]['현재수량']
                
                st.info(f"📦 제품: **{name}** | 현재 재고: **{current_qty}**개")
                
                col1, col2 = st.columns(2)
                qty_change = col1.number_input("수량 입력", min_value=1, value=1)
                user_name = col2.text_input("담당자명", value="약사") 
                
                btn_col1, btn_col2 = st.columns(2)
                in_btn = btn_col1.button("🟢 입고하기 (+)", use_container_width=True)
                out_btn = btn_col2.button("🔴 출고하기 (-)", use_container_width=True)
                
                if in_btn or out_btn:
                    action = "입고(+)" if in_btn else "출고(-)"
                    new_qty = current_qty + qty_change if in_btn else current_qty - qty_change
                    
                    if new_qty < 0:
                        st.error("⚠️ 출고 수량이 현재 재고보다 많습니다!")
                    else:
                        inventory_df.at[idx, '현재수량'] = new_qty
                        new_log = pd.DataFrame([{
                            "일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "바코드": search_query, "제품명": name, "작업": action,
                            "수량": qty_change, "잔여재고": new_qty, "담당자": user_name
                        }])
                        conn.update(worksheet="재고현황", data=inventory_df)
                        updated_log_df = pd.concat([log_df, new_log], ignore_index=True)
                        conn.update(worksheet="기록장", data=updated_log_df)
                        st.success(f"✅ {action} 완료!")
                        # 성공 후 검색창 비우기
                        if 'search_query' in st.session_state:
                            del st.session_state['search_query']
                        st.rerun()
            else:
                st.warning("신규 제품 등록이 필요합니다.")
                # (이후 신규 등록 폼 생략 - 이전 코드와 동일)

    # (이후 재고 현황판 및 기록장 탭 동일)
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from pyzbar.pyzbar import decode
from PIL import Image

# 1. 화면 설정
st.set_page_config(page_title="미래약국 재고관리 프로", layout="wide")
st.title("💊 미래약국 스마트 재고관리 시스템")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        inventory = conn.read(worksheet="재고현황", ttl="0")
        logs = conn.read(worksheet="기록장", ttl="0")
        return inventory, logs
    except:
        st.error("⚠️ 구글 시트 연결에 실패했습니다. 시트 이름이 '재고현황'과 '기록장'인지 확인해주세요.")
        return pd.DataFrame(), pd.DataFrame()

inventory_df, log_df = load_data()

# ⭐ 불편함 1 해결: 바코드에 붙는 소수점(.0) 강제 제거 함수
def clean_barcode(df):
    if not df.empty and '바코드' in df.columns:
        # 글자로 바꾸고, 맨 뒤에 .0이 있으면 없애버림
        df['바코드'] = df['바코드'].astype(str).str.replace(r'\.0$', '', regex=True)
        df['바코드'] = df['바코드'].replace('nan', '')
    return df

inventory_df = clean_barcode(inventory_df)
log_df = clean_barcode(log_df)

# 세션 상태(검색창 텍스트) 초기화
if 'search_box' not in st.session_state:
    st.session_state.search_box = ""

# 3개의 탭 구성
tab1, tab2, tab3 = st.tabs(["🚀 입출고 및 스캔", "📜 입출고 기록장", "⚙️ 데이터 관리 (삭제)"])

with tab1:
    with st.expander("📸 카메라로 바코드 찍기 (클릭해서 열기)"):
        img_file = st.camera_input("바코드를 화면 중앙에 비추고 촬영하세요")
        if img_file:
            img = Image.open(img_file)
            decoded_objs = decode(img)
            if decoded_objs:
                barcode_data = decoded_objs[0].data.decode('utf-8')
                st.success(f"✅ 바코드 인식 성공: {barcode_data}")
                st.session_state.search_box = barcode_data # 카메라 인식 후 검색창에 자동 입력
                st.rerun()
            else:
                st.warning("❌ 바코드를 인식하지 못했습니다. 더 밝은 곳에서 선명하게 찍어주세요.")

    # ⭐ 불편함 2 해결: key="search_box"로 묶어서 언제든 초기화할 수 있게 만듦
    search_query = st.text_input("바코드 스캔 또는 제품명 직접 입력", 
                                 key="search_box",
                                 placeholder="예: 8801234... 또는 박카스")

    if search_query:
        # 터치 한 번으로 검색창 날리기 버튼
        if st.button("🔄 지우고 다른 제품 검색하기"):
            st.session_state.search_box = ""
            st.rerun()
            
        if '바코드' not in inventory_df.columns or '제품명' not in inventory_df.columns:
            st.error("⚠️ 시트 첫 줄에 '바코드'와 '제품명' 제목이 있어야 합니다.")
        else:
            match_barcode = inventory_df['바코드'].astype(str) == search_query
            match_name = inventory_df['제품명'].astype(str).str.contains(search_query, na=False)
            result = inventory_df[match_barcode | match_name]
            
            # [A] 이미 등록된 제품일 때
            if not result.empty:
                idx = result.index[0]
                name = result.iloc[0]['제품명']
                current_qty = result.iloc[0]['현재수량']
                
                st.info(f"📦 제품 확인: **{name}** | 현재 재고: **{current_qty}**개")
                
                col1, col2 = st.columns(2)
                qty_change = col1.number_input("수량 입력", min_value=1, value=1)
                user_name = col2.text_input("담당자명", value="약사") 
                
                st.write("작업을 선택하세요:")
                btn_col1, btn_col2 = st.columns(2)
                in_btn = btn_col1.button("🟢 입고하기 (+)", use_container_width=True)
                out_btn = btn_col2.button("🔴 출고하기 (-)", use_container_width=True)
                
                if in_btn or out_btn:
                    action = "입고(+)" if in_btn else "출고(-)"
                    new_qty = current_qty + qty_change if in_btn else current_qty - qty_change
                    
                    if new_qty < 0:
                        st.error("⚠️ 현재 재고보다 많이 나갈 수 없습니다!")
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
                        
                        st.success(f"✅ {name} {action} 완료!")
                        # ⭐ 작업 완료 즉시 검색창 빈칸으로 만들기 ⭐
                        st.session_state.search_box = ""
                        st.rerun()
                        
            # [B] 처음 보는 제품일 때 (신규 등록)
            else:
                st.warning(f"⚠️ '{search_query}'(은)는 장부에 없습니다. 새로 등록할까요?")
                with st.form("new_reg_form"):
                    new_name = st.text_input("제품명 입력", value=search_query)
                    init_qty = st.number_input("초기 재고", min_value=0, value=0)
                    user_name = st.text_input("등록자", value="약사")
                    
                    if st.form_submit_button("신규 제품으로 등록"):
                        new_item = pd.DataFrame([{"바코드": search_query, "제품명": new_name, "현재수량": init_qty}])
                        updated_inventory = pd.concat([inventory_df, new_item], ignore_index=True)
                        
                        new_log = pd.DataFrame([{
                            "일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "바코드": search_query, "제품명": new_name, "작업": "신규등록",
                            "수량": init_qty, "잔여재고": init_qty, "담당자": user_name
                        }])
                        conn.update(worksheet="재고현황", data=updated_inventory)
                        updated_log_df = pd.concat([log_df, new_log], ignore_index=True)
                        conn.update(worksheet="기록장", data=updated_log_df)
                        
                        st.success(f"✅ {new_name} 등록 완료!")
                        # ⭐ 신규 등록 완료 즉시 검색창 빈칸으로 만들기 ⭐
                        st.session_state.search_box = ""
                        st.rerun()

    st.divider()
    st.subheader("📊 전체 재고 현황 (5개 미만 빨간색)")
    def highlight_low_stock(row):
        return ['color: red; font-weight: bold' if row['현재수량'] < 5 else '' for _ in row]
    if not inventory_df.empty:
        styled_df = inventory_df.style.apply(highlight_low_stock, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("📑 실시간 입출고 내역")
    if not log_df.empty:
        st.dataframe(log_df.iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.write("아직 기록이 없습니다.")

with tab3:
    st.info("💡 구글 시트에 직접 들어가지 않고도 잘못된 데이터를 앱에서 바로 지울 수 있습니다.")
    
    st.subheader("🗑️ 1. 장부에서 제품 완전히 지우기")
    if not inventory_df.empty:
        inv_options = inventory_df['바코드'].astype(str) + " - " + inventory_df['제품명'].astype(str)
        item_to_delete = st.selectbox("삭제할 제품을 선택하세요", inv_options.tolist(), key="del_inv")
        
        if st.button("❌ 선택한 제품 장부에서 삭제"):
            del_barcode = item_to_delete.split(" - ")[0]
            new_inventory = inventory_df[inventory_df['바코드'].astype(str) != del_barcode].reset_index(drop=True)
            conn.update(worksheet="재고현황", data=new_inventory)
            st.success(f"✅ 제품 삭제 및 연동 완료!")
            st.rerun()

    st.divider()

    st.subheader("🗑️ 2. 잘못된 입출고 기록 삭제하기")
    if not log_df.empty:
        recent_logs = log_df.copy().iloc[::-1]
        log_options = [f"[{idx}] {row['일시']} | {row['제품명']} | {row['작업']} {row['수량']}개" for idx, row in recent_logs.iterrows()]
        
        log_to_delete = st.selectbox("취소할 기록을 선택하세요", log_options, key="del_log")
        
        if st.button("❌ 선택한 기록 삭제"):
            idx_to_drop = int(log_to_delete.split("]")[0][1:])
            new_log_df = log_df.drop(index=idx_to_drop).reset_index(drop=True)
            conn.update(worksheet="기록장", data=new_log_df)
            st.success("✅ 해당 기록 삭제 및 연동 완료!")
            st.rerun()
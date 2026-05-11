import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="미래약국 재고관리 프로", layout="wide")
st.title("💊 미래약국 스마트 재고관리 시스템")

# 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 1. 데이터 불러오기
def load_data():
    inventory = conn.read(worksheet="재고현황", ttl="0")
    logs = conn.read(worksheet="기록장", ttl="0")
    return inventory, logs

inventory_df, log_df = load_data()

# 탭 메뉴 구성
tab1, tab2 = st.tabs(["🚀 입출고 처리", "📜 입출고 기록장"])

with tab1:
    search_query = st.text_input("바코드 스캔 또는 제품명 입력", placeholder="예: 8801234... 또는 박카스")

    if search_query:
        if '바코드' not in inventory_df.columns:
            st.error("⚠️ 시트 제목에 '바코드'가 없습니다. 구글 시트의 첫 줄을 [바코드, 제품명, 현재수량]으로 맞춰주세요.")
        else:
            result = inventory_df[inventory_df['바코드'].astype(str) == search_query]
            
            # [A] 이미 등록된 제품일 때 (입고/출고)
            if not result.empty:
                idx = result.index[0]
                name = result.iloc[0]['제품명']
                current_qty = result.iloc[0]['현재수량']
                
                st.info(f"📦 제품: **{name}** | 현재 재고: **{current_qty}**개")
                
                # 수량과 담당자만 입력받기
                col1, col2 = st.columns(2)
                qty_change = col1.number_input("수량 입력", min_value=1, value=1)
                user_name = col2.text_input("담당자명", value="약사") 
                
                st.write("어떤 작업을 진행할까요?")
                # 직관적인 2개의 대형 버튼 배치
                btn_col1, btn_col2 = st.columns(2)
                in_btn = btn_col1.button("🟢 입고하기 (+)", use_container_width=True)
                out_btn = btn_col2.button("🔴 출고하기 (-)", use_container_width=True)
                
                if in_btn or out_btn:
                    action = "입고(+)" if in_btn else "출고(-)"
                    # 출고일 때는 수량을 빼고, 입고일 때는 더함
                    new_qty = current_qty + qty_change if in_btn else current_qty - qty_change
                    
                    # 마이너스 재고 방지 (선택 사항)
                    if new_qty < 0:
                        st.error("⚠️ 출고 수량이 현재 재고보다 많습니다!")
                    else:
                        inventory_df.at[idx, '현재수량'] = new_qty
                        
                        new_log = pd.DataFrame([{
                            "일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "바코드": search_query,
                            "제품명": name,
                            "작업": action,
                            "수량": qty_change,
                            "잔여재고": new_qty,
                            "담당자": user_name
                        }])
                        
                        conn.update(worksheet="재고현황", data=inventory_df)
                        updated_log_df = pd.concat([log_df, new_log], ignore_index=True)
                        conn.update(worksheet="기록장", data=updated_log_df)
                        
                        st.success(f"✅ {action} 처리 완료! (잔여: {new_qty}개)")
                        st.rerun()
            # [B] 처음 보는 바코드일 때 (신규 등록 창 띄우기)
            else:
                st.warning("⚠️ 등록되지 않은 바코드/제품입니다. 신규 등록을 진행합니다.")
                with st.form("new_registration"):
                    new_name = st.text_input("제품명 입력 (예: 광동쌍화탕 1박스)")
                    init_qty = st.number_input("초기 입고 수량", min_value=0, value=0)
                    user_name = st.text_input("등록 담당자명", value="약사")
                    
                    if st.form_submit_button("신규 등록 및 장부 추가"):
                        # 1. 재고 시트에 추가
                        new_inventory = pd.DataFrame([{
                            "바코드": search_query, 
                            "제품명": new_name, 
                            "현재수량": init_qty
                        }])
                        updated_inventory_df = pd.concat([inventory_df, new_inventory], ignore_index=True)
                        
                        # 2. 기록장에 '신규등록'으로 추가
                        new_log = pd.DataFrame([{
                            "일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "바코드": search_query,
                            "제품명": new_name,
                            "작업": "신규등록",
                            "수량": init_qty,
                            "잔여재고": init_qty,
                            "담당자": user_name
                        }])
                        updated_log_df = pd.concat([log_df, new_log], ignore_index=True)
                        
                        # 3. 서버 전송
                        conn.update(worksheet="재고현황", data=updated_inventory_df)
                        conn.update(worksheet="기록장", data=updated_log_df)
                        
                        st.success(f"✅ 신규 제품 '{new_name}' 등록이 완료되었습니다!")
                        st.rerun()

    # --- 재고 부족 알림 현황판 ---
    st.divider()
    st.subheader("📊 전체 재고 현황 (5개 미만 빨간색 경고)")
    
    def highlight_low_stock(row):
        return ['color: red; font-weight: bold' if row['현재수량'] < 5 else '' for _ in row]

    if not inventory_df.empty:
        styled_df = inventory_df.style.apply(highlight_low_stock, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("📑 실시간 입출고 기록장")
    if not log_df.empty:
        st.dataframe(log_df.iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.write("기록이 아직 없습니다.")
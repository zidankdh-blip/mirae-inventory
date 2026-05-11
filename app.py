import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="미래약국 재고관리 프로", layout="wide")
st.title("💊 미래약국 스마트 재고관리 시스템")

# 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 1. 데이터 불러오기 (캐시 없이 최신 상태 유지)
def load_data():
    inventory = conn.read(worksheet="재고현황", ttl="0")
    logs = conn.read(worksheet="기록장", ttl="0")
    return inventory, logs

inventory_df, log_df = load_data()

# 탭 메뉴 구성 (입출고 / 기록장 확인)
tab1, tab2 = st.tabs(["🚀 입출고 처리", "📜 입출고 기록장"])

with tab1:
    search_query = st.text_input("바코드 스캔 또는 제품명 입력", placeholder="스캐너를 찍어주세요")

    if search_query:
        # 데이터에 '바코드' 컬럼이 있는지 확인 (에러 방지)
        if '바코드' not in inventory_df.columns:
            st.error("⚠️ 시트 제목에 '바코드'가 없습니다. 구글 시트 첫 줄을 확인해 주세요.")
        else:
            result = inventory_df[inventory_df['바코드'].astype(str) == search_query]
            
            if not result.empty:
                idx = result.index[0]
                name = result.iloc[0]['제품명']
                current_qty = result.iloc[0]['현재수량']
                
                st.info(f"📦 제품: **{name}** | 현재 재고: **{current_qty}**개")
                
                col1, col2, col3 = st.columns(3)
                action = col1.radio("작업", ["입고(+)", "출고(-)"])
                qty_change = col2.number_input("수량", min_value=1, value=1)
                user_name = col3.text_input("담당자명", value="약사") # 누가 했는지 기록
                
                if st.button("장부 업데이트 및 기록"):
                    # 1. 재고 계산
                    new_qty = current_qty + qty_change if action == "입고(+)" else current_qty - qty_change
                    inventory_df.at[idx, '현재수량'] = new_qty
                    
                    # 2. 기록장 한 줄 추가
                    new_log = pd.DataFrame([{
                        "일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "바코드": search_query,
                        "제품명": name,
                        "작업": action,
                        "수량": qty_change,
                        "잔여재고": new_qty,
                        "담당자": user_name
                    }])
                    
                    # 3. 구글 시트 전송
                    conn.update(worksheet="재고현황", data=inventory_df)
                    # 기록장은 기존 데이터에 붙여넣기
                    updated_log_df = pd.concat([log_df, new_log], ignore_index=True)
                    conn.update(worksheet="기록장", data=updated_log_df)
                    
                    st.success(f"처리 완료! (잔여: {new_qty}개)")
                    st.rerun()
            else:
                st.warning("신규 제품 등록이 필요합니다.")
                # (기존 신규 등록 로직 생략 - 필요시 추가 가능)

    # --- 재고 부족 알림 기능 (빨간색 표시) ---
    st.divider()
    st.subheader("📊 현재 재고 현황 (5개 미만 빨간색)")
    
    def highlight_low_stock(row):
        # '현재수량'이 5 미만이면 해당 행을 빨간색으로
        return ['color: red; font-weight: bold' if row['현재수량'] < 5 else '' for _ in row]

    if not inventory_df.empty:
        # 스타일 적용해서 테이블 표시
        styled_df = inventory_df.style.apply(highlight_low_stock, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("📑 최근 입출고 내역")
    if not log_df.empty:
        # 최근 기록이 위로 오도록 역순 표시
        st.dataframe(log_df.iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.write("기록이 아직 없습니다.")
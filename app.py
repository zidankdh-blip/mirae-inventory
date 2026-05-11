import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 화면 설정
st.set_page_config(page_title="미래약국 창고관리", layout="centered")
st.title("☁️ 미래약국 실시간 재고관리 (클라우드)")

# 1. 구글 시트 연결 (secrets.toml 정보를 자동으로 가져옴)
conn = st.connection("gsheets", type=GSheetsConnection)

# 데이터 불러오기 함수
def get_data():
    return conn.read(ttl="0")  # ttl="0"은 항상 최신 데이터를 가져온다는 뜻입니다.

df = get_data()

# 2. 통합 입력창 (스캐너 & 검색)
search_query = st.text_input("바코드를 스캔하거나 제품명을 입력하세요", placeholder="예: 8801234... 또는 쌍화탕")

if search_query:
    # 2-1. 바코드 검색 (일치하는 것 찾기)
    result = df[df['바코드'].astype(str) == search_query]
    
    if not result.empty:
        # 이미 등록된 제품인 경우
        idx = result.index[0]
        name = result.iloc[0]['제품명']
        current_qty = result.iloc[0]['현재수량']
        
        st.success(f"✅ 제품 확인: **{name}** (현재 재고: {current_qty}개)")
        
        col1, col2 = st.columns(2)
        qty_change = col1.number_input("수량 변경", min_value=1, value=1)
        action = col2.radio("작업 선택", ["입고(+)", "출고(-)"])
        
        if st.button("장부 업데이트"):
            new_qty = current_qty + qty_change if action == "입고(+)" else current_qty - qty_change
            df.at[idx, '현재수량'] = new_qty
            conn.update(data=df) # 구글 시트에 즉시 저장
            st.info(f"업데이트 완료! 새로운 재고: {new_qty}개")
            st.rerun()
            
    else:
        # 검색 결과가 바코드 숫자인 경우 신규 등록
        if search_query.isdigit():
            st.warning("⚠️ 등록되지 않은 바코드입니다. 신규 등록이 필요합니다.")
            with st.form("new_registration"):
                new_name = st.text_input("제품명 입력 (예: 박카스 F 1박스)")
                init_qty = st.number_input("기초 재고 설정", min_value=0, value=0)
                if st.form_submit_button("구글 시트에 등록"):
                    new_row = pd.DataFrame([{"바코드": search_query, "제품명": new_name, "현재수량": init_qty}])
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    conn.update(data=updated_df)
                    st.success("새 제품이 등록되었습니다!")
                    st.rerun()
        else:
            # 이름으로 검색한 경우
            search_res = df[df['제품명'].str.contains(search_query, na=False)]
            if not search_res.empty:
                st.write(f"🔍 **'{search_query}'** 검색 결과입니다.")
                st.dataframe(search_res, use_container_width=True)
            else:
                st.error("검색 결과가 없습니다.")

# 3. 전체 현황판
st.divider()
st.subheader("📊 실시간 전체 재고 현황")
if not df.empty:
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.write("등록된 재고가 없습니다.")
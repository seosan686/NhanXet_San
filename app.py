import streamlit as st
import google.generativeai as genai
from PIL import Image
import tempfile
import os
import io
import pandas as pd
from docx import Document
import time
import random

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Trợ Lý Nhập Liệu 4.0",
    page_icon="✍️",
    layout="centered"
)

# --- 2. CSS GIAO DIỆN ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #f0f2f6; }
    .header-box {
        background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%);
        padding: 30px; border-radius: 15px; text-align: center; color: white;
        margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .header-box h1 { color: white !important; margin: 0; font-size: 2rem; }
    
    div.stButton > button {
        background: linear-gradient(90deg, #11998e, #38ef7d);
        color: white !important; border: none; padding: 15px; font-weight: bold;
        border-radius: 10px; width: 100%; font-size: 18px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. HÀM XỬ LÝ ---

def classify_student(value):
    """Hàm phân loại học sinh"""
    s = str(value).upper().strip()
    # Ký tự
    if s == 'T': return 'Hoàn thành tốt'
    if s == 'H': return 'Hoàn thành'
    if s == 'C': return 'Chưa hoàn thành'
    # Điểm số
    try:
        score = float(value)
        if score >= 7: return 'Hoàn thành tốt'
        elif score >= 5: return 'Hoàn thành'
        else: return 'Chưa hoàn thành'
    except: return None

def process_ai_response_to_list(content, level_filter):
    """Lọc câu nhận xét"""
    comments = []
    current_level = ""
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        line_upper = line.upper()
        
        if "MỨC: HOÀN THÀNH TỐT" in line_upper: current_level = "Hoàn thành tốt"; continue
        if "MỨC: CHƯA HOÀN THÀNH" in line_upper: current_level = "Chưa hoàn thành"; continue
        if "MỨC: HOÀN THÀNH" in line_upper: current_level = "Hoàn thành"; continue
            
        if (line.startswith('-') or line.startswith('*') or line[0].isdigit()) and current_level == level_filter:
            clean_text = line.lstrip("-*1234567890. ").replace("**", "").strip()
            # Lọc bớt câu quá ngắn (dưới 30 ký tự là rác)
            if len(clean_text) > 30 and "MỨC:" not in clean_text: 
                comments.append(clean_text)
    return comments

# --- 4. GIAO DIỆN CHÍNH ---
st.markdown("""
<div class="header-box">
    <h1>✍️ AUTO-FILL NHẬN XÉT (TT27)</h1>
    <p>Phiên bản nhận xét chi tiết, đầy đủ 2 vế</p>
</div>
""", unsafe_allow_html=True)

# --- NHẬP KEY ---
with st.sidebar:
    st.header("🔐 Cấu hình")
    default_key = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else ""
    manual_key = st.text_input("🔑 Nhập API Key:", type="password")
    if manual_key: api_key = manual_key; st.info("Dùng Key nhập tay")
    elif default_key: api_key = default_key; st.success("Dùng Key hệ thống")
    else: api_key = None; st.warning("Chưa có Key!")

if api_key:
    try: genai.configure(api_key=api_key)
    except: st.error("Key lỗi!")

# --- 5. INPUT DATA ---
st.info("Bước 1: Tải file danh sách học sinh và minh chứng.")

c1, c2 = st.columns(2)
with c1:
    student_file = st.file_uploader("📂 File Danh sách HS (.xlsx):", type=["xlsx", "xls"])
with c2:
    evidence_files = st.file_uploader("📂 File Minh chứng bài dạy:", type=["pdf", "png", "jpg", "docx"], accept_multiple_files=True)

# --- 6. CẤU HÌNH XỬ LÝ ---
if student_file:
    try:
        df = pd.read_excel(student_file)
        st.write("▼ Xem trước danh sách học sinh:")
        st.dataframe(df.head(3), use_container_width=True)
        
        st.markdown("---")
        st.info("Bước 2: Cấu hình cột dữ liệu.")
        
        col_score = st.selectbox("📌 Chọn cột Mức đạt / Điểm số:", df.columns)
        col_new = st.text_input("📌 Tên cột sẽ điền nhận xét:", "Lời nhận xét GV")
        
        c3, c4 = st.columns(2)
        with c3: mon_hoc = st.text_input("📚 Môn học:", "Tin học")
        with c4: chu_de = st.text_input("📝 Chủ đề/Bài học:", "Chủ đề E")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 TỰ ĐỘNG ĐIỀN NHẬN XÉT (CHI TIẾT 300 KÝ TỰ)"):
            if not api_key: st.toast("Thiếu API Key!"); st.stop()
            
            progress_bar = st.progress(0, text="Đang phân tích dữ liệu...")
            
            # 1. Phân loại
            df['__Level_Temp__'] = df[col_score].apply(classify_student)
            
            # 2. Ngữ cảnh
            context_text = ""
            media_files = []
            if evidence_files:
                for file in evidence_files:
                    if file.name.endswith('.docx'):
                        try: doc = Document(file); context_text += "\n".join([p.text for p in doc.paragraphs])
                        except: pass
                    elif file.type == "application/pdf":
                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(file.getvalue()); media_files.append(genai.upload_file(tmp.name))
                    else: media_files.append(Image.open(file))

            # 3. Prompt (ĐÃ NÂNG CẤP MẠNH MẼ)
            progress_bar.progress(30, text="AI đang viết nhận xét chi tiết, đầy đủ 2 vế...")
            
            model = genai.GenerativeModel('gemini-2.5-flash-lite-preview-09-2025')
            
            prompt = f"""
            Bạn là giáo viên Tiểu học tâm huyết. Hãy viết bộ nhận xét CHI TIẾT cho môn {mon_hoc}, chủ đề: {chu_de}.
            Dữ liệu minh chứng từ bài dạy: {context_text[:3000]}...
            
            YÊU CẦU QUAN TRỌNG:
            1. ĐỘ DÀI: Khoảng 250 - 350 ký tự/câu. Không viết quá ngắn.
            2. TỪ CẤM: "Em", "Con", "Bạn", "Nắm được".
            3. CẤU TRÚC 2 VẾ (BẮT BUỘC):
               - Mức HOÀN THÀNH: [Vế 1: Điểm đã làm tốt] NHƯNG/TUY NHIÊN [Vế 2: Điểm cần rèn luyện thêm].
               - Mức CHƯA HOÀN THÀNH: [Vế 1: Sự tham gia/cố gắng dù nhỏ] NHƯNG [Vế 2: Biện pháp hỗ trợ cụ thể của GV/PH].
            
            HÃY VIẾT 3 NHÓM NHẬN XÉT (Mỗi nhóm 15 câu KHÁC NHAU):
            
            1. NHÓM MỨC: HOÀN THÀNH TỐT (Lời khen sâu sắc)
            - Ví dụ: Thể hiện tư duy rất tốt trong việc sắp xếp các thư mục trong máy tính, đồng thời biết hỗ trợ các bạn khác thực hành nhanh chóng.
            
            2. NHÓM MỨC: HOÀN THÀNH (Đủ 2 vế: Được và Chưa được)
            - Ví dụ: Thực hiện được thao tác lưu bài vào thư mục đúng quy định, tuy nhiên cần chú ý đặt tên file ngắn gọn và khoa học hơn để dễ tìm kiếm.
            
            3. NHÓM MỨC: CHƯA HOÀN THÀNH (Đủ 2 vế: Ghi nhận và Hỗ trợ)
            - Ví dụ: Có cố gắng quan sát thao tác của giáo viên trên màn hình, nhưng chưa tự mình thực hiện được việc tạo thư mục, cần giáo viên cầm tay chỉ việc thêm ở các tiết sau.
            
            ĐỊNH DẠNG TRẢ VỀ:
            I. MỨC: HOÀN THÀNH TỐT
            - [Câu 1]
            ...
            II. MỨC: HOÀN THÀNH
            ...
            III. MỨC: CHƯA HOÀN THÀNH
            ...
            """
            
            inputs = [prompt] + media_files
            response = model.generate_content(inputs)
            
            # 4. Xử lý kết quả
            pool_T = process_ai_response_to_list(response.text, "Hoàn thành tốt")
            pool_H = process_ai_response_to_list(response.text, "Hoàn thành")
            pool_C = process_ai_response_to_list(response.text, "Chưa hoàn thành")
            
            # Fallback
            if not pool_T: pool_T = ["Nắm vững kiến thức bài học, kỹ năng thực hành thành thạo và có tư duy sáng tạo trong quá trình học tập."]
            if not pool_H: pool_H = ["Hoàn thành các yêu cầu cơ bản của bài học, tuy nhiên cần rèn luyện thêm kỹ năng thực hành để thao tác nhanh hơn."]
            if not pool_C: pool_C = ["Có chú ý nghe giảng nhưng chưa thực hiện được yêu cầu bài học, cần sự hướng dẫn chi tiết hơn từ giáo viên."]

            # 5. Điền dữ liệu
            progress_bar.progress(80, text="Đang điền dữ liệu ngẫu nhiên vào file...")
            
            def fill_comment(level):
                if level == 'Hoàn thành tốt': return random.choice(pool_T)
                if level == 'Hoàn thành': return random.choice(pool_H)
                if level == 'Chưa hoàn thành': return random.choice(pool_C)
                return ""

            df[col_new] = df['__Level_Temp__'].apply(fill_comment)
            del df['__Level_Temp__']
            
            progress_bar.progress(100, text="Hoàn tất!")
            
            # 6. Xuất file
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
                ws = writer.sheets['Sheet1']
                # Tăng độ rộng cột để chứa nội dung dài
                ws.column_dimensions[chr(65 + df.columns.get_loc(col_new))].width = 80 
            output.seek(0)
            
            st.success("✅ Đã xong! Nội dung chi tiết, đầy đủ 2 vế.")
            st.download_button(
                label="⬇️ TẢI FILE EXCEL KẾT QUẢ",
                data=output,
                file_name=f"DanhSach_NhanXet_ChiTiet_{mon_hoc}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            
            with st.expander("Xem mẫu nhận xét (10 em đầu)"):
                st.dataframe(df[[col_score, col_new]].head(10), use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi đọc file Excel: {e}")

# --- FOOTER ---
st.markdown("<div style='text-align:center; margin-top:50px; color:#888;'>© 2025 - Thầy Sần Tool</div>", unsafe_allow_html=True)
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
    .success-box { background-color: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. HÀM XỬ LÝ ---

def classify_student(value):
    """Hàm phân loại học sinh dựa trên giá trị ô Excel (Điểm số hoặc Ký tự T/H/C)"""
    s = str(value).upper().strip()
    
    # Trường hợp ký tự
    if s == 'T': return 'Hoàn thành tốt'
    if s == 'H': return 'Hoàn thành'
    if s == 'C': return 'Chưa hoàn thành'
    
    # Trường hợp số
    try:
        score = float(value)
        if score >= 7: return 'Hoàn thành tốt'
        elif score >= 5: return 'Hoàn thành'
        else: return 'Chưa hoàn thành'
    except:
        return None # Không xác định được

def process_ai_response_to_list(content, level_filter):
    """Lọc các câu nhận xét từ phản hồi AI theo mức độ"""
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
            if len(clean_text) > 5: comments.append(clean_text)
    return comments

# --- 4. GIAO DIỆN CHÍNH ---
st.markdown("""
<div class="header-box">
    <h1>✍️ AUTO-FILL NHẬN XÉT (TT27)</h1>
    <p>Tự động điền lời nhận xét vào danh sách học sinh</p>
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
st.info("Bước 1: Tải file danh sách học sinh (Excel) và file minh chứng (Ảnh/PDF/Word) nếu có.")

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
        st.info("Bước 2: Chọn cột chứa Điểm số hoặc Mức đạt (T/H/C) để AI phân loại.")
        
        # Chọn cột điểm
        col_score = st.selectbox("📌 Chọn cột Mức đạt / Điểm số:", df.columns)
        
        # Nhập tên cột mới
        col_new = st.text_input("📌 Tên cột sẽ điền nhận xét:", "Lời nhận xét GV")
        
        # Thông tin môn học
        c3, c4 = st.columns(2)
        with c3: mon_hoc = st.text_input("📚 Môn học:", "Tin học")
        with c4: chu_de = st.text_input("📝 Chủ đề/Bài học:", "Chủ đề E")

        # Nút chạy
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 TỰ ĐỘNG ĐIỀN NHẬN XÉT VÀO FILE"):
            if not api_key: st.toast("Thiếu API Key!"); st.stop()
            
            progress_bar = st.progress(0, text="Đang phân tích dữ liệu...")
            
            # 1. Phân tích dữ liệu học sinh
            df['__Level_Temp__'] = df[col_score].apply(classify_student)
            
            counts = df['__Level_Temp__'].value_counts()
            st.write("📊 Thống kê sơ bộ:", counts.to_dict())
            
            # 2. Chuẩn bị ngữ cảnh minh chứng
            context_text = ""
            media_files = []
            
            if evidence_files:
                for file in evidence_files:
                    if file.name.endswith('.docx'):
                        try:
                            doc = Document(file)
                            context_text += "\n".join([p.text for p in doc.paragraphs])
                        except: pass
                    elif file.type == "application/pdf":
                         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(file.getvalue()); media_files.append(genai.upload_file(tmp.name))
                    else: # Ảnh
                        media_files.append(Image.open(file))

            # 3. Tạo kho nhận xét (Mỗi mức độ khoảng 15 câu mẫu đa dạng)
            progress_bar.progress(30, text="AI đang viết các mẫu câu nhận xét đa dạng...")
            
            model = genai.GenerativeModel('gemini-2.5-flash-lite-preview-09-2025')
            
            prompt = f"""
            Bạn là GV Tiểu học. Viết bộ nhận xét cho môn {mon_hoc}, bài {chu_de}.
            Dữ liệu minh chứng bài dạy: {context_text[:2000]}...
            
            YÊU CẦU:
            - Viết 15 câu nhận xét KHÁC NHAU cho mức: HOÀN THÀNH TỐT.
            - Viết 15 câu nhận xét KHÁC NHAU cho mức: HOÀN THÀNH.
            - Viết 15 câu nhận xét KHÁC NHAU cho mức: CHƯA HOÀN THÀNH.
            
            NGUYÊN TẮC: Không dùng "Em/Con", ngắn gọn, đúng TT27.
            
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
            
            # 4. Tách dữ liệu ra các kho
            pool_T = process_ai_response_to_list(response.text, "Hoàn thành tốt")
            pool_H = process_ai_response_to_list(response.text, "Hoàn thành")
            pool_C = process_ai_response_to_list(response.text, "Chưa hoàn thành")
            
            # Fallback nếu AI tạo lỗi
            if not pool_T: pool_T = ["Hoàn thành tốt nhiệm vụ học tập, có sự sáng tạo."]
            if not pool_H: pool_H = ["Hoàn thành yêu cầu bài học, cần tích cực hơn."]
            if not pool_C: pool_C = ["Cần cố gắng nhiều hơn để hoàn thành nhiệm vụ."]

            # 5. Điền vào Excel (Randomize)
            progress_bar.progress(80, text="Đang điền dữ liệu vào từng học sinh...")
            
            def fill_comment(level):
                if level == 'Hoàn thành tốt': return random.choice(pool_T)
                if level == 'Hoàn thành': return random.choice(pool_H)
                if level == 'Chưa hoàn thành': return random.choice(pool_C)
                return ""

            df[col_new] = df['__Level_Temp__'].apply(fill_comment)
            
            # Xóa cột tạm
            del df['__Level_Temp__']
            
            progress_bar.progress(100, text="Hoàn tất!")
            
            # 6. Xuất file
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
                # Auto-adjust column width
                ws = writer.sheets['Sheet1']
                ws.column_dimensions[chr(65 + df.columns.get_loc(col_new))].width = 50 
            output.seek(0)
            
            st.success("✅ Đã xử lý xong! Hãy tải file về.")
            st.download_button(
                label="⬇️ TẢI FILE EXCEL ĐÃ CÓ NHẬN XÉT",
                data=output,
                file_name=f"DanhSach_NhanXet_{mon_hoc}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            
            with st.expander("Xem kết quả mẫu"):
                st.dataframe(df[[col_score, col_new]].head(10), use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi đọc file Excel: {e}")

# --- FOOTER ---
st.markdown("<div style='text-align:center; margin-top:50px; color:#888;'>© 2025 - Thầy Sần Tool</div>", unsafe_allow_html=True)
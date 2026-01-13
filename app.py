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
    page_title="Trợ Lý Nhập Liệu 5.0 (Select Column)",
    page_icon="💎",
    layout="centered"
)

# --- 2. CSS GIAO DIỆN ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #f4f6f9; }
    .header-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px; border-radius: 15px; text-align: center; color: white;
        margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .header-box h1 { color: white !important; margin: 0; font-size: 2rem; }
    
    div.stButton > button {
        background: linear-gradient(90deg, #667eea, #764ba2);
        color: white !important; border: none; padding: 15px; font-weight: bold;
        border-radius: 10px; width: 100%; font-size: 18px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. HÀM XỬ LÝ ---

def classify_student(value):
    """Phân loại học sinh"""
    s = str(value).upper().strip()
    if s == 'T': return 'Hoàn thành tốt'
    if s == 'H': return 'Hoàn thành'
    if s == 'C': return 'Chưa hoàn thành'
    try:
        score = float(value)
        if score >= 7: return 'Hoàn thành tốt'
        elif score >= 5: return 'Hoàn thành'
        else: return 'Chưa hoàn thành'
    except: return None

def clean_comment_format(text):
    """Chuẩn hóa văn bản: Chỉ viết hoa chữ cái đầu"""
    if not text: return ""
    text = text.strip().strip("-*•").strip()
    if len(text) == 0: return ""
    return text[0].upper() + text[1:]

def process_ai_response_unique(content, target_level, needed_count):
    """Lấy danh sách nhận xét độc nhất"""
    comments = []
    current_level = ""
    
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        line_upper = line.upper()
        
        if "MỨC: HOÀN THÀNH TỐT" in line_upper: current_level = "Hoàn thành tốt"; continue
        if "MỨC: CHƯA HOÀN THÀNH" in line_upper: current_level = "Chưa hoàn thành"; continue
        if "MỨC: HOÀN THÀNH" in line_upper: current_level = "Hoàn thành"; continue
            
        if (line.startswith('-') or line.startswith('*') or line[0].isdigit()) and current_level == target_level:
            raw_text = line.lstrip("-*1234567890. ").replace("**", "").strip()
            if "MỨC:" in raw_text.upper(): continue
            final_text = clean_comment_format(raw_text)
            if len(final_text) > 15: 
                comments.append(final_text)

    if len(comments) < needed_count:
        while len(comments) < needed_count:
            comments.append(random.choice(comments) if comments else "Hoàn thành nhiệm vụ học tập.")
            
    random.shuffle(comments)
    return comments

# --- 4. GIAO DIỆN CHÍNH ---
st.markdown("""
<div class="header-box">
    <h1>💎 TRỢ LÝ NHẬN XÉT TỰ ĐỘNG TT27</h1>
    <p>Tác giả: Lù Seo Sần - Trường PTDTBT TH Bản Ngò</p>
</div>
""", unsafe_allow_html=True)

# --- KEY ---
with st.sidebar:
    st.header("🔐 Cấu hình")
    default_key = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else ""
    manual_key = st.text_input("🔑 Nhập API Key:", type="password")
    if manual_key: api_key = manual_key; st.info("Key cá nhân")
    elif default_key: api_key = default_key; st.success("Key hệ thống")
    else: api_key = None; st.warning("Thiếu Key!")

if api_key:
    try: genai.configure(api_key=api_key)
    except: st.error("Key lỗi!")

# --- 5. INPUT ---
st.info("Bước 1: Tải file danh sách và minh chứng.")
c1, c2 = st.columns(2)
with c1: student_file = st.file_uploader("📂 Danh sách HS (.xlsx):", type=["xlsx", "xls"])
with c2: evidence_files = st.file_uploader("📂 Minh chứng (Ảnh/Word/PDF):", type=["pdf", "png", "jpg", "docx"], accept_multiple_files=True)

# --- 6. XỬ LÝ ---
if student_file:
    df = pd.read_excel(student_file)
    st.write("▼ Danh sách học sinh (3 dòng đầu):")
    st.dataframe(df.head(3), use_container_width=True)
    st.markdown("---")
    
    # [CẬP NHẬT MỚI] Chuyển thành Selectbox cho cả 2 mục
    all_columns = list(df.columns)
    
    st.warning("⚠️ LƯU Ý: Cột được chọn ở mục 'Đầu ra' sẽ bị GHI ĐÈ dữ liệu mới.")
    
    col1, col2 = st.columns(2)
    with col1:
        col_score = st.selectbox("📌 Chọn cột ĐIỂM SỐ (Đầu vào):", all_columns, index=0)
    with col2:
        # Tự động chọn cột cuối cùng làm mặc định (thường là cột Nhận xét trống)
        default_index = len(all_columns) - 1
        col_new = st.selectbox("📌 Chọn cột NHẬN XÉT (Đầu ra):", all_columns, index=default_index)

    c3, c4 = st.columns(2)
    with c3: mon_hoc = st.text_input("📚 Môn:", "Tin học")
    with c4: chu_de = st.text_input("📝 Bài học:", "Học kỳ I")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 ĐIỀN NHẬN XÉT VÀO CỘT ĐÃ CHỌN"):
        if not api_key: st.toast("Thiếu Key!"); st.stop()
        
        # Kiểm tra trùng cột (cảnh báo nhẹ nhưng vẫn cho chạy)
        if col_score == col_new:
            st.error("❌ Cột Điểm và Cột Nhận xét đang trùng nhau! Vui lòng chọn khác.")
            st.stop()
            
        # 1. Đếm số lượng
        progress_bar = st.progress(0, text="Đang phân tích số lượng...")
        
        df['__Level__'] = df[col_score].apply(classify_student)
        counts = df['__Level__'].value_counts()
        
        count_T = counts.get('Hoàn thành tốt', 0)
        count_H = counts.get('Hoàn thành', 0)
        count_C = counts.get('Chưa hoàn thành', 0)
        
        st.write(f"📊 Số lượng cần viết: Tốt ({count_T}), Hoàn thành ({count_H}), Chưa HT ({count_C})")
        
        # 2. Xử lý minh chứng
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

        # 3. Prompt
        req_T = int(count_T * 1.1) + 2
        req_H = int(count_H * 1.1) + 2
        req_C = int(count_C * 1.1) + 2
        
        progress_bar.progress(20, text="AI đang viết nhận xét...")
        
        model = genai.GenerativeModel('gemini-2.5-flash-lite-preview-09-2025')
        
        prompt = f"""
        Bạn là giáo viên. Viết nhận xét DUY NHẤT cho HS môn {mon_hoc}, bài {chu_de}.
        Minh chứng: {context_text[:2000]}...
        
        QUY TẮC:
        1. Chỉ viết hoa chữ cái đầu câu. KHÔNG viết in hoa toàn bộ.
        2. TỪ CẤM: "Em", "Con", "Bạn".
        3. ĐỘ DÀI: ~200 ký tự.
        
        SỐ LƯỢNG:
        - {req_T} câu Mức HOÀN THÀNH TỐT (Chỉ khen, KHÔNG dùng 'tuy nhiên').
        - {req_H} câu Mức HOÀN THÀNH (Có 2 vế: Được + Cần rèn thêm).
        - {req_C} câu Mức CHƯA HOÀN THÀNH (Có 2 vế: Tham gia + Cần hỗ trợ).
        
        ĐỊNH DẠNG:
        I. MỨC: HOÀN THÀNH TỐT
        - [Câu 1]
        ...
        II. MỨC: HOÀN THÀNH
        ...
        III. MỨC: CHƯA HOÀN THÀNH
        ...
        """
        
        inputs = [prompt] + media_files
        try:
            response = model.generate_content(inputs)
            
            # 4. Phân phối
            progress_bar.progress(70, text="Đang điền vào file...")
            
            pool_T = process_ai_response_unique(response.text, "Hoàn thành tốt", count_T)
            pool_H = process_ai_response_unique(response.text, "Hoàn thành", count_H)
            pool_C = process_ai_response_unique(response.text, "Chưa hoàn thành", count_C)
            
            def assign_comment(level):
                if level == 'Hoàn thành tốt' and pool_T: return pool_T.pop(0)
                if level == 'Hoàn thành' and pool_H: return pool_H.pop(0)
                if level == 'Chưa hoàn thành' and pool_C: return pool_C.pop(0)
                return "" # Trả về rỗng nếu không xác định được mức

            # Ghi đè vào cột đã chọn
            df[col_new] = df['__Level__'].apply(assign_comment)
            del df['__Level__']
            
            progress_bar.progress(100, text="Xong!")
            
            # 5. Xuất file
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
                ws = writer.sheets['Sheet1']
                # Tìm index của cột đã chọn để chỉnh độ rộng
                col_idx = df.columns.get_loc(col_new)
                ws.column_dimensions[chr(65 + col_idx)].width = 60
            output.seek(0)
            
            st.success(f"✅ Đã điền xong nhận xét vào cột: [{col_new}]")
            st.download_button("⬇️ Tải File Excel Kết Quả", output, f"NhanXet_{mon_hoc}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            with st.expander("Kiểm tra kết quả"):
                st.dataframe(df[[col_score, col_new]].sample(min(5, len(df))), use_container_width=True)

        except Exception as e:
            st.error(f"Lỗi: {e}")

# --- FOOTER ---
st.markdown("<div style='text-align:center; margin-top:50px; color:#888;'>© 2025 - Thầy Sần Tool</div>", unsafe_allow_html=True)
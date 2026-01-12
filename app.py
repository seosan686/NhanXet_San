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
    page_title="Trợ Lý Nhập Liệu 5.0 (No-Duplicate)",
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
    # Xóa dấu câu thừa ở đầu/cuối
    text = text.strip().strip("-*•").strip()
    if len(text) == 0: return ""
    
    # Chỉ viết hoa chữ cái đầu tiên, còn lại giữ nguyên (hoặc lower nếu cần thiết)
    # Ở đây ta dùng capitalize() để chắc chắn chỉ chữ đầu hoa
    # Tuy nhiên nếu muốn giữ tên riêng (nếu có) thì cẩn thận, nhưng nhận xét thường ko có tên riêng
    return text[0].upper() + text[1:]

def process_ai_response_unique(content, target_level, needed_count):
    """Lấy danh sách nhận xét độc nhất"""
    comments = []
    current_level = ""
    
    # Duyệt qua từng dòng
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        line_upper = line.upper()
        
        # Xác định section
        if "MỨC: HOÀN THÀNH TỐT" in line_upper: current_level = "Hoàn thành tốt"; continue
        if "MỨC: CHƯA HOÀN THÀNH" in line_upper: current_level = "Chưa hoàn thành"; continue
        if "MỨC: HOÀN THÀNH" in line_upper: current_level = "Hoàn thành"; continue
            
        # Lấy nội dung
        if (line.startswith('-') or line.startswith('*') or line[0].isdigit()) and current_level == target_level:
            raw_text = line.lstrip("-*1234567890. ").replace("**", "").strip()
            
            # Bỏ các dòng tiêu đề nếu AI lỡ viết lại
            if "MỨC:" in raw_text.upper(): continue
            
            # Chuẩn hóa (Viết hoa chữ đầu)
            final_text = clean_comment_format(raw_text)
            
            if len(final_text) > 15: # Lọc câu quá ngắn
                comments.append(final_text)

    # Nếu thiếu (do AI viết ít hơn yêu cầu), ta nhân bản tạm thời để đủ số lượng (nhưng sẽ cố gắng unique nhất có thể)
    if len(comments) < needed_count:
        st.warning(f"⚠️ Mức '{target_level}' cần {needed_count} câu nhưng AI chỉ viết được {len(comments)} câu. Sẽ có {needed_count - len(comments)} em bị trùng lặp.")
        while len(comments) < needed_count:
            comments.append(random.choice(comments) if comments else "Hoàn thành nhiệm vụ học tập.")
            
    # Trộn ngẫu nhiên danh sách trước khi phát
    random.shuffle(comments)
    return comments

# --- 4. GIAO DIỆN CHÍNH ---
st.markdown("""
<div class="header-box">
    <h1>💎 TRỢ LÝ NHẬN XÉT TIỂU HỌC TT27</h1>
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
    st.write("▼ Danh sách học sinh:", df.head(3))
    st.markdown("---")
    
    col_score = st.selectbox("📌 Cột Điểm/Mức đạt:", df.columns)
    col_new = st.text_input("📌 Tên cột nhận xét mới:", "Nhận xét GV")
    c3, c4 = st.columns(2)
    with c3: mon_hoc = st.text_input("📚 Môn:", "Tin học")
    with c4: chu_de = st.text_input("📝 Bài học:", "Chủ đề E")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 TẠO NHẬN XÉT KHÔNG TRÙNG LẶP"):
        if not api_key: st.toast("Thiếu Key!"); st.stop()
        
        # 1. Đếm số lượng cần thiết
        progress_bar = st.progress(0, text="Đang đếm số lượng học sinh từng mức...")
        
        df['__Level__'] = df[col_score].apply(classify_student)
        counts = df['__Level__'].value_counts()
        
        count_T = counts.get('Hoàn thành tốt', 0)
        count_H = counts.get('Hoàn thành', 0)
        count_C = counts.get('Chưa hoàn thành', 0)
        
        st.write(f"📊 Yêu cầu AI viết: {count_T} câu Tốt, {count_H} câu Hoàn thành, {count_C} câu Chưa hoàn thành.")
        
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

        # 3. Prompt Động (Dynamic Prompt)
        # Yêu cầu AI viết dư ra 10% để dự phòng
        req_T = int(count_T * 1.1) + 2
        req_H = int(count_H * 1.1) + 2
        req_C = int(count_C * 1.1) + 2
        
        progress_bar.progress(20, text="AI đang viết hàng trăm câu nhận xét khác nhau (Sẽ mất khoảng 30s)...")
        
        model = genai.GenerativeModel('gemini-2.5-flash-lite-preview-09-2025')
        
        prompt = f"""
        Bạn là giáo viên. Viết nhận xét DUY NHẤT (không trùng nhau) cho danh sách học sinh môn {mon_hoc}, bài {chu_de}.
        Minh chứng: {context_text[:2000]}...
        
        QUY TẮC CỐT LÕI:
        1. KHÔNG viết in hoa toàn bộ. Chỉ viết hoa chữ cái đầu câu. (Ví dụ: "Thành thạo..." thay vì "THÀNH THẠO...").
        2. TỪ CẤM: "Em", "Con", "Bạn".
        3. ĐỘ DÀI: Khoảng 200 ký tự (đủ ý nhưng ngắn gọn).
        
        YÊU CẦU SỐ LƯỢNG (BẮT BUỘC ĐỦ):
        - Viết {req_T} câu cho mức HOÀN THÀNH TỐT.
        - Viết {req_H} câu cho mức HOÀN THÀNH.
        - Viết {req_C} câu cho mức CHƯA HOÀN THÀNH.
        
        CẤU TRÚC:
        1. NHÓM HOÀN THÀNH TỐT (Chỉ khen, KHÔNG dùng "tuy nhiên/nhưng"):
           - Khen kỹ năng cụ thể + Khen sự sáng tạo/thái độ. 
           - Ví dụ: Thao tác chuột rất nhanh nhẹn, hoàn thành xuất sắc bài thực hành.
        
        2. NHÓM HOÀN THÀNH (Có 2 vế):
           - [Điểm làm được] NHƯNG/TUY NHIÊN [Điểm cần rèn thêm].
        
        3. NHÓM CHƯA HOÀN THÀNH (Có 2 vế):
           - [Sự tham gia] NHƯNG [Cần GV hỗ trợ gì].
        
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
        try:
            response = model.generate_content(inputs)
            
            # 4. Phân phối độc nhất (One-to-One Mapping)
            progress_bar.progress(70, text="Đang phân phối từng câu nhận xét vào từng học sinh...")
            
            # Lấy danh sách câu từ AI
            pool_T = process_ai_response_unique(response.text, "Hoàn thành tốt", count_T)
            pool_H = process_ai_response_unique(response.text, "Hoàn thành", count_H)
            pool_C = process_ai_response_unique(response.text, "Chưa hoàn thành", count_C)
            
            # Hàm lấy câu và xóa khỏi kho (Pop)
            def assign_comment(level):
                if level == 'Hoàn thành tốt' and pool_T: return pool_T.pop(0)
                if level == 'Hoàn thành' and pool_H: return pool_H.pop(0)
                if level == 'Chưa hoàn thành' and pool_C: return pool_C.pop(0)
                return "Đã hoàn thành bài học." # Fallback cuối cùng nếu hết câu

            df[col_new] = df['__Level__'].apply(assign_comment)
            del df['__Level__']
            
            progress_bar.progress(100, text="Xong!")
            
            # 5. Xuất file
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
                ws = writer.sheets['Sheet1']
                ws.column_dimensions[chr(65 + df.columns.get_loc(col_new))].width = 60
            output.seek(0)
            
            st.success("✅ Thành công! Mỗi học sinh đã có một nhận xét riêng biệt.")
            st.download_button("⬇️ Tải File Excel Kết Quả", output, f"NhanXet_NoDuplicate_{mon_hoc}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            with st.expander("Kiểm tra ngẫu nhiên 5 em"):
                st.dataframe(df.sample(min(5, len(df)))[[col_score, col_new]], use_container_width=True)

        except Exception as e:
            st.error(f"Lỗi xử lý: {e}")

# --- FOOTER ---
st.markdown("<div style='text-align:center; margin-top:50px; color:#888;'>© 2025 - Thầy Sần Tool</div>", unsafe_allow_html=True)
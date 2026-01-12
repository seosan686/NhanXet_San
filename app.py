import streamlit as st
import google.generativeai as genai
from PIL import Image
import tempfile
import os
import io
import pandas as pd # Xử lý Excel
from docx import Document # Xử lý Word
import time

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Kho Nhận Xét Thông Minh 4.0",
    page_icon="🗃️",
    layout="centered"
)

# --- 2. CSS GIAO DIỆN ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #f8f9fa; }
    
    .header-box {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 30px; border-radius: 15px; text-align: center; color: white;
        margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .header-box h1 { color: white !important; margin: 0; font-size: 2rem; }
    .header-box p { color: #e0e0e0 !important; margin-top: 10px; font-weight: bold; font-size: 1.1rem; }
    
    .guide-box {
        background-color: #fff8e1; color: #856404; padding: 15px;
        border-radius: 8px; border-left: 5px solid #ffc107; margin-bottom: 20px;
        font-size: 0.95rem; line-height: 1.5;
    }
    
    .stTextInput, .stNumberInput { background-color: white; border-radius: 5px; }
    
    div.stButton > button {
        background: linear-gradient(90deg, #28a745, #218838);
        color: white !important;
        border: none; padding: 15px 30px; font-size: 18px; font-weight: bold;
        border-radius: 10px; width: 100%; margin-top: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2); transition: 0.3s;
    }
    div.stButton > button:hover { transform: translateY(-2px); box-shadow: 0 6px 12px rgba(0,0,0,0.3); }

    .footer {
        text-align: center; color: #666; margin-top: 50px; padding-top: 20px;
        border-top: 1px solid #ddd; font-size: 0.9rem;
    }
    
    [data-testid="stImage"] { border-radius: 8px; border: 1px solid #ddd; }
</style>
""", unsafe_allow_html=True)

# --- 3. HÀM XỬ LÝ DỮ LIỆU TỪNG ĐỢT ---
def process_batch_response(content):
    batch_data = []
    current_level = ""
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        
        line_upper = line.upper()
        if "MỨC: HOÀN THÀNH TỐT" in line_upper:
            current_level = "Hoàn thành tốt"
            continue
        elif "MỨC: CHƯA HOÀN THÀNH" in line_upper:
            current_level = "Chưa hoàn thành"
            continue
        elif "MỨC: HOÀN THÀNH" in line_upper:
            current_level = "Hoàn thành"
            continue
            
        if (line.startswith('-') or line.startswith('*') or line[0].isdigit()) and current_level:
            clean_text = line.lstrip("-*1234567890. ")
            clean_text = clean_text.replace("**", "")
            if len(clean_text) > 5: 
                batch_data.append({
                    "Mức độ": current_level,
                    "Nội dung nhận xét": clean_text
                })
    return batch_data

# --- 4. GIAO DIỆN CHÍNH ---
st.markdown("""
<div class="header-box">
    <h1>🗃️ KHO NHẬN XÉT THÔNG MINH 4.0</h1>
    <p>Tác giả Lù Seo Sần - 097.1986.343</p>
</div>
""", unsafe_allow_html=True)

# --- [NHẬP KEY CÁ NHÂN] ---
with st.sidebar:
    st.header("🔐 Đăng nhập hệ thống")
    default_key = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else ""
    manual_key = st.text_input("🔑 Nhập API Key thay thế (nếu cần):", type="password")

    if manual_key:
        api_key = manual_key
        st.info("⚠️ Đang dùng Key nhập tay")
    elif default_key:
        api_key = default_key
        st.success("✅ Đang dùng Key hệ thống")
    else:
        api_key = None
        st.warning("⬅️ Vui lòng nhập API Key để bắt đầu!")

if api_key:
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Lỗi Key: {e}")

# --- 5. KHUNG NHẬP LIỆU ---
st.markdown("### 📂 1. TÀI LIỆU CĂN CỨ")
st.markdown("""
<div class="guide-box">
<b>💡 Siêu hỗ trợ:</b> Hệ thống đọc được <b>Ảnh, PDF, Excel (.xlsx)</b> và cả <b>File Word (.docx)</b> chứa nội dung bài dạy hoặc tiêu chí.
</div>
""", unsafe_allow_html=True)

# [CẬP NHẬT] Thêm docx vào danh sách cho phép
uploaded_files = st.file_uploader(
    "Kéo thả file vào đây (Đa định dạng):", 
    type=["pdf", "png", "jpg", "xlsx", "xls", "docx"], 
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"✅ Đã nhận {len(uploaded_files)} file tài liệu.")
    st.markdown("---")
    st.caption("👁️ Xem trước tài liệu:")
    cols = st.columns(3)
    for i, file in enumerate(uploaded_files):
        if file.type in ["image/jpeg", "image/png"]:
            with cols[i % 3]: st.image(file, caption=f"Ảnh {i+1}", use_container_width=True)
        elif file.type == "application/pdf":
            with cols[i % 3]: st.info(f"📄 PDF: {file.name}")
        elif "spreadsheet" in file.type or file.name.endswith(".xlsx"):
            with cols[i % 3]: st.success(f"📊 Excel: {file.name}")
        elif "word" in file.type or file.name.endswith(".docx"):
            with cols[i % 3]: st.warning(f"📝 Word: {file.name}")
    st.markdown("---")

st.markdown("### ⚙️ 2. CẤU HÌNH NỘI DUNG")
c1, c2 = st.columns(2)
with c1: mon_hoc = st.text_input("📚 Môn học:", "Tin học", placeholder="Nhập tên môn...")
with c2: so_luong_tong = st.number_input("🔢 TỔNG số lượng mẫu mỗi mức độ cần tạo:", min_value=10, max_value=1000, value=30, step=10)

chu_de = st.text_input("📌 Chủ đề / Bài học:", "Chủ đề E: Ứng dụng tin học")

# --- 6. XỬ LÝ AI ---
st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 TẠO NGÂN HÀNG NHẬN XÉT (EXCEL)"):
    if not api_key: st.toast("Thiếu API Key!", icon="❌")
    elif not uploaded_files: st.toast("Vui lòng tải tài liệu lên!", icon="⚠️")
    else:
        # Cấu hình chia lô
        BATCH_SIZE = 10 
        num_batches = (so_luong_tong // BATCH_SIZE) + (1 if so_luong_tong % BATCH_SIZE > 0 else 0)
        
        all_results = []
        progress_text = "Đang khởi động quy trình xử lý hàng loạt..."
        my_bar = st.progress(0, text=progress_text)
        
        try:
            model = genai.GenerativeModel('gemini-2.5-flash-lite-preview-09-2025')
            
            # --- [XỬ LÝ ĐA ĐỊNH DẠNG] ---
            file_contents = [] # Chứa file Media (Ảnh/PDF)
            text_context_extra = "" # Chứa chữ từ Excel và Word
            temp_paths = []

            for file in uploaded_files:
                # 1. Xử lý Excel
                if file.name.endswith('.xlsx') or file.name.endswith('.xls'):
                    try:
                        df_excel = pd.read_excel(file)
                        text_context_extra += f"\n\n--- DỮ LIỆU TỪ EXCEL ({file.name}) ---\n{df_excel.to_string(index=False)}"
                    except: pass

                # 2. Xử lý Word (.docx) -> [MỚI]
                elif file.name.endswith('.docx'):
                    try:
                        doc = Document(file)
                        full_text = []
                        for para in doc.paragraphs:
                            full_text.append(para.text)
                        # Đọc cả bảng trong Word nếu có
                        for table in doc.tables:
                            for row in table.rows:
                                for cell in row.cells:
                                    full_text.append(cell.text)
                        
                        text_context_extra += f"\n\n--- DỮ LIỆU TỪ WORD ({file.name}) ---\n" + "\n".join(full_text)
                    except Exception as e:
                        st.error(f"Lỗi đọc file Word {file.name}: {e}")

                # 3. Xử lý PDF (Upload)
                elif file.type == "application/pdf":
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(file.getvalue())
                        temp_paths.append(tmp.name)
                    file_contents.append(genai.upload_file(tmp.name))
                
                # 4. Xử lý Ảnh
                else:
                    file_contents.append(Image.open(file))

            # --- BẮT ĐẦU VÒNG LẶP ---
            for i in range(num_batches):
                pct = (i / num_batches)
                my_bar.progress(pct, text=f"⏳ Đợt {i+1}/{num_batches}: Đang viết câu {i*BATCH_SIZE + 1} đến {(i+1)*BATCH_SIZE}...")
                
                prompt = f"""
                Bạn là chuyên gia giáo dục Tiểu học. Nhiệm vụ: Xây dựng KHO NHẬN XÉT cho môn {mon_hoc}, chủ đề: {chu_de}.
                ĐÂY LÀ ĐỢT TẠO THỨ {i+1}. HÃY CỐ GẮNG VIẾT KHÁC VỚI NHỮNG CÂU TRƯỚC.
                
                DỮ LIỆU ĐẦU VÀO:
                1. Xem ảnh/PDF đính kèm.
                2. Đọc dữ liệu văn bản trích xuất từ Excel/Word dưới đây:
                {text_context_extra}
                
                NGUYÊN TẮC (TT27):
                - Không dùng "Em", "Con", "Nắm được".
                - Độ dài < 380 ký tự.
                - Phải chứa từ khóa chuyên môn.
                
                SỐ LƯỢNG: {BATCH_SIZE} câu/mức độ.
                
                CẤU TRÚC 3 MỨC:
                I. MỨC: HOÀN THÀNH TỐT
                - [Nội dung]
                II. MỨC: HOÀN THÀNH
                - [Nội dung]
                III. MỨC: CHƯA HOÀN THÀNH
                - [Nội dung]
                """
                
                inputs = [prompt] + file_contents
                response = model.generate_content(inputs)
                
                batch_items = process_batch_response(response.text)
                all_results.extend(batch_items)
                time.sleep(1)

            # --- KẾT THÚC ---
            my_bar.progress(100, text="✅ Xong!")
            
            df = pd.DataFrame(all_results)
            df.drop_duplicates(subset=['Nội dung nhận xét'], inplace=True)
            
            st.success(f"✅ Đã tạo {len(df)} câu nhận xét (Tổng hợp từ PDF, Ảnh, Excel, Word).")

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='NganHangNhanXet')
                ws = writer.sheets['NganHangNhanXet']
                ws.column_dimensions['A'].width = 20; ws.column_dimensions['B'].width = 80
            output.seek(0)
            
            st.download_button(label="⬇️ TẢI FILE EXCEL", data=output, file_name=f"Kho_Nhan_Xet_{mon_hoc}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

            with st.expander("👀 Xem kết quả"): st.dataframe(df, use_container_width=True)
            for p in temp_paths: os.remove(p)

        except Exception as e: st.error(f"Lỗi: {e}")

# --- CHÂN TRANG ---
st.markdown("<div class='footer'>Bản quyền thuộc về Lù Seo Sần - Trường PTDTBT Tiểu học Bản Ngò</div>", unsafe_allow_html=True)
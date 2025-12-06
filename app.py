import streamlit as st
import google.generativeai as genai
from PIL import Image
import tempfile
import os
import io
import pandas as pd # Thư viện xử lý Excel
import time # Thư viện thời gian

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Kho Nhận Xét Thông Minh TT27",
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
            if len(clean_text) > 5: # Chỉ lấy câu có nội dung, bỏ câu rác
                batch_data.append({
                    "Mức độ": current_level,
                    "Nội dung nhận xét": clean_text
                })
    return batch_data

# --- 4. GIAO DIỆN CHÍNH ---
st.markdown("""
<div class="header-box">
    <h1>🗃️ TRỢ LÝ TẠO KHO NHẬN XÉT (TT27)</h1>
    <p>Tác giả Lù Seo Sần - 097.1986.343</p>
</div>
""", unsafe_allow_html=True)

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    with st.sidebar:
        st.header("🔐 Cấu hình")
        api_key = st.text_input("🔑 API Key:", type="password")

if api_key:
    genai.configure(api_key=api_key)

# --- 5. KHUNG NHẬP LIỆU ---

st.markdown("### 📂 1. TÀI LIỆU CĂN CỨ")
st.markdown("""
<div class="guide-box">
<b>💡 Cơ chế mới:</b> Hệ thống sẽ tự động chạy nhiều lần để đảm bảo đủ số lượng câu thầy yêu cầu.
</div>
""", unsafe_allow_html=True)

uploaded_files = st.file_uploader("Kéo thả file vào đây (PDF/Ảnh):", type=["pdf", "png", "jpg"], accept_multiple_files=True)

if uploaded_files:
    st.success(f"✅ Đã nhận {len(uploaded_files)} file tài liệu.")
    st.markdown("---")
    st.caption("👁️ Xem trước tài liệu (Thumbnails):")
    cols = st.columns(3)
    for i, file in enumerate(uploaded_files):
        if file.type in ["image/jpeg", "image/png"]:
            with cols[i % 3]: st.image(file, caption=f"Ảnh {i+1}", use_container_width=True)
        elif file.type == "application/pdf":
            with cols[i % 3]: st.info(f"📄 PDF: {file.name}")
    st.markdown("---")

st.markdown("### ⚙️ 2. CẤU HÌNH NỘI DUNG")
c1, c2 = st.columns(2)
with c1: mon_hoc = st.text_input("📚 Môn học:", "Tin học", placeholder="Nhập tên môn...")
with c2: so_luong_tong = st.number_input("🔢 TỔNG số lượng mẫu mỗi mức độ cần tạo:", min_value=10, max_value=1000, value=30, step=10)

chu_de = st.text_input("📌 Chủ đề / Bài học:", "Chủ đề E: Ứng dụng tin học")

# --- 6. XỬ LÝ AI (LOGIC VÒNG LẶP) ---
st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 TẠO NGÂN HÀNG NHẬN XÉT (EXCEL)"):
    if not api_key: st.toast("Thiếu API Key!", icon="❌")
    elif not uploaded_files: st.toast("Vui lòng tải tài liệu lên!", icon="⚠️")
    else:
        # Cấu hình chia lô
        BATCH_SIZE = 10 # Mỗi lần chỉ xin AI 10 câu cho mỗi mức độ để nó làm cho chuẩn
        num_batches = (so_luong_tong // BATCH_SIZE) + (1 if so_luong_tong % BATCH_SIZE > 0 else 0)
        
        all_results = [] # Nơi chứa toàn bộ kết quả gộp lại
        
        progress_text = "Đang khởi động quy trình xử lý hàng loạt..."
        my_bar = st.progress(0, text=progress_text)
        
        try:
            model = genai.GenerativeModel('gemini-2.5-flash-lite-preview-09-2025')
            
            # Xử lý file upload một lần
            file_contents = []
            temp_paths = []
            for file in uploaded_files:
                if file.type == "application/pdf":
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(file.getvalue())
                        temp_paths.append(tmp.name)
                    file_contents.append(genai.upload_file(tmp.name))
                else:
                    file_contents.append(Image.open(file))

            # BẮT ĐẦU VÒNG LẶP (LOOP)
            for i in range(num_batches):
                current_progress = (i / num_batches)
                my_bar.progress(current_progress, text=f"⏳ Đang chạy đợt {i+1}/{num_batches} (Đang viết câu {i*BATCH_SIZE + 1} đến {(i+1)*BATCH_SIZE})...")
                
                # Prompt yêu cầu AI sáng tạo khác đi mỗi lần
                prompt = f"""
                Bạn là chuyên gia giáo dục Tiểu học. Nhiệm vụ: Xây dựng KHO NHẬN XÉT cho môn {mon_hoc}, chủ đề: {chu_de}.
                ĐÂY LÀ ĐỢT TẠO THỨ {i+1}. HÃY CỐ GẮNG VIẾT KHÁC VỚI NHỮNG CÂU THÔNG THƯỜNG.
                
                NGUYÊN TẮC CỐT LÕI:
                1. Căn cứ: Bám sát tài liệu đính kèm, Chương trình GDPT 2018, Thông tư 27.
                2. TỪ CẤM: "Em", "Con", "Nắm được".
                3. Độ dài: < 380 ký tự.
                4. Nội dung: Phải chứa từ khóa chuyên môn trong tài liệu.
                
                SỐ LƯỢNG YÊU CẦU ĐỢT NÀY: {BATCH_SIZE} câu cho MỖI mức độ.
                
                CẤU TRÚC BẮT BUỘC 3 MỨC ĐỘ:
                1. MỨC: HOÀN THÀNH TỐT (T)
                - Khen ngợi thành thạo kỹ năng, sáng tạo.
                2. MỨC: HOÀN THÀNH (H)
                - [Những yêu cầu đã làm được], [Những yêu cầu cần cố gắng].
                3. MỨC: CHƯA HOÀN THÀNH (C)
                - [Những điểm đã tham gia/làm được], [Những yêu cầu cần cố gắng].
                
                ĐẦU RA (Định dạng để máy đọc):
                I. MỨC: HOÀN THÀNH TỐT
                - [Câu 1]
                ...
                II. MỨC: HOÀN THÀNH
                ...
                III. MỨC: CHƯA HOÀN THÀNH
                ...
                """
                
                inputs = [prompt] + file_contents
                response = model.generate_content(inputs)
                
                # Phân tích kết quả đợt này và gộp vào kho chung
                batch_items = process_batch_response(response.text)
                all_results.extend(batch_items)
                
                # Nghỉ 1 chút để không bị Google chặn spam
                time.sleep(1)

            # KẾT THÚC VÒNG LẶP
            my_bar.progress(100, text="✅ Đã hoàn tất xử lý!")
            
            # TẠO FILE EXCEL TỔNG HỢP
            df = pd.DataFrame(all_results)
            
            # Lọc trùng lặp (nếu AI lỡ viết câu giống nhau)
            df.drop_duplicates(subset=['Nội dung nhận xét'], inplace=True)
            
            st.success(f"✅ Đã tạo thành công {len(df)} câu nhận xét (Đã tự động lọc bỏ câu trùng).")

            # Xuất Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='NganHangNhanXet')
                worksheet = writer.sheets['NganHangNhanXet']
                worksheet.column_dimensions['A'].width = 20
                worksheet.column_dimensions['B'].width = 80
            output.seek(0)
            
            st.download_button(
                label=f"⬇️ TẢI FILE EXCEL TỔNG HỢP ({len(df)} CÂU)",
                data=output,
                file_name=f"Kho_Nhan_Xet_{mon_hoc}_TongHop.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

            with st.expander("👀 Xem trước dữ liệu tổng hợp"):
                 st.dataframe(df, use_container_width=True)
            
            # Dọn dẹp
            for p in temp_paths: os.remove(p)

        except Exception as e:
            st.error(f"Lỗi: {e}")

# --- CHÂN TRANG ---
st.markdown("""
<div class="footer">
    Bản quyền thuộc về Lù Seo Sần - Trường PTDTBT Tiểu học Bản Ngò
</div>
""", unsafe_allow_html=True)

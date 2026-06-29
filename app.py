import streamlit as st
import pandas as pd
import re
import io
import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from pypdf import PdfReader
from docx import Document
from fpdf import FPDF

# 1. Konfigurasi Halaman Streamlit (Favicon dari CDN)
st.set_page_config(
    page_title="Forensic Metadata Harvester & Reporter",
    page_icon="https://cdn-icons-png.flaticon.com/512/2912/2912770.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Kustomisasi CSS & Font Plus Jakarta Sans + Bootstrap Icons
st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    /* Font Global */
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
    /* Judul Utama dengan Gradient Kontras Tinggi */
    .main-title {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 800;
        font-size: 40px;
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 50%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
        letter-spacing: -1px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .sub-title {
        font-size: 15px;
        color: var(--text-color);
        opacity: 0.7;
        margin-bottom: 30px;
        font-weight: 400;
    }
    
    /* Kartu UI Custom yang Beradaptasi dengan Tema Gelap & Terang */
    .custom-card {
        background: var(--secondary-background-color);
        padding: 20px;
        border-radius: 14px;
        box-shadow: 0 4px 15px -3px rgba(0, 0, 0, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.15);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        margin-bottom: 15px;
    }
    
    .custom-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 25px -5px rgba(37, 99, 235, 0.2);
        border-color: #3b82f6;
    }
    
    .card-icon {
        font-size: 26px;
        margin-bottom: 10px;
    }
    
    .card-title {
        font-size: 13px;
        color: var(--text-color);
        opacity: 0.6;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .card-value {
        font-size: 22px;
        color: var(--text-color);
        font-weight: 700;
        margin-top: 5px;
        word-wrap: break-word;
    }
    
    /* Lencana Status Forensik (Bespoke Badges - Kontras Tinggi di Gelap & Terang) */
    .custom-badge {
        padding: 6px 14px;
        border-radius: 50px;
        font-size: 13px;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin-top: 10px;
        margin-bottom: 10px;
    }
    
    .badge-success {
        background-color: rgba(16, 185, 129, 0.1);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .badge-warning {
        background-color: rgba(245, 158, 11, 0.1);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    /* Sub-header Kustom */
    .custom-section-header {
        font-size: 18px;
        font-weight: 700;
        color: var(--text-color);
        margin-top: 10px;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
</style>
""", unsafe_allow_html=True)

# 2. Fungsi Pembantu: Parsing GPS Koordinat dari EXIF
def get_decimal_from_dms(dms, ref):
    try:
        degrees = float(dms[0])
        minutes = float(dms[1])
        seconds = float(dms[2])
    except (TypeError, ZeroDivisionError, IndexError):
        return None
        
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ['S', 'W']:
        decimal = -decimal
    return decimal

def parse_gps(gps_info):
    if not gps_info:
        return None
        
    resolved_gps = {}
    for k, v in gps_info.items():
        tag_name = GPSTAGS.get(k, k)
        resolved_gps[tag_name] = v
        
    lat_ref = resolved_gps.get('GPSLatitudeRef')
    lat_dms = resolved_gps.get('GPSLatitude')
    lon_ref = resolved_gps.get('GPSLongitudeRef')
    lon_dms = resolved_gps.get('GPSLongitude')
    
    if lat_ref and lat_dms and lon_ref and lon_dms:
        lat = get_decimal_from_dms(lat_dms, lat_ref)
        lon = get_decimal_from_dms(lon_dms, lon_ref)
        if lat is not None and lon is not None:
            return {"latitude": lat, "longitude": lon}
            
    return None

# 3. Fungsi Pembantu: Parsing Format Tanggal PDF
def parse_pdf_date(date_str):
    if not date_str:
        return 'N/A'
    match = re.search(r'(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?', date_str)
    if match:
        parts = match.groups()
        year, month, day = parts[0], parts[1], parts[2]
        time_str = ""
        if parts[3] and parts[4]:
            sec = parts[5] if parts[5] else "00"
            time_str = f" {parts[3]}:{parts[4]}:{sec}"
        return f"{day}/{month}/{year}{time_str}"
    return date_str

# 4. Fungsi Ekstraksi Metadata untuk Masing-masing Format
def extract_image_metadata(file_name, file_bytes):
    try:
        img = Image.open(io.BytesIO(file_bytes))
        basic = {
            "Format": img.format,
            "Lebar x Tinggi (Pixel)": f"{img.width} x {img.height}",
            "Mode Warna": img.mode
        }
        
        exif_data = img._getexif()
        exif_info = {}
        gps_raw = {}
        
        if exif_data:
            for tag, value in exif_data.items():
                tag_name = TAGS.get(tag, tag)
                if tag_name == "GPSInfo":
                    gps_raw = value
                else:
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8', errors='ignore')
                        except:
                            value = str(value)
                    exif_info[tag_name] = value
                    
        # Ambil tanggal pengambilan
        date_taken = exif_info.get("DateTimeOriginal") or exif_info.get("DateTime") or "N/A"
        if date_taken != "N/A":
            try:
                dt_obj = datetime.datetime.strptime(date_taken, "%Y:%m:%d %H:%M:%S")
                date_taken = dt_obj.strftime("%d/%m/%Y %H:%M:%S")
            except:
                pass
        basic["Tanggal Pengambilan"] = date_taken
        basic["Merek Kamera"] = exif_info.get("Make", "N/A")
        basic["Model HP/Kamera"] = exif_info.get("Model", "N/A")
        basic["Software Editor"] = exif_info.get("Software", "N/A")
        
        gps_parsed = parse_gps(gps_raw)
        
        return {
            "name": file_name,
            "type": "Gambar",
            "size_kb": len(file_bytes) / 1024.0,
            "metadata": basic,
            "exif_raw": exif_info,
            "gps": gps_parsed,
            "error": None
        }
    except Exception as e:
        return {
            "name": file_name,
            "type": "Gambar",
            "size_kb": len(file_bytes) / 1024.0,
            "error": str(e)
        }

def extract_pdf_metadata(file_name, file_bytes):
    try:
        pdf = PdfReader(io.BytesIO(file_bytes))
        meta = pdf.metadata
        
        basic = {}
        if meta:
            basic["Judul (Title)"] = meta.title or "N/A"
            basic["Penulis (Author)"] = meta.author or "N/A"
            basic["Aplikasi Pembuat (Creator)"] = meta.creator or "N/A"
            basic["Aplikasi Produser (Producer)"] = meta.producer or "N/A"
            basic["Tanggal Dibuat"] = parse_pdf_date(meta.get('/CreationDate'))
            basic["Tanggal Diubah"] = parse_pdf_date(meta.get('/ModDate'))
        else:
            basic = {
                "Judul (Title)": "N/A",
                "Penulis (Author)": "N/A",
                "Aplikasi Pembuat (Creator)": "N/A",
                "Aplikasi Produser (Producer)": "N/A",
                "Tanggal Dibuat": "N/A",
                "Tanggal Diubah": "N/A"
            }
            
        basic["Jumlah Halaman"] = str(len(pdf.pages))
        
        return {
            "name": file_name,
            "type": "PDF",
            "size_kb": len(file_bytes) / 1024.0,
            "metadata": basic,
            "gps": None,
            "error": None
        }
    except Exception as e:
        return {
            "name": file_name,
            "type": "PDF",
            "size_kb": len(file_bytes) / 1024.0,
            "error": str(e)
        }

def extract_docx_metadata(file_name, file_bytes):
    try:
        doc = Document(io.BytesIO(file_bytes))
        props = doc.core_properties
        
        basic = {
            "Judul (Title)": props.title or "N/A",
            "Penulis (Author)": props.author or "N/A",
            "Terakhir Diubah Oleh": props.last_modified_by or "N/A",
            "Tanggal Dibuat": props.created.strftime("%d/%m/%Y %H:%M:%S") if props.created else "N/A",
            "Tanggal Diubah": props.modified.strftime("%d/%m/%Y %H:%M:%S") if props.modified else "N/A",
            "Revisi Ke": str(props.revision) if props.revision else "1",
            "Komentar": props.comments or "N/A"
        }
        
        return {
            "name": file_name,
            "type": "Word (DOCX)",
            "size_kb": len(file_bytes) / 1024.0,
            "metadata": basic,
            "gps": None,
            "error": None
        }
    except Exception as e:
        return {
            "name": file_name,
            "type": "Word (DOCX)",
            "size_kb": len(file_bytes) / 1024.0,
            "error": str(e)
        }

# 5. Class Generator PDF Laporan Forensik Resmi
class ForensicPDFReport(FPDF):
    def __init__(self, case_id, investigator, institution, case_date):
        super().__init__()
        self.case_id = case_id
        self.investigator = investigator
        self.institution = institution
        self.case_date = case_date
        
    def header(self):
        self.set_font('helvetica', 'B', 14)
        self.cell(0, 10, 'LAPORAN ANALISIS METADATA FORENSIK DIGITAL', 0, 1, 'C')
        self.set_font('helvetica', '', 9)
        self.cell(0, 5, 'Dihasilkan oleh: Forensic Metadata Harvester & Reporter', 0, 1, 'C')
        self.ln(5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)
        
    def footer(self):
        self.set_y(-25)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 5, f'Halaman {self.page_no()} | ID Laporan Barang Bukti: {self.case_id}', 0, 0, 'C')

def generate_pdf_report(case_info, file_results):
    pdf = ForensicPDFReport(
        case_id=case_info["case_id"],
        investigator=case_info["investigator"],
        institution=case_info["institution"],
        case_date=case_info["case_date"]
    )
    pdf.add_page()
    pdf.set_font('helvetica', '', 10)
    
    # Bagian 1: Informasi Kasus
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 7, 'I. INFORMASI KASUS & INVESTIGASI', 0, 1)
    pdf.set_font('helvetica', '', 10)
    pdf.cell(50, 6, 'ID Laporan:', 0, 0)
    pdf.cell(0, 6, case_info["case_id"], 0, 1)
    pdf.cell(50, 6, 'Pemeriksa (Investigator):', 0, 0)
    pdf.cell(0, 6, case_info["investigator"], 0, 1)
    pdf.cell(50, 6, 'Institusi/Lembaga:', 0, 0)
    pdf.cell(0, 6, case_info["institution"], 0, 1)
    pdf.cell(50, 6, 'Tanggal Analisis:', 0, 0)
    pdf.cell(0, 6, case_info["case_date"], 0, 1)
    pdf.ln(5)
    
    # Bagian 2: Ringkasan Bukti
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 7, 'II. RINGKASAN BARANG BUKTI', 0, 1)
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 6, f'Total barang bukti yang diperiksa secara forensik: {len(file_results)} file.', 0, 1)
    pdf.ln(5)
    
    # Bagian 3: Detail Forensik Tiap File
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 7, 'III. HASIL ANALISIS METADATA BUKTI', 0, 1)
    pdf.ln(2)
    
    for idx, res in enumerate(file_results):
        pdf.set_font('helvetica', 'B', 10)
        pdf.cell(0, 6, f'Barang Bukti #{idx+1}: {res["name"]} [{res["type"]}]', 0, 1)
        pdf.set_font('helvetica', '', 9)
        pdf.cell(50, 5, 'Ukuran File:', 0, 0)
        pdf.cell(0, 5, f'{res["size_kb"]:.2f} KB', 0, 1)
        
        if res.get("error"):
            pdf.set_text_color(220, 53, 69)
            pdf.cell(0, 5, f'Error Ekstraksi: {res["error"]}', 0, 1)
            pdf.set_text_color(0, 0, 0)
        else:
            for key, val in res["metadata"].items():
                pdf.cell(50, 5, f'{key}:', 0, 0)
                pdf.cell(0, 5, str(val), 0, 1)
                
            if res.get("gps"):
                pdf.cell(50, 5, 'Koordinat Lokasi (GPS):', 0, 0)
                pdf.cell(0, 5, f"Latitude: {res['gps']['latitude']}, Longitude: {res['gps']['longitude']}", 0, 1)
                
        pdf.ln(4)
        
    # Bagian 4: Pernyataan Integritas & Tanda Tangan
    pdf.ln(10)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 7, 'IV. PERNYATAAN INTEGRITAS DATA', 0, 1)
    pdf.set_font('helvetica', '', 9)
    pdf.multi_cell(0, 5, 'Seluruh informasi metadata dalam laporan ini diekstrak langsung secara biner dari data asli barang bukti digital yang diunggah oleh investigator tanpa manipulasi data. Hasil ekstraksi mencerminkan data asli saat barang bukti diperiksa.')
    pdf.ln(10)
    
    if pdf.get_y() > 220:
        pdf.add_page()
        
    current_y = pdf.get_y()
    pdf.set_xy(125, current_y)
    pdf.cell(0, 5, 'Penyelidik (Investigator),', 0, 1, 'C')
    pdf.ln(15)
    pdf.set_xy(125, pdf.get_y())
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 5, case_info["investigator"], 0, 1, 'C')
    pdf.set_xy(125, pdf.get_y())
    pdf.set_font('helvetica', '', 9)
    pdf.cell(0, 5, case_info["institution"], 0, 1, 'C')
    
    return bytes(pdf.output())

# 6. Generator ID Laporan (Session State di Background)
if "case_id" not in st.session_state:
    import random
    st.session_state.case_id = f"CASE-{random.randint(10000, 99999)}"

case_id = st.session_state.case_id

# Sidebar Informasi Investigasi (Nama, Asal/Institusi, Tanggal)
st.sidebar.title(":material/folder_open: Informasi Investigasi")
investigator = st.sidebar.text_input("Nama Penyelidik / Investigator:", value="M. Fahrul Alfanani")
institution = st.sidebar.text_input("Asal / Universitas:", value="Informatika - Universitas Nahdlatul Ulama Sidoarjo")
case_date = st.sidebar.date_input("Tanggal Analisis:", datetime.date.today(), format="DD/MM/YYYY").strftime("%d/%m/%Y")

st.sidebar.markdown("---")
st.sidebar.markdown("""
Informasi Alat:
Alat ini mem-parsing metadata tersembunyi seperti EXIF foto, detail XML dokumen PDF, dan properti inti file DOCX.
""")

# Judul Utama Dashboard (Menggunakan CSS Gradient & Bootstrap Icons)
st.markdown('<div class="main-title"><i class="bi bi-search"></i> Forensic Metadata Harvester & Reporter</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Ekstraksi biner metadata tersembunyi dokumen/gambar dan ekspor Laporan Bukti Forensik resmi untuk sidang hukum.</div>', unsafe_allow_html=True)

# File Upload Section (Label Diganti dengan Header Kustom)
st.markdown('<div class="custom-section-header"><i class="bi bi-cloud-arrow-up-fill" style="color:#2563eb;"></i> Unggah Barang Bukti Digital Anda</div>', unsafe_allow_html=True)
uploaded_files = st.file_uploader(
    "Mendukung format gambar (JPG/PNG) dan dokumen (PDF/DOCX):",
    type=["jpg", "jpeg", "png", "pdf", "docx"],
    accept_multiple_files=True,
    label_visibility="collapsed"
)

if uploaded_files:
    file_results = []
    
    # Ekstrak data biner file secara otomatis setelah diunggah
    for u_file in uploaded_files:
        file_bytes = u_file.getvalue()
        file_name = u_file.name
        
        if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
            result = extract_image_metadata(file_name, file_bytes)
        elif file_name.lower().endswith('.pdf'):
            result = extract_pdf_metadata(file_name, file_bytes)
        elif file_name.lower().endswith('.docx'):
            result = extract_docx_metadata(file_name, file_bytes)
        else:
            result = {"name": file_name, "type": "Tidak Dikenal", "size_kb": len(file_bytes)/1024.0, "error": "Format file tidak didukung."}
            
        file_results.append(result)
        
    # Tab Tampilan Hasil
    tab_summary, tab_details, tab_map = st.tabs([
        ":material/description: Ringkasan Temuan Kasus",
        ":material/analytics: Detail Analisis Bukti",
        ":material/map: Peta Lokasi (GPS Geotag)"
    ])
    
    # TAB 1: Ringkasan Temuan Kasus (Desain Baru Kartu Visual)
    with tab_summary:
        st.markdown('<div class="custom-section-header"><i class="bi bi-person-badge-fill" style="color:#4f46e5;"></i> Data Investigator & Kasus</div>', unsafe_allow_html=True)
        
        col_case1, col_case2, col_case3 = st.columns(3)
        with col_case1:
            st.markdown(f"""
            <div class="custom-card">
                <div class="card-icon" style="color: #4f46e5;"><i class="bi bi-person-badge"></i></div>
                <div class="card-title">Investigator</div>
                <div class="card-value">{investigator}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_case2:
            st.markdown(f"""
            <div class="custom-card">
                <div class="card-icon" style="color: #0891b2;"><i class="bi bi-bank"></i></div>
                <div class="card-title">Asal / Universitas</div>
                <div class="card-value" style="font-size: 16px; line-height: 1.3;">{institution}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_case3:
            st.markdown(f"""
            <div class="custom-card">
                <div class="card-icon" style="color: #db2777;"><i class="bi bi-calendar3"></i></div>
                <div class="card-title">Tanggal Analisis</div>
                <div class="card-value">{case_date}</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown('<div class="custom-section-header"><i class="bi bi-bar-chart-fill" style="color:#10b981;"></i> Statistik Barang Bukti</div>', unsafe_allow_html=True)
        
        total_files = len(file_results)
        img_count = sum(1 for r in file_results if r["type"] == "Gambar")
        doc_count = sum(1 for r in file_results if r["type"] in ["PDF", "Word (DOCX)"])
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.markdown(f"""
            <div class="custom-card">
                <div class="card-icon" style="color: #10b981;"><i class="bi bi-folder2-open"></i></div>
                <div class="card-title">Total Barang Bukti</div>
                <div class="card-value">{total_files} File</div>
            </div>
            """, unsafe_allow_html=True)
        with col_stat2:
            st.markdown(f"""
            <div class="custom-card">
                <div class="card-icon" style="color: #f59e0b;"><i class="bi bi-image"></i></div>
                <div class="card-title">Bukti Gambar (Foto)</div>
                <div class="card-value">{img_count} Gambar</div>
            </div>
            """, unsafe_allow_html=True)
        with col_stat3:
            st.markdown(f"""
            <div class="custom-card">
                <div class="card-icon" style="color: #6366f1;"><i class="bi bi-file-earmark-text"></i></div>
                <div class="card-title">Bukti Dokumen</div>
                <div class="card-value">{doc_count} Dokumen</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown('<div class="custom-section-header"><i class="bi bi-file-earmark-pdf-fill" style="color:#ef4444;"></i> Aksi Eksportir Laporan</div>', unsafe_allow_html=True)
        st.markdown("Hasilkan laporan digital forensik resmi dalam format PDF yang siap dicetak untuk kebutuhan sidang hukum:")
        
        case_info = {
            "case_id": case_id,
            "investigator": investigator,
            "institution": institution,
            "case_date": case_date
        }
        
        # Inisialisasi state untuk kesiapan PDF
        if "pdf_ready" not in st.session_state:
            st.session_state.pdf_ready = False
            
        # Reset kesiapan PDF jika isi bukti atau informasi investigasi berubah
        file_hash_keys = (tuple([f.name for f in uploaded_files]), investigator, institution, case_date)
        if "last_hash_keys" not in st.session_state:
            st.session_state.last_hash_keys = None
            
        if st.session_state.last_hash_keys != file_hash_keys:
            st.session_state.pdf_ready = False
            st.session_state.last_hash_keys = file_hash_keys
            
        if not st.session_state.pdf_ready:
            st.markdown("Klik tombol di bawah ini untuk memproses pembuatan file Laporan PDF:")
            if st.button("Generate Laporan PDF", type="secondary"):
                st.session_state.pdf_ready = True
                st.rerun()
        else:
            with st.spinner("Sedang menyusun file PDF biner..."):
                pdf_bytes = generate_pdf_report(case_info, file_results)
                
            st.markdown("""
            <div class="custom-badge badge-success">
                <i class="bi bi-check-circle-fill"></i> File Laporan PDF Berhasil Disusun!
            </div>
            """, unsafe_allow_html=True)
            st.write("")
            st.download_button(
                label="Unduh Laporan PDF Resmi",
                data=pdf_bytes,
                file_name=f"Laporan_Forensik_{case_id}.pdf",
                mime="application/pdf",
                type="primary"
            )
        
    # TAB 2: Detail Analisis Bukti (Desain Badge Forensik Baru)
    with tab_details:
        st.markdown('<div class="custom-section-header"><i class="bi bi-clipboard-data-fill" style="color:#4f46e5;"></i> Analisis Biner Berkas Bukti</div>', unsafe_allow_html=True)
        st.markdown("Pilih dan tinjau setiap bukti untuk melihat metadata asli yang tersembunyi:")
        
        for idx, res in enumerate(file_results):
            with st.expander(f":material/draft: Bukti #{idx+1}: {res['name']} ({res['type']})"):
                st.markdown(f"**Ukuran File:** {res['size_kb']:.2f} KB")
                
                if res.get("error"):
                    st.error(f"Gagal mem-parsing metadata file ini: {res['error']}")
                else:
                    col_meta1, col_meta2 = st.columns([1, 1])
                    with col_meta1:
                        st.markdown("**Metadata Utama (Terekstrak):**")
                        df_m = pd.DataFrame(list(res["metadata"].items()), columns=["Properti", "Nilai"])
                        st.dataframe(df_m, use_container_width=True, hide_index=True)
                        
                        if res["type"] == "Gambar":
                            sw_editor = res["metadata"].get("Software Editor", "N/A")
                            if sw_editor != "N/A" and any(x in sw_editor.lower() for x in ["photoshop", "gimp", "canva", "snapseed", "lightroom"]):
                                st.markdown(f"""
                                <div class="custom-badge badge-warning">
                                    <i class="bi bi-exclamation-triangle-fill"></i> Terindikasi Diedit: Software Editor ({sw_editor}) Terdeteksi
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown("""
                                <div class="custom-badge badge-success">
                                    <i class="bi bi-shield-fill-check"></i> Integritas Asli (Metadata Kamera Murni)
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            author = res["metadata"].get("Penulis (Author)", "N/A")
                            editor = res["metadata"].get("Terakhir Diubah Oleh", "N/A")
                            if res["type"] == "Word (DOCX)" and editor != "N/A" and author != "N/A" and author != editor:
                                st.markdown(f"""
                                <div class="custom-badge badge-warning">
                                    <i class="bi bi-exclamation-triangle-fill"></i> Terindikasi Diedit: Pengubah Terakhir Berbeda ({editor})
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown("""
                                <div class="custom-badge badge-success">
                                    <i class="bi bi-shield-fill-check"></i> Integritas Asli (Metadata Dokumen Orisinal)
                                </div>
                                """, unsafe_allow_html=True)
                            
                    with col_meta2:
                        if res["type"] == "Gambar":
                            try:
                                img_preview = Image.open(io.BytesIO(uploaded_files[idx].getvalue()))
                                img_preview.thumbnail((300, 300))
                                st.image(img_preview, caption=res["name"], use_column_width=False)
                            except:
                                pass
                                
                            if res.get("gps"):
                                st.info(f"Ditemukan Data Koordinat GPS: \nLatitude: {res['gps']['latitude']} \nLongitude: {res['gps']['longitude']}")
                        elif res["type"] in ["PDF", "Word (DOCX)"]:
                            st.info("Dokumen teks tidak memiliki pratinjau visual. Semua properti tercatat lengkap pada tabel metadata utama.")
                            
                    if res["type"] == "Gambar" and res.get("exif_raw"):
                        st.markdown("**EXIF Metadata Mentah (Raw):**")
                        df_exif = pd.DataFrame(list(res["exif_raw"].items()), columns=["Tag EXIF", "Nilai Mentah"])
                        st.dataframe(df_exif, use_container_width=True, hide_index=True)

    # TAB 3: Peta Lokasi (GPS Geotag)
    with tab_map:
        st.markdown('<div class="custom-section-header"><i class="bi bi-geo-alt-fill" style="color:#db2777;"></i> Pemetaan Geografis Koordinat GPS</div>', unsafe_allow_html=True)
        st.markdown("Memetakan koordinat latitude & longitude dari barang bukti digital (foto) yang memiliki penanda lokasi GPS biner:")
        
        gps_locations = []
        for idx, res in enumerate(file_results):
            if res["type"] == "Gambar" and res.get("gps"):
                gps_locations.append({
                    "lat": res["gps"]["latitude"],
                    "lon": res["gps"]["longitude"],
                    "Nama Bukti": res["name"],
                    "Merek HP/Kamera": res["metadata"].get("Model HP/Kamera", "N/A"),
                    "Waktu Jepret": res["metadata"].get("Tanggal Pengambilan", "N/A")
                })
                
        if gps_locations:
            df_gps = pd.DataFrame(gps_locations)
            st.map(df_gps, latitude="lat", longitude="lon", zoom=10)
            
            st.markdown("---")
            st.markdown("**Daftar Detail Lokasi Geotagging:**")
            st.table(df_gps[["Nama Bukti", "Merek HP/Kamera", "Waktu Jepret", "lat", "lon"]])
        else:
            st.info("Tidak ada data GPS yang terdeteksi dari file gambar yang diunggah. Pastikan Anda mengunggah foto asli yang diambil langsung dari kamera HP yang mengaktifkan fitur lokasi/GPS.")
else:
    st.info("Silakan unggah satu atau beberapa file bukti digital (.jpg, .png, .pdf, .docx) di atas untuk memulai analisis forensik metadata.")

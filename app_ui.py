import base64
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = PROJECT_ROOT / "output"
PATIENT_PROFILE_CANDIDATES = [
    PROJECT_ROOT / "input" / "patient_profiles.csv",
    PROJECT_ROOT / "input" / "data" / "mimic-iv-clinical-database" / "patient_profiles.csv",
    PROJECT_ROOT / "patient_profiles.csv",
    PROJECT_ROOT / "data" / "mimic-iv-clinical-database" / "patient_profiles.csv",
]
MIMIC_HOSP_CANDIDATES = [
    PROJECT_ROOT / "input" / "hosp",
    PROJECT_ROOT / "input" / "data" / "mimic-iv-clinical-database-demo-2.2" / "hosp",
    PROJECT_ROOT / "input" / "data" / "mimic-iv-clinical-database" / "hosp",
    PROJECT_ROOT / "hosp",
    PROJECT_ROOT / "data" / "mimic-iv-clinical-database-demo-2.2" / "hosp",
    PROJECT_ROOT / "data" / "mimic-iv-clinical-database" / "hosp",
    Path.home()
    / "Desktop"
    / "mimic-iv-clinical-database-demo-2.2"
    / "mimic-iv-clinical-database-demo-2.2"
    / "hosp",
]


st.set_page_config(
    page_title="衛教 PDF 預覽系統",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
    .block-container {
        max-width: 1180px;
        padding-top: 2.5rem;
        padding-bottom: 3rem;
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1f2937;
        margin-bottom: 0.3rem;
    }
    .hero-subtitle {
        color: #6b7280;
        margin-bottom: 1.4rem;
    }
    .info-box {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }
    .pdf-frame {
        width: 100%;
        height: 820px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
    }
    .patient-box {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def list_pdfs():
    if not PDF_DIR.exists():
        return []
    return sorted(PDF_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)


def find_subject_pdf(subject_id: str):
    subject_id = subject_id.strip()
    if not subject_id:
        return None

    matches = sorted(
        PDF_DIR.glob(f"{subject_id}*.pdf"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def subject_from_pdf(pdf_path: Path):
    return pdf_path.stem.split("_", 1)[0]


@st.cache_data
def load_patient_profiles():
    for path in PATIENT_PROFILE_CANDIDATES:
        if path.exists():
            df = pd.read_csv(path)
            df["subject_id"] = df["subject_id"].astype(str)
            return df, path
    return pd.DataFrame(), None


@st.cache_data
def load_hosp_summary():
    for hosp_dir in MIMIC_HOSP_CANDIDATES:
        patients_path = hosp_dir / "patients.csv.gz"
        admissions_path = hosp_dir / "admissions.csv.gz"
        if patients_path.exists() and admissions_path.exists():
            patients = pd.read_csv(
                patients_path,
                usecols=["subject_id", "gender", "anchor_age"],
            )
            admissions = pd.read_csv(admissions_path, usecols=["subject_id", "hadm_id"])

            patients["subject_id"] = patients["subject_id"].astype(str)
            admissions["subject_id"] = admissions["subject_id"].astype(str)

            admission_counts = (
                admissions.groupby("subject_id")["hadm_id"]
                .nunique()
                .rename("admission_count")
                .reset_index()
            )
            summary = patients.merge(admission_counts, on="subject_id", how="left")
            summary["admission_count"] = summary["admission_count"].fillna(0).astype(int)
            return summary, hosp_dir

    return pd.DataFrame(), None


def get_patient_rows(subject_id: str):
    if patient_profiles.empty:
        return patient_profiles
    return patient_profiles[patient_profiles["subject_id"] == str(subject_id)]


def get_hosp_row(subject_id: str):
    if hosp_summary.empty:
        return None
    matched = hosp_summary[hosp_summary["subject_id"] == str(subject_id)]
    if matched.empty:
        return None
    return matched.iloc[0]


def show_patient_summary(subject_id: str):
    rows = get_patient_rows(subject_id)
    if rows.empty:
        st.warning("找不到此 Subject ID 的 patient_profiles 資料。")
        return

    selected_row = rows.iloc[0]
    if len(rows) > 1 and "hadm_id" in rows.columns:
        hadm_options = [str(value) for value in rows["hadm_id"].tolist()]
        selected_hadm = st.selectbox("選擇 hadm_id", hadm_options)
        selected_row = rows[rows["hadm_id"].astype(str) == selected_hadm].iloc[0]
    hosp_row = get_hosp_row(subject_id)

    st.markdown('<div class="patient-box">', unsafe_allow_html=True)
    st.markdown("### 病人資料摘要")

    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric("Subject ID", selected_row.get("subject_id", ""))
    with metric_cols[1]:
        st.metric("Gender", "" if hosp_row is None else hosp_row.get("gender", ""))
    with metric_cols[2]:
        st.metric("Anchor Age", "" if hosp_row is None else hosp_row.get("anchor_age", ""))
    with metric_cols[3]:
        admission_count = len(rows) if hosp_row is None else hosp_row.get("admission_count", len(rows))
        st.metric("住院次數", admission_count)

    with st.expander("查看 diagnoses 與 prescriptions / medications", expanded=True):
        st.markdown("**Diagnoses：**")
        st.write(selected_row.get("diagnoses", ""))

        medication_text = selected_row.get(
            "prescriptions",
            selected_row.get("medications", ""),
        )
        st.markdown("**Prescriptions / Medications：**")
        st.write(medication_text)

    st.markdown("</div>", unsafe_allow_html=True)


def show_pdf(pdf_path: Path):
    encoded = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <iframe
            class="pdf-frame"
            src="data:application/pdf;base64,{encoded}"
            type="application/pdf">
        </iframe>
        """,
        unsafe_allow_html=True,
    )


st.markdown('<div class="hero-title">衛教 PDF 預覽系統</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle">讀取 patient_education/output 內已產生的衛教 PDF。</div>',
    unsafe_allow_html=True,
)

pdfs = list_pdfs()
patient_profiles, patient_profiles_path = load_patient_profiles()
hosp_summary, hosp_summary_path = load_hosp_summary()

with st.sidebar:
    st.header("資料夾")
    st.code(str(PDF_DIR))
    st.write(f"PDF 數量：{len(pdfs)}")
    st.divider()
    st.header("病人資料")
    if patient_profiles_path:
        st.code(str(patient_profiles_path))
        st.write(f"資料筆數：{len(patient_profiles)}")
    else:
        st.warning("找不到 patient_profiles.csv")
    if hosp_summary_path:
        st.caption("MIMIC hosp")
        st.code(str(hosp_summary_path))
    else:
        st.warning("找不到 hosp/patients.csv.gz 與 admissions.csv.gz")

st.markdown('<div class="info-box">請輸入病人 Subject ID，或從現有 PDF 清單選擇一份檔案。</div>', unsafe_allow_html=True)

query_col, select_col = st.columns([1, 1.3])

with query_col:
    subject_id = st.text_input("Subject ID", placeholder="例如：123456")
    search_clicked = st.button("查詢 PDF", type="primary", use_container_width=True)

with select_col:
    options = [""] + [p.name for p in pdfs]
    selected_name = st.selectbox("或選擇現有 PDF", options)

selected_pdf = None

if search_clicked:
    selected_pdf = find_subject_pdf(subject_id)
    if selected_pdf is None:
        st.error("找不到此 Subject ID 對應的 PDF。")
elif selected_name:
    selected_pdf = PDF_DIR / selected_name
elif pdfs:
    selected_pdf = pdfs[0]

if selected_pdf and selected_pdf.exists():
    st.divider()
    st.subheader(selected_pdf.name)
    st.caption(f"檔案位置：{selected_pdf}")

    selected_subject_id = subject_id.strip() if search_clicked and subject_id.strip() else subject_from_pdf(selected_pdf)
    show_patient_summary(selected_subject_id)

    with open(selected_pdf, "rb") as f:
        st.download_button(
            label="下載 PDF 衛教手冊",
            data=f,
            file_name=selected_pdf.name,
            mime="application/pdf",
            use_container_width=True,
        )

    show_pdf(selected_pdf)
else:
    st.info("目前尚未選擇 PDF。")

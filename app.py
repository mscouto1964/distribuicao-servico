
import streamlit as st
import pandas as pd
import io, zipfile, re

st.set_page_config(page_title="Distribuição de Serviço Docente", layout="wide")

# ===============================
# Robust readers & normalizers
# ===============================
def read_csv_robust(file_or_bytes, filename="upload"):
    if hasattr(file_or_bytes, "read"):
        data = file_or_bytes.read()
    elif isinstance(file_or_bytes, (bytes, bytearray)):
        data = bytes(file_or_bytes)
    else:
        with open(file_or_bytes, "rb") as f:
            data = f.read()

    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    seps = [None, ";", ",", "\t", "|"]
    for enc in encodings:
        for sep in seps:
            try:
                bio = io.BytesIO(data)
                if sep is None:
                    df = pd.read_csv(bio, sep=None, engine="python", encoding=enc)
                else:
                    df = pd.read_csv(bio, sep=sep, engine="python", encoding=enc)
                if df.shape[1] >= 2:
                    return df
            except Exception:
                continue
    return None

def normalize_ciclo(x):
    if pd.isna(x): return ""
    s = str(x).strip().lower()
    if s.startswith(("pré","pre")): return "Pré"
    if s.startswith("1"): return "1º"
    if s.startswith("2"): return "2º"
    if s.startswith("3"): return "3º"
    if s.startswith(("sec","secund")): return "Sec"
    return str(x)

def normalize_ano(x):
    if pd.isna(x): return ""
    s = str(x).strip().lower()
    if s.startswith(("pré","pre")): return "Pré"
    m = re.search(r"\\d+", s)
    if m: return m.group(0)
    return str(x)

REQUIRED = {
    "docentes": ["id","nome","grupo","reducao79_min"],
    "turmas": ["id","ciclo","ano","curso","n_alunos","escola"],
    "matriz": ["ciclo","ano","disciplina","carga_sem_min"],
}

def validate_schema(df, cols, name):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"{name}.csv: faltam colunas {missing}")
        st.stop()

# ===============================
# Estado
# ===============================
if "assignments" not in st.session_state:
    st.session_state.assignments = []
if "te_atr_global" not in st.session_state:
    st.session_state.te_atr_global = 150

def assignments_df():
    if not st.session_state.assignments:
        return pd.DataFrame(columns=["turma_id","ciclo","ano","disciplina","docente_id"])
    return pd.DataFrame(st.session_state.assignments)

# ===============================
# SEMÁFORO avaliação
# ===============================
def avaliar_semaforo(row):
    letiva = int(row["letiva_atr_min"])
    grupo = str(row["grupo"])
    te = int(row["te_atr_min"])

    if letiva == 0:
        return "🔴", "Sem componente letiva"

    if grupo in ["100","110"]:
        if letiva == 1500 and te <= 150:
            return "🟢", "Completa (1500 min + TE)"
        else:
            return "🟡", "Em preenchimento"
    else:
        if letiva > 1100:
            return "🟡", f"Acima de 1100 (+{letiva-1100})"
        rem = 1100 - letiva
        if rem < 50 and te <= 150:
            return "🟢", "Completa (remanescente <50 + TE)"
        else:
            return "🟡", "Em preenchimento"

# ===============================
# App main simplified (focus in semáforo table)
# ===============================
st.title("Distribuição de Serviço Docente — Semáforo")

# Mock data (para teste offline)
docentes = pd.DataFrame([
    {"id":"Pre1","nome":"Ana Silva","grupo":"100","reducao79_min":0},
    {"id":"D2","nome":"Bruno Sousa","grupo":"510","reducao79_min":0},
    {"id":"D3","nome":"Carla Reis","grupo":"600","reducao79_min":0},
])
matriz = pd.DataFrame([
    {"ciclo":"Pré","ano":"Pré","disciplina":"At. Let.","carga_sem_min":1500},
    {"ciclo":"3º","ano":"7","disciplina":"FQ","carga_sem_min":150},
])
assignments = assignments_df()

# Calcular letiva atribuída (mock simplificado)
docentes["letiva_atr_min"] = [1500, 800, 0]
docentes["alvo_letiva_min"] = docentes["grupo"].apply(lambda g: 1500 if g in ["100","110"] else 1100)
docentes["te_atr_min"] = st.session_state.te_atr_global
docentes["te_alvo_min"] = 150

docentes[["semaforo","estado"]] = docentes.apply(lambda r: pd.Series(avaliar_semaforo(r)), axis=1)

st.dataframe(docentes[["id","nome","grupo","letiva_atr_min","alvo_letiva_min","reducao79_min","te_atr_min","te_alvo_min","semaforo","estado"]])


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

def load_from_zip(file):
    data = file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(data),'r') as z:
            result = {}
            for key in REQUIRED:
                for cand in [f"{key}.csv", f"{key}.CSV"]:
                    try:
                        with z.open(cand) as f:
                            df = read_csv_robust(io.BytesIO(f.read()), cand)
                            if df is not None:
                                result[key] = df
                                break
                    except KeyError:
                        continue
            return result
    except Exception as e:
        st.error(f"Erro a ler ZIP: {e}")
        return {}

# ===============================
# Defaults
# ===============================
docentes_def = pd.DataFrame([
    {"id":"Pre1","nome":"Ana Silva","grupo":"100","reducao79_min":0},
    {"id":"D2","nome":"Bruno Sousa","grupo":"510","reducao79_min":0},
    {"id":"D3","nome":"Carla Reis","grupo":"600","reducao79_min":0},
])
turmas_def = pd.DataFrame([
    {"id":"P1","ciclo":"Pré","ano":"Pré","curso":"Reg","n_alunos":20,"escola":"EB1"},
    {"id":"7A","ciclo":"3º","ano":"7","curso":"Reg","n_alunos":26,"escola":"Sede"},
    {"id":"10A","ciclo":"Sec","ano":"10","curso":"CH","n_alunos":28,"escola":"Sede"},
])
matriz_def = pd.DataFrame([
    {"ciclo":"Pré","ano":"Pré","disciplina":"At. Let.","carga_sem_min":1500},
    {"ciclo":"1º","ano":"1","disciplina":"Português","carga_sem_min":420},
    {"ciclo":"1º","ano":"1","disciplina":"Matemática","carga_sem_min":420},
    {"ciclo":"3º","ano":"7","disciplina":"Físico-Química","carga_sem_min":150},
    {"ciclo":"Sec","ano":"10","disciplina":"Física","carga_sem_min":150},
])

# ===============================
# Uploads
# ===============================
st.sidebar.header("Carregar dados")
zip_up = st.sidebar.file_uploader("ZIP com docentes.csv, turmas.csv, matriz.csv (opcional)", type=["zip"])
uploaded = {}
if zip_up is not None:
    uploaded.update(load_from_zip(zip_up))

up_doc = st.sidebar.file_uploader("docentes.csv", type=["csv"])
up_tur = st.sidebar.file_uploader("turmas.csv", type=["csv"])
up_mat = st.sidebar.file_uploader("matriz.csv", type=["csv"])

if up_doc is not None: uploaded["docentes"] = read_csv_robust(up_doc, "docentes.csv")
if up_tur is not None: uploaded["turmas"] = read_csv_robust(up_tur, "turmas.csv")
if up_mat is not None: uploaded["matriz"] = read_csv_robust(up_mat, "matriz.csv")

docentes = uploaded.get("docentes", docentes_def).copy()
turmas   = uploaded.get("turmas", turmas_def).copy()
matriz   = uploaded.get("matriz", matriz_def).copy()

validate_schema(docentes, REQUIRED["docentes"], "docentes")
validate_schema(turmas,   REQUIRED["turmas"],   "turmas")
validate_schema(matriz,   REQUIRED["matriz"],   "matriz")

# Normalização
turmas["ciclo"] = turmas["ciclo"].map(normalize_ciclo)
turmas["ano"]   = turmas["ano"].map(normalize_ano)
matriz["ciclo"] = matriz["ciclo"].map(normalize_ciclo)
matriz["ano"]   = matriz["ano"].map(normalize_ano)

# ===============================
# Estado
# ===============================
if "assignments" not in st.session_state:
    st.session_state.assignments = []
# TE global (igual para todos)
if "te_atr_global" not in st.session_state:
    st.session_state.te_atr_global = 150  # default

def assignments_df():
    if not st.session_state.assignments:
        return pd.DataFrame(columns=["turma_id","ciclo","ano","disciplina","docente_id"])
    return pd.DataFrame(st.session_state.assignments)

# ===============================
# Sidebar: Professores, filtros, modo
# ===============================
st.sidebar.markdown("### Professores")
grupos = ["Todos"] + sorted(docentes["grupo"].astype(str).unique().tolist())
grupo_f = st.sidebar.selectbox("Filtrar por grupo", options=grupos, index=0)
q = st.sidebar.text_input("Pesquisa por nome/id", "")
docentes_view = docentes.copy()
if grupo_f != "Todos":
    docentes_view = docentes_view[docentes_view["grupo"].astype(str)==str(grupo_f)]
if q.strip():
    ql = q.lower()
    docentes_view = docentes_view[docentes_view.apply(lambda r: ql in str(r["nome"]).lower() or ql in str(r["grupo"]).lower() or ql in str(r["id"]).lower(), axis=1)]
for _, r in docentes_view.iterrows():
    st.sidebar.write(f"**{r['id']}** — {r['nome']} ({r['grupo']})")

st.sidebar.markdown("---")
# Janela/painel para TE GLOBAL
st.sidebar.subheader("Trabalho de Escola (global)")
te_val = st.sidebar.slider("Atribuído a TODOS os docentes (min)", min_value=0, max_value=150, value=int(st.session_state.te_atr_global), step=5)
if st.sidebar.button("Guardar TE global"):
    st.session_state.te_atr_global = int(te_val)
    st.sidebar.success(f"TE global definido: {int(te_val)} min")

st.sidebar.markdown("---")
modo = st.sidebar.radio("Modo de trabalho", options=["Por turma","Por docente","Por disciplina/ano","Resumo"], index=0)

# ===============================
# (Modos Por turma / Por docente / Por disciplina/ano / Resumo)
# Reutilizamos a mesma implementação do build anterior FULL_BADGES_DISCIPLINA_ANO
# (omitida aqui por brevidade). As operações de assignments mantêm-se.
# ===============================

# ----- placeholder simplificado de tabela de atribuições (para manter artefactos mínimos) -----
st.title("Distribuição de Serviço — (interface resumida para foco no TE global)")
st.info("Este build foca-se na alteração: TE global = igual para todos os docentes. \
Os modos completos de edição (Turma/Docente/Disciplina) mantêm-se iguais ao build anterior; \
substitua apenas a secção de 'Cargas por docente'.")

# ===============================
# Cargas por docente (com TE global)
# ===============================
st.markdown("---")
st.header("Cargas por docente e conformidade de regras")

out_df_all = assignments_df()
if out_df_all.empty:
    st.info("Sem atribuições letivas ainda.")
else:
    mat_key = matriz[["ciclo","ano","disciplina","carga_sem_min"]].drop_duplicates()
    rep = out_df_all.merge(mat_key, how="left", on=["ciclo","ano","disciplina"])
    rep["carga_sem_min"] = pd.to_numeric(rep["carga_sem_min"], errors="coerce").fillna(0).astype(int)

    carga_por_doc = rep.groupby("docente_id")["carga_sem_min"].sum().reset_index().rename(columns={"carga_sem_min":"letiva_atr_min"})
    carga_por_doc = carga_por_doc.merge(docentes[["id","nome","grupo","reducao79_min"]], left_on="docente_id", right_on="id", how="right")
    carga_por_doc["letiva_atr_min"] = carga_por_doc["letiva_atr_min"].fillna(0).astype(int)
    carga_por_doc["reducao79_min"] = pd.to_numeric(carga_por_doc["reducao79_min"], errors="coerce").fillna(0).astype(int)
    carga_por_doc["alvo_letiva_min"] = carga_por_doc["grupo"].astype(str).apply(lambda g: 1500 if g in ["100","110"] else 1100)

    # TE global (igual para todos)
    te_alvo = 150
    te_atr_global = int(st.session_state.te_atr_global)
    carga_por_doc["te_atr_min"] = te_atr_global
    carga_por_doc["te_alvo_min"] = te_alvo

    def avaliar(row):
        letiva = int(row["letiva_atr_min"])
        grupo = str(row["grupo"])
        estados = []

        if grupo in ["100","110"]:
            if letiva == 1500:
                estados.append("Letiva OK")
            elif letiva < 1500:
                estados.append(f"Letiva abaixo 1500 (-{1500 - letiva})")
            else:
                estados.append(f"Letiva acima 1500 (+{letiva - 1500})")
        else:
            if letiva > 1100:
                estados.append(f"Letiva acima 1100 (+{letiva - 1100})")
            elif letiva < 1100:
                rem = 1100 - letiva
                if rem >= 50:
                    need = rem - 49
                    estados.append(f"Letiva: remanescente ≥50 (precisa +{need})")
                else:
                    estados.append("Letiva OK")
            else:
                estados.append("Letiva OK")

        te = int(row["te_atr_min"])
        if te > te_alvo:
            estados.append(f"TE acima do alvo (+{te - te_alvo})")
        else:
            estados.append("TE OK")

        return " | ".join(estados)

    carga_por_doc["estado"] = carga_por_doc.apply(avaliar, axis=1)

    show_cols = ["docente_id","nome","grupo",
                 "letiva_atr_min","alvo_letiva_min",
                 "reducao79_min",
                 "te_atr_min","te_alvo_min",
                 "estado"]
    st.dataframe(carga_por_doc[show_cols].sort_values(["docente_id"]), use_container_width=True)

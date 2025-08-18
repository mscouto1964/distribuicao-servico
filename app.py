
import streamlit as st
import pandas as pd
import io, zipfile

st.set_page_config(page_title="Distribuição de Serviço Docente", layout="wide")

# =========================
# Funções auxiliares
# =========================
def read_csv_robust(file_or_bytes):
    if hasattr(file_or_bytes, "read"):
        data = file_or_bytes.read()
    else:
        data = file_or_bytes
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except:
            continue
    return None

# =========================
# Estado inicial
# =========================
if "assignments" not in st.session_state:
    st.session_state.assignments = []
if "cargos" not in st.session_state:
    st.session_state.cargos = []
if "te_global" not in st.session_state:
    st.session_state.te_global = 150
if "credito_total" not in st.session_state:
    st.session_state.credito_total = 500

# =========================
# Upload de ficheiros
# =========================
st.sidebar.header("Carregar ficheiros")
up_doc = st.sidebar.file_uploader("docentes.csv", type=["csv"])
up_tur = st.sidebar.file_uploader("turmas.csv", type=["csv"])
up_mat = st.sidebar.file_uploader("matriz.csv", type=["csv"])
up_car = st.sidebar.file_uploader("cargos.csv", type=["csv"])

# Modelos CSV
st.sidebar.markdown("### Descarregar modelos")
st.sidebar.download_button("Modelo docentes.csv",
    "id,nome,grupo,reducao79_min\nD1,Ana Silva,510,0\n",
    file_name="docentes.csv")
st.sidebar.download_button("Modelo turmas.csv",
    "id,ciclo,ano,curso,n_alunos,escola\n7A,3º,7,Reg,26,Sede\n",
    file_name="turmas.csv")
st.sidebar.download_button("Modelo matriz.csv",
    "ciclo,ano,disciplina,carga_sem_min\n3º,7,Português,150\n",
    file_name="matriz.csv")
st.sidebar.download_button("Modelo cargos.csv",
    "id,cargo,carga_min\nC1,Diretor de Turma,45\nC2,Coord. Departamento,90\n",
    file_name="cargos.csv")

# =========================
# TE e crédito global
# =========================
st.sidebar.subheader("Configurações Globais")
st.session_state.te_global = st.sidebar.slider("Trabalho de Escola (TE)", 0, 150, st.session_state.te_global, step=5)
st.session_state.credito_total = st.sidebar.number_input("Crédito total (min)", value=st.session_state.credito_total, step=10)

# =========================
# Mock data se não carregar nada
# =========================
if up_doc: docentes = read_csv_robust(up_doc)
else: docentes = pd.DataFrame([{"id":"D1","nome":"Ana Silva","grupo":"510","reducao79_min":0}])

if up_tur: turmas = read_csv_robust(up_tur)
else: turmas = pd.DataFrame([{"id":"7A","ciclo":"3º","ano":"7","curso":"Reg","n_alunos":26,"escola":"Sede"}])

if up_mat: matriz = read_csv_robust(up_mat)
else: matriz = pd.DataFrame([{"ciclo":"3º","ano":"7","disciplina":"Português","carga_sem_min":150}])

if up_car: cargos = read_csv_robust(up_car)
else: cargos = pd.DataFrame([{"id":"C1","cargo":"Diretor de Turma","carga_min":45}])

# =========================
# Atribuição de cargos
# =========================
st.title("Gestão de Cargos")
if not cargos.empty:
    st.markdown("Atribuir cargos a docentes e escolher imputação (LETIVA / ART79 / TE).")
    docentes_opts = [""] + docentes["id"].astype(str).tolist()
    cargos["docente_id"] = ""
    cargos["imputacao"] = "LETIVA"
    edited = st.data_editor(
        cargos,
        column_config={
            "docente_id": st.column_config.SelectboxColumn("Docente", options=docentes_opts),
            "imputacao": st.column_config.SelectboxColumn("Imputação", options=["LETIVA","ART79","TE"])
        },
        hide_index=True, use_container_width=True
    )
    if st.button("Guardar cargos"):
        st.session_state.cargos = edited.to_dict(orient="records")
        st.success("Cargos atribuídos.")

# =========================
# Crédito usado e restante
# =========================
cargos_df = pd.DataFrame(st.session_state.cargos)
credito_gasto = 0
if not cargos_df.empty:
    credito_gasto = cargos_df[cargos_df["imputacao"]=="LETIVA"]["carga_min"].sum()
st.sidebar.metric("Crédito total", st.session_state.credito_total)
st.sidebar.metric("Crédito gasto (LETIVA)", credito_gasto)
st.sidebar.metric("Crédito restante", st.session_state.credito_total - credito_gasto)

# =========================
# Tabela de cargas por docente (simplificada)
# =========================
st.header("Cargas por Docente (simplificado)")
res = docentes.copy()
res["letiva_atr_min"] = 0
res["art79"] = res["reducao79_min"]
res["te"] = st.session_state.te_global
if not cargos_df.empty:
    for _, row in cargos_df.iterrows():
        if not row["docente_id"]: continue
        if row["imputacao"]=="LETIVA":
            res.loc[res["id"]==row["docente_id"],"letiva_atr_min"] += row["carga_min"]
        elif row["imputacao"]=="ART79":
            res.loc[res["id"]==row["docente_id"],"art79"] += row["carga_min"]
        elif row["imputacao"]=="TE":
            res.loc[res["id"]==row["docente_id"],"te"] += row["carga_min"]
st.dataframe(res, use_container_width=True)

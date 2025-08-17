
import streamlit as st
import pandas as pd
from streamlit_sortables import sort_items
import io, zipfile

st.set_page_config(page_title="Distribuição de Serviço Docente", layout="wide")

# ===============================
# Helpers
# ===============================
def normalize_ciclo(x: str):
    if not isinstance(x, str): return ""
    t = str(x).strip().lower()
    if t.startswith("pré") or t.startswith("pre"): return "Pré"
    if t.startswith("1"): return "1º"
    if t.startswith("2"): return "2º"
    if t.startswith("3"): return "3º"
    if t.startswith("sec") or "secund" in t: return "Sec"
    return x

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
                            result[key] = pd.read_csv(f)
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
    {"id":"D1","nome":"Ana Silva","grupo":"110","reducao79_min":0},
    {"id":"D2","nome":"Bruno Sousa","grupo":"510","reducao79_min":0},
    {"id":"D3","nome":"Carla Reis","grupo":"600","reducao79_min":0},
])
turmas_def = pd.DataFrame([
    {"id":"1A","ciclo":"1º","ano":1,"curso":"Reg","n_alunos":24,"escola":"EB1"},
    {"id":"7A","ciclo":"3º","ano":7,"curso":"Reg","n_alunos":26,"escola":"Sede"},
    {"id":"10A","ciclo":"Sec","ano":10,"curso":"CH","n_alunos":28,"escola":"Sede"},
])
matriz_def = pd.DataFrame([
    {"ciclo":"1º","ano":1,"disciplina":"Português","carga_sem_min":300},
    {"ciclo":"1º","ano":1,"disciplina":"Estudo do Meio","carga_sem_min":150},
    {"ciclo":"3º","ano":7,"disciplina":"Físico-Química","carga_sem_min":150},
    {"ciclo":"Sec","ano":10,"disciplina":"Física","carga_sem_min":150},
    {"ciclo":"Sec","ano":10,"disciplina":"Matemática","carga_sem_min":150},
])

# ===============================
# Loaders (ZIP or individual)
# ===============================
st.sidebar.header("Carregar dados")
zip_up = st.sidebar.file_uploader("ZIP com docentes.csv, turmas.csv, matriz.csv (opcional)", type=["zip"])
uploaded = {}
if zip_up is not None:
    uploaded.update(load_from_zip(zip_up))

up_doc = st.sidebar.file_uploader("docentes.csv", type=["csv"])
up_tur = st.sidebar.file_uploader("turmas.csv", type=["csv"])
up_mat = st.sidebar.file_uploader("matriz.csv", type=["csv"])

if up_doc is not None: uploaded["docentes"] = pd.read_csv(up_doc)
if up_tur is not None: uploaded["turmas"] = pd.read_csv(up_tur)
if up_mat is not None: uploaded["matriz"] = pd.read_csv(up_mat)

docentes = uploaded.get("docentes", docentes_def).copy()
turmas   = uploaded.get("turmas", turmas_def).copy()
matriz   = uploaded.get("matriz", matriz_def).copy()

validate_schema(docentes, REQUIRED["docentes"], "docentes")
validate_schema(turmas,   REQUIRED["turmas"],   "turmas")
validate_schema(matriz,   REQUIRED["matriz"],   "matriz")

turmas["ciclo"] = turmas["ciclo"].map(normalize_ciclo)
matriz["ciclo"] = matriz["ciclo"].map(normalize_ciclo)

# ===============================
# Session state: distribution model
# assignments: list of dicts {turma_id, ciclo, ano, disciplina, docente_id}
# ===============================
if "assignments" not in st.session_state:
    st.session_state.assignments = []

def current_assignments_df():
    if not st.session_state.assignments:
        return pd.DataFrame(columns=["turma_id","ciclo","ano","disciplina","docente_id"])
    return pd.DataFrame(st.session_state.assignments)

def set_assignment(turma_id, ciclo, ano, disciplina, docente_id):
    df = current_assignments_df()
    # remove any existing row for (turma,disciplina)
    df = df[~((df["turma_id"]==turma_id) & (df["disciplina"]==disciplina))].copy()
    # add new
    df = pd.concat([df, pd.DataFrame([{
        "turma_id":turma_id,"ciclo":ciclo,"ano":ano,"disciplina":disciplina,"docente_id":docente_id
    }])], ignore_index=True)
    st.session_state.assignments = df.to_dict(orient="records")

def unassign(turma_id, disciplina):
    df = current_assignments_df()
    df = df[~((df["turma_id"]==turma_id) & (df["disciplina"]==disciplina))].copy()
    st.session_state.assignments = df.to_dict(orient="records")

# ===============================
# Sidebar: Professores + Turmas + Disciplinas
# ===============================
st.sidebar.markdown("### Professores")
for _, r in docentes.iterrows():
    st.sidebar.write(f"**{r['id']}** — {r['nome']} ({r['grupo']})")

st.sidebar.markdown("---")
st.sidebar.markdown("### Turmas")
turma_sel = st.sidebar.selectbox(
    "Selecionar turma",
    options=list(turmas["id"].astype(str)),
    index=0 if len(turmas)>0 else None
)

turma_row = turmas[turmas["id"].astype(str)==str(turma_sel)].iloc[0]
ciclo_sel = turma_row["ciclo"]
ano_sel = turma_row["ano"]

disciplinas_turma = matriz[(matriz["ciclo"]==ciclo_sel) & (matriz["ano"]==ano_sel)]["disciplina"].dropna().astype(str).tolist()
if not disciplinas_turma:
    st.sidebar.info("Não há disciplinas definidas na matriz para esta turma (ciclo+ano).")

st.sidebar.markdown("**Disciplinas da turma selecionada:**")
for d in disciplinas_turma:
    st.sidebar.write("- ", d)

# ===============================
# Main: Drag & drop interface
# ===============================
st.title("Distribuição de Serviço — Drag & Drop")

# Build lists for DnD
# List 0: Por atribuir (da turma selecionada)
ass_df = current_assignments_df()
already = set(ass_df.loc[ass_df["turma_id"]==turma_sel, "disciplina"].tolist())
por_atribuir = [f"{turma_sel} · {disc}" for disc in disciplinas_turma if disc not in already]

# One list per docente: items assigned a ele (de todas as turmas)
listas = []
labels = ["Por atribuir"] + [f"{row['id']} — {row['nome']}" for _, row in docentes.iterrows()]

# Inicial items: build per-teacher lists showing items currently assigned
doc_lists = {}
for _, row in docentes.iterrows():
    did = row["id"]
    mine = ass_df[ass_df["docente_id"]==did]
    items = [f"{r.turma_id} · {r.disciplina}" for r in mine.itertuples(index=False)]
    doc_lists[did] = items

listas = [por_atribuir] + list(doc_lists.values())

st.caption("Arraste uma disciplina da lista *Por atribuir* para o professor pretendido. Itens mostram 'TURMA · DISCIPLINA'.")

new_lists = sort_items(
    lists=listas,
    direction="horizontal",
    min_height=300,
    # styles
    stylesheet="""
    .sortable {background: #f8fafc; padding: 10px; border-radius: 12px; min-height: 280px;}
    .item {background: white; padding: 8px 10px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #e5e7eb;}
    """,
    list_labels=labels
)

# Interpret changes: compare old vs new
# new_lists[0] = Por atribuir; new_lists[i] = docente i-1
if new_lists is not None:
    # rebuild assignments from lists 1..n
    new_assignments = []
    for i, (_, row) in enumerate(docentes.iterrows(), start=1):
        did = row["id"]
        items = new_lists[i]
        for it in items:
            turma_id, disc = [x.strip() for x in it.split("·",1)]
            # fetch ciclo/ano from turmas
            trow = turmas[turmas["id"].astype(str)==str(turma_id)].iloc[0]
            new_assignments.append({
                "turma_id": turma_id,
                "ciclo": trow["ciclo"],
                "ano": trow["ano"],
                "disciplina": disc,
                "docente_id": did
            })
    st.session_state.assignments = new_assignments

# ===============================
# Output tables
# ===============================
st.subheader("Atribuições atuais")
out_df = current_assignments_df().sort_values(["turma_id","disciplina"]).reset_index(drop=True)
st.dataframe(out_df, use_container_width=True)

# Tabela de turmas × disciplinas com docente atribuído (id)
st.subheader(f"Turma {turma_sel}: Disciplinas e docente atribuído")
turma_matrix = pd.DataFrame({"disciplina": disciplinas_turma})
turma_matrix["docente_id"] = turma_matrix["disciplina"].map(
    out_df[out_df["turma_id"]==turma_sel].set_index("disciplina")["docente_id"].to_dict()
).fillna("")

st.dataframe(turma_matrix, use_container_width=True)

# ===============================
# Download / Upload distribuição
# ===============================
st.markdown("---")
c1, c2 = st.columns(2)
with c1:
    st.download_button("Descarregar distribuição (CSV)",
        out_df.to_csv(index=False).encode("utf-8"),
        "distribuicao_servico.csv",
        "text/csv"
    )
with c2:
    up_dist = st.file_uploader("Repor distribuição a partir de CSV (turma_id,ciclo,ano,disciplina,docente_id)", type=["csv"], key="dist_up")
    if up_dist is not None:
        try:
            imp = pd.read_csv(up_dist)
            # valida cols
            needed = ["turma_id","ciclo","ano","disciplina","docente_id"]
            if all(c in imp.columns for c in needed):
                st.session_state.assignments = imp[needed].to_dict(orient="records")
                st.success("Distribuição carregada.")
            else:
                st.error("CSV inválido. Deve conter as colunas: " + ", ".join(needed))
        except Exception as e:
            st.error(f"Erro a ler CSV: {e}")

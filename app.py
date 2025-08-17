
import streamlit as st
import pandas as pd
import io, zipfile, re

st.set_page_config(page_title="Distribuição de Serviço Docente", layout="wide")

# ===============================
# Robust readers & normalizers
# ===============================
def read_csv_robust(file_or_bytes, filename="upload"):
    """Read CSV trying multiple encodings and separators; return DataFrame or None."""
    if hasattr(file_or_bytes, "read"):
        data = file_or_bytes.read()
    elif isinstance(file_or_bytes, (bytes, bytearray)):
        data = bytes(file_or_bytes)
    else:
        # assume path
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
    s = s.replace("º", "º")  # keep ordinal symbol
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
    # extrair dígitos (e.g., "1º", "1Âº")
    m = re.search(r"\d+", s)
    if m: return m.group(0)  # "1","2",...
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
# Defaults (caso não carregue CSVs)
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

# Normalização de texto
turmas["ciclo"] = turmas["ciclo"].map(normalize_ciclo)
turmas["ano"]   = turmas["ano"].map(normalize_ano)
matriz["ciclo"] = matriz["ciclo"].map(normalize_ciclo)
matriz["ano"]   = matriz["ano"].map(normalize_ano)

# ===============================
# Estado
# ===============================
if "assignments" not in st.session_state:
    st.session_state.assignments = []

def assignments_df():
    if not st.session_state.assignments:
        return pd.DataFrame(columns=["turma_id","ciclo","ano","disciplina","docente_id"])
    return pd.DataFrame(st.session_state.assignments)

# ===============================
# Sidebar: Filtros e Turma
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
st.sidebar.markdown("### Turmas")
turma_sel = st.sidebar.selectbox("Selecionar turma", options=list(turmas["id"].astype(str)))

turma_row = turmas[turmas["id"].astype(str)==str(turma_sel)].iloc[0]
ciclo_sel, ano_sel = turma_row["ciclo"], turma_row["ano"]

disciplinas_turma = matriz[(matriz["ciclo"]==ciclo_sel) & (matriz["ano"]==ano_sel)]["disciplina"].dropna().astype(str).tolist()
if not disciplinas_turma:
    st.sidebar.info("Não há disciplinas definidas na matriz para esta turma (ciclo+ano).")

# ===============================
# Main: Editor por Tabela
# ===============================
st.title("Distribuição de Serviço — Atribuição por Tabela (Robusto)")

st.write(f"**Turma selecionada:** {turma_sel} — {ciclo_sel} (ano: {ano_sel})")
ass = assignments_df()
mapa_doc = {r["id"]: f"{r['id']} — {r['nome']}" for _, r in docentes.iterrows()}
opcoes = [""] + list(mapa_doc.keys())

t = pd.DataFrame({"disciplina": disciplinas_turma})
ja = ass[ass["turma_id"]==turma_sel].set_index("disciplina")["docente_id"].to_dict()
t["docente_id"] = t["disciplina"].map(ja).fillna("")

edited = st.data_editor(
    t,
    column_config={
        "docente_id": st.column_config.SelectboxColumn(
            "Docente",
            options=opcoes,
            required=False
        )
    },
    use_container_width=True,
    hide_index=True,
    num_rows="fixed"
)

cA, cB, cC = st.columns([1,1,2])
with cA:
    if st.button("Guardar atribuições da turma", type="primary"):
        df = assignments_df()
        df = df[df["turma_id"]!=turma_sel].copy()
        novas = []
        for _, r in edited.iterrows():
            did = str(r["docente_id"]).strip()
            if did == "": continue
            novas.append({"turma_id": turma_sel, "ciclo": ciclo_sel, "ano": ano_sel, "disciplina": r["disciplina"], "docente_id": did})
        if novas:
            df = pd.concat([df, pd.DataFrame(novas)], ignore_index=True)
        st.session_state.assignments = df.to_dict(orient="records")
        st.success("Atribuições guardadas.")
with cB:
    if st.button("Limpar atribuições da turma"):
        df = assignments_df()
        df = df[df["turma_id"]!=turma_sel].copy()
        st.session_state.assignments = df.to_dict(orient="records")
        st.info("Atribuições da turma removidas.")
with cC:
    cols = [""] + docentes["id"].astype(str).tolist()
    destinatario = st.selectbox("Atribuir TODAS as disciplinas da turma a…", options=cols, index=0)
    if st.button("Aplicar atribuição total"):
        if destinatario != "":
            novas = [{"turma_id": turma_sel, "ciclo": ciclo_sel, "ano": ano_sel, "disciplina": d, "docente_id": destinatario} for d in disciplinas_turma]
            st.session_state.assignments = [r for r in st.session_state.assignments if r["turma_id"]!=turma_sel] + novas
            st.success(f"Todas as disciplinas da turma {turma_sel} atribuídas a {destinatario}.")
        else:
            st.warning("Escolha um docente.")

# ===============================
# Output
# ===============================
st.subheader("Atribuições atuais (todas as turmas)")
out_df = assignments_df().sort_values(["turma_id","disciplina"]).reset_index(drop=True)
st.dataframe(out_df, use_container_width=True)

st.subheader(f"{turma_sel}: Disciplinas e docente atribuído")
turma_matrix = pd.DataFrame({"disciplina": disciplinas_turma})
turma_matrix["docente_id"] = turma_matrix["disciplina"].map(out_df[out_df["turma_id"]==turma_sel].set_index("disciplina")["docente_id"].to_dict()).fillna("")
st.dataframe(turma_matrix, use_container_width=True)

# ===============================
# Regras & contadores por docente
# ===============================
st.markdown("---")
st.header("Cargas por docente e conformidade de regras")

if out_df.empty:
    st.info("Sem atribuições ainda.")
else:
    mat_key = matriz[["ciclo","ano","disciplina","carga_sem_min"]].drop_duplicates()
    rep = out_df.merge(mat_key, how="left", on=["ciclo","ano","disciplina"])
    rep["carga_sem_min"] = pd.to_numeric(rep["carga_sem_min"], errors="coerce").fillna(0).astype(int)

    carga_por_doc = rep.groupby("docente_id")["carga_sem_min"].sum().reset_index().rename(columns={"carga_sem_min":"letiva_min"})
    carga_por_doc = carga_por_doc.merge(docentes[["id","nome","grupo"]], left_on="docente_id", right_on="id", how="left")
    carga_por_doc["alvo"] = carga_por_doc["grupo"].astype(str).apply(lambda g: 1500 if g in ["100","110"] else 1100)

    def avaliar(row):
        letiva = int(row["letiva_min"])
        grupo = str(row["grupo"])
        if grupo in ["100","110"]:
            if letiva == 1500:
                return "OK", ""
            elif letiva < 1500:
                return "Abaixo 1500", f"Aumentar {1500 - letiva} min de LETIVA (grupo {grupo})."
            else:
                return "Acima 1500", f"Reduzir {letiva - 1500} min de LETIVA (grupo {grupo})."
        else:
            if letiva > 1100:
                return "Acima 1100", f"Reduzir {letiva - 1100} min de LETIVA (máximo 1100)."
            elif letiva < 1100:
                rem = 1100 - letiva
                if rem >= 50:
                    need = rem - 49
                    return "Remanescente ≥ 50", f"Acrescentar {need} min de LETIVA para remanescente ≤ 49 min."
                else:
                    return "OK", f"Pode acrescentar até {49 - rem} min sem quebrar a regra do remanescente."
            else:
                return "OK", ""

    estados, dicas = zip(*carga_por_doc.apply(avaliar, axis=1)) if not carga_por_doc.empty else ([], [])
    if not carga_por_doc.empty:
        carga_por_doc["estado"] = estados
        carga_por_doc["sugestao"] = dicas
        st.dataframe(carga_por_doc[["docente_id","nome","grupo","letiva_min","alvo","estado","sugestao"]].sort_values(["estado","docente_id"]), use_container_width=True)

# ===============================
# Download / Upload distribuição
# ===============================
st.markdown("---")
c1, c2 = st.columns(2)
with c1:
    st.download_button("Descarregar distribuição (CSV)", out_df.to_csv(index=False).encode("utf-8"), "distribuicao_servico.csv", "text/csv")
with c2:
    up_dist = st.file_uploader("Repor distribuição a partir de CSV (turma_id,ciclo,ano,disciplina,docente_id)", type=["csv"], key="dist_up")
    if up_dist is not None:
        try:
            imp = read_csv_robust(up_dist, "dist.csv")
            needed = ["turma_id","ciclo","ano","disciplina","docente_id"]
            if imp is not None and all(c in imp.columns for c in needed):
                st.session_state.assignments = imp[needed].to_dict(orient="records")
                st.success("Distribuição carregada.")
            else:
                st.error("CSV inválido. Deve conter as colunas: " + ", ".join(needed))
        except Exception as e:
            st.error(f"Erro a ler CSV: {e}")

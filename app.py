
import streamlit as st
import pandas as pd
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
# ===============================
if "assignments" not in st.session_state:
    st.session_state.assignments = []

def assignments_df():
    if not st.session_state.assignments:
        return pd.DataFrame(columns=["turma_id","ciclo","ano","disciplina","docente_id"])
    return pd.DataFrame(st.session_state.assignments)

# ===============================
# Sidebar: Professores + filtros + Turmas
# ===============================
st.sidebar.markdown("### Professores")
# Filtros
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

# ===============================
# Main: Editor de atribuições por turma
# ===============================
st.title("Distribuição de Serviço — Atribuição por Tabela")

st.write(f"**Turma selecionada:** {turma_sel} — {ciclo_sel} ({ano_sel}º ano)")
ass = assignments_df()
mapa_doc = {r["id"]: f"{r['id']} — {r['nome']}" for _, r in docentes.iterrows()}
opcoes = [""] + list(mapa_doc.keys())

# construir tabela para a turma
t = pd.DataFrame({"disciplina": disciplinas_turma})
já = ass[ass["turma_id"]==turma_sel].set_index("disciplina")["docente_id"].to_dict()
t["docente_id"] = t["disciplina"].map(já).fillna("")

edited = st.data_editor(
    t,
    column_config={
        "docente_id": st.column_config.SelectboxColumn(
            "Docente",
            help="Escolha o docente responsável por esta disciplina",
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
            if did == "":
                continue
            novas.append({
                "turma_id": turma_sel,
                "ciclo": ciclo_sel,
                "ano": ano_sel,
                "disciplina": r["disciplina"],
                "docente_id": did
            })
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
    destinatario = st.selectbox("Atribuir TODAS as disciplinas da turma a…", options=cols, index=0, help="Substitui as atribuições atuais desta turma")
    if st.button("Aplicar atribuição total"):
        if destinatario != "":
            novas = [{
                "turma_id": turma_sel, "ciclo": ciclo_sel, "ano": ano_sel,
                "disciplina": d, "docente_id": destinatario
            } for d in disciplinas_turma]
            st.session_state.assignments = [r for r in st.session_state.assignments if r["turma_id"]!=turma_sel] + novas
            st.success(f"Todas as disciplinas da turma {turma_sel} atribuídas a {destinatario}.")
        else:
            st.warning("Escolha um docente.")

# ===============================
# Output tables
# ===============================
st.subheader("Atribuições atuais (todas as turmas)")
out_df = assignments_df().sort_values(["turma_id","disciplina"]).reset_index(drop=True)
st.dataframe(out_df, use_container_width=True)

st.subheader(f"{turma_sel}: Disciplinas e docente atribuído")
turma_matrix = pd.DataFrame({"disciplina": disciplinas_turma})
turma_matrix["docente_id"] = turma_matrix["disciplina"].map(
    out_df[out_df["turma_id"]==turma_sel].set_index("disciplina")["docente_id"].to_dict()
).fillna("")
st.dataframe(turma_matrix, use_container_width=True)

# ===============================
# Regras & contadores por docente
# ===============================
st.markdown("---")
st.header("Cargas por docente e conformidade de regras")
# obter carga por (ciclo, ano, disciplina) da matriz
mat_key = matriz[["ciclo","ano","disciplina","carga_sem_min"]].drop_duplicates()

if out_df.empty:
    st.info("Sem atribuições ainda.")
else:
    # juntar out_df com matriz para puxar minutos por disciplina
    rep = out_df.merge(mat_key, how="left", on=["ciclo","ano","disciplina"])
    rep["carga_sem_min"] = pd.to_numeric(rep["carga_sem_min"], errors="coerce").fillna(0).astype(int)
    carga_por_doc = rep.groupby("docente_id")["carga_sem_min"].sum().reset_index().rename(columns={"carga_sem_min":"letiva_min"})
    # anexar info do docente/grupo
    carga_por_doc = carga_por_doc.merge(docentes[["id","nome","grupo"]], left_on="docente_id", right_on="id", how="left")
    carga_por_doc["alvo"] = carga_por_doc["grupo"].astype(str).apply(lambda g: 1500 if g in ["100","110"] else 1100)
    # regras
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
    estados, dicas = zip(*carga_por_doc.apply(avaliar, axis=1))
    carga_por_doc["estado"] = estados
    carga_por_doc["sugestao"] = dicas

    st.dataframe(
        carga_por_doc[["docente_id","nome","grupo","letiva_min","alvo","estado","sugestao"]]
        .sort_values(["estado","docente_id"]),
        use_container_width=True
    )

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
            needed = ["turma_id","ciclo","ano","disciplina","docente_id"]
            if all(c in imp.columns for c in needed):
                st.session_state.assignments = imp[needed].to_dict(orient="records")
                st.success("Distribuição carregada.")
            else:
                st.error("CSV inválido. Deve conter as colunas: " + ", ".join(needed))
        except Exception as e:
            st.error(f"Erro a ler CSV: {e}")

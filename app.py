
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
    m = re.search(r"\d+", s)
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
modo = st.sidebar.radio("Modo de trabalho", options=["Por turma","Por docente","Por disciplina/ano","Resumo"], index=2)

# ===============================
# Por turma (igual ao build anterior)
# ===============================
if modo == "Por turma":
    st.title("Distribuição de Serviço — Por Turma")
    turma_sel = st.sidebar.selectbox("Selecionar turma", options=list(turmas["id"].astype(str)))
    turma_row = turmas[turmas["id"].astype(str)==str(turma_sel)].iloc[0]
    ciclo_sel, ano_sel = turma_row["ciclo"], turma_row["ano"]

    disciplinas_turma = matriz[(matriz["ciclo"]==ciclo_sel) & (matriz["ano"]==ano_sel)]["disciplina"].dropna().astype(str).tolist()
    if not disciplinas_turma:
        st.info("Não há disciplinas definidas na matriz para esta turma (ciclo+ano).")

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
            "docente_id": st.column_config.SelectboxColumn("Docente", options=opcoes, required=False)
        },
        use_container_width=True, hide_index=True, num_rows="fixed"
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

    st.subheader(f"{turma_sel}: Disciplinas e docente atribuído")
    out_df = assignments_df()
    turma_matrix = pd.DataFrame({"disciplina": disciplinas_turma})
    turma_matrix["docente_id"] = turma_matrix["disciplina"].map(out_df[out_df["turma_id"]==turma_sel].set_index("disciplina")["docente_id"].to_dict()).fillna("")
    st.dataframe(turma_matrix, use_container_width=True)

# ===============================
# Por docente (igual ao build anterior)
# ===============================
elif modo == "Por docente":
    st.title("Distribuição de Serviço — Por Docente")
    docentes_opts = docentes["id"].astype(str).tolist()
    docente_sel = st.sidebar.selectbox("Selecionar docente", options=docentes_opts)

    td = turmas.merge(matriz, how="left", on=["ciclo","ano"])
    td = td[["id","ciclo","ano","disciplina","carga_sem_min"]].dropna(subset=["disciplina"])
    td = td.rename(columns={"id":"turma_id"}).reset_index(drop=True)

    ass = assignments_df()
    ass_map = ass.set_index(["turma_id","disciplina"])["docente_id"].to_dict()
    td["atribuido_a"] = td.apply(lambda r: ass_map.get((str(r["turma_id"]), str(r["disciplina"])), ""), axis=1)

    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        filtro_turma = st.text_input("Filtrar por turma (contém)", "")
    with fcol2:
        filtro_ano = st.text_input("Filtrar por ano (ex.: 7, 10, Pré)", "")
    with fcol3:
        filtro_disc = st.text_input("Filtrar por disciplina (contém)", "")

    def contains(s, sub):
        if not sub: return True
        return sub.lower() in str(s).lower()

    view = td[td.apply(lambda r: contains(r["turma_id"], filtro_turma) and contains(r["ano"], filtro_ano) and contains(r["disciplina"], filtro_disc), axis=1)].copy()

    view["atribuir"] = view.apply(lambda r: r["atribuido_a"] == docente_sel, axis=1)
    edited = st.data_editor(
        view,
        column_config={
            "atribuir": st.column_config.CheckboxColumn("Atribuir ao docente selecionado"),
        },
        hide_index=True,
        use_container_width=True
    )

    if st.button("Guardar atribuições do docente", type="primary"):
        ass_new = ass.copy()
        to_keep = []
        for _, r in ass_new.iterrows():
            key = (r["turma_id"], r["disciplina"])
            match = edited[(edited["turma_id"]==r["turma_id"]) & (edited["disciplina"]==r["disciplina"])]
            if len(match)>0 and not bool(match.iloc[0]["atribuir"]) and r["docente_id"]==docente_sel:
                continue
            to_keep.append(r)
        ass_new = pd.DataFrame(to_keep) if to_keep else pd.DataFrame(columns=ass.columns)

        for _, r in edited.iterrows():
            if bool(r["atribuir"]):
                ass_new = ass_new[~((ass_new["turma_id"]==r["turma_id"]) & (ass_new["disciplina"]==r["disciplina"]))]
                ass_new = pd.concat([ass_new, pd.DataFrame([{
                    "turma_id": r["turma_id"],
                    "ciclo": r["ciclo"],
                    "ano": r["ano"],
                    "disciplina": r["disciplina"],
                    "docente_id": docente_sel
                }])], ignore_index=True)
        st.session_state.assignments = ass_new.to_dict(orient="records")
        st.success("Atribuições atualizadas.")

    st.subheader(f"Atribuições do docente {docente_sel}")
    ass_doc = assignments_df()
    st.dataframe(ass_doc[ass_doc["docente_id"]==docente_sel].sort_values(["turma_id","disciplina"]), use_container_width=True)

# ===============================
# Por disciplina/ano (novo modo)
# ===============================
elif modo == "Por disciplina/ano":
    st.title("Distribuição de Serviço — Por Disciplina/Ano")

    # opções de disciplina e ano com base na matriz
    disciplinas = sorted(matriz["disciplina"].dropna().astype(str).unique().tolist())
    anos = sorted(matriz["ano"].dropna().astype(str).unique().tolist())
    c1, c2, c3 = st.columns([2,1,2])
    with c1:
        disc_sel = st.selectbox("Escolher disciplina", options=disciplinas)
    with c2:
        ano_sel = st.selectbox("Escolher ano", options=anos)
    with c3:
        # Sugestão: opcional ciclo (derivado do cruzamento)
        ciclos = sorted(matriz.loc[matriz["disciplina"]==disc_sel, "ciclo"].dropna().astype(str).unique().tolist())
        ciclo_hint = st.selectbox("Ciclo (opcional)", options=["(auto)"] + ciclos, index=0)

    # construir todas as turmas que têm (disciplina, ano) — via join matriz+turmas
    msub = matriz[(matriz["disciplina"]==disc_sel) & (matriz["ano"]==ano_sel)]
    if ciclo_hint != "(auto)":
        msub = msub[msub["ciclo"]==ciclo_hint]
    tsub = turmas.merge(msub[["ciclo","ano","disciplina","carga_sem_min"]], how="inner", on=["ciclo","ano"])
    tsub = tsub[["id","ciclo","ano","disciplina","carga_sem_min"]].rename(columns={"id":"turma_id"}).reset_index(drop=True)

    ass = assignments_df()
    ass_map = ass.set_index(["turma_id","disciplina"])["docente_id"].to_dict()
    tsub["docente_id"] = tsub.apply(lambda r: ass_map.get((str(r["turma_id"]), str(r["disciplina"])), ""), axis=1)

    mapa_doc = {r["id"]: f"{r['id']} — {r['nome']}" for _, r in docentes.iterrows()}
    opcoes = [""] + list(mapa_doc.keys())

    edited = st.data_editor(
        tsub,
        column_config={
            "docente_id": st.column_config.SelectboxColumn("Docente", options=opcoes, required=False)
        },
        hide_index=True,
        use_container_width=True
    )

    cA, cB = st.columns([1,2])
    with cA:
        if st.button("Guardar atribuições (disciplina/ano)"):
            ass_new = ass[~((ass["disciplina"]==disc_sel) & (ass["ano"]==ano_sel))].copy() if ciclo_hint=="(auto)" else ass[~((ass["disciplina"]==disc_sel) & (ass["ano"]==ano_sel) & (ass["ciclo"]==ciclo_hint))].copy()
            for _, r in edited.iterrows():
                did = str(r["docente_id"]).strip()
                if did=="": 
                    # se vazio, remove linha específica (caso existisse)
                    ass_new = ass_new[~((ass_new["turma_id"]==r["turma_id"]) & (ass_new["disciplina"]==disc_sel))]
                    continue
                ass_new = ass_new[~((ass_new["turma_id"]==r["turma_id"]) & (ass_new["disciplina"]==disc_sel))]
                ass_new = pd.concat([ass_new, pd.DataFrame([{
                    "turma_id": r["turma_id"], "ciclo": r["ciclo"], "ano": r["ano"],
                    "disciplina": disc_sel, "docente_id": did
                }])], ignore_index=True)
            st.session_state.assignments = ass_new.to_dict(orient="records")
            st.success("Atribuições guardadas.")
    with cB:
        cols = [""] + docentes["id"].astype(str).tolist()
        dest_all = st.selectbox("Atribuir todas as turmas desta disciplina/ano a…", options=cols, index=0)
        if st.button("Aplicar atribuição total (disciplina/ano)"):
            if dest_all != "":
                ass_new = ass[~((ass["disciplina"]==disc_sel) & (ass["ano"]==ano_sel))].copy() if ciclo_hint=="(auto)" else ass[~((ass["disciplina"]==disc_sel) & (ass["ano"]==ano_sel) & (ass["ciclo"]==ciclo_hint))].copy()
                novas = [{
                    "turma_id": r["turma_id"], "ciclo": r["ciclo"], "ano": r["ano"],
                    "disciplina": disc_sel, "docente_id": dest_all
                } for _, r in edited.iterrows()]
                st.session_state.assignments = (pd.concat([ass_new, pd.DataFrame(novas)], ignore_index=True)).to_dict(orient="records")
                st.success(f"Todas as linhas de {disc_sel} ({ano_sel}) atribuídas a {dest_all}.")
            else:
                st.warning("Escolha um docente.")

# ===============================
# Resumo com badges (igual ao build anterior)
# ===============================
else:
    st.title("Resumo das Atribuições — com Badges")

    out_df = assignments_df()
    base = turmas.merge(matriz, how="left", on=["ciclo","ano"])
    base = base[["id","ciclo","ano","disciplina"]].dropna(subset=["disciplina"]).rename(columns={"id":"turma_id"})
    who = out_df.set_index(["turma_id","disciplina"])["docente_id"].to_dict()
    base["atribuido_a"] = base.apply(lambda r: who.get((str(r["turma_id"]), str(r["disciplina"])), ""), axis=1)
    base["estado"] = base["atribuido_a"].apply(lambda x: "Atribuída" if str(x).strip()!="" else "Por atribuir")

    tab1, tab2 = st.tabs(["Por ano de escolaridade","Por disciplina"])

    with tab1:
        st.subheader("Visão por ano de escolaridade")
        cts = base.groupby("ano").agg(
            total=("disciplina","count"),
            por_atribuir=("estado", lambda s: (s=="Por atribuir").sum())
        ).reset_index()
        st.markdown("**Badges:** *por atribuir / total*")
        cols = st.columns(len(cts)) if len(cts)>0 else []
        for col, (_, row) in zip(cols, cts.iterrows()):
            col.metric(label=f"Ano {row['ano']}", value=f"{int(row['por_atribuir'])}", delta=f"de {int(row['total'])}")

        anos = ["Todos"] + list(pd.unique(base["ano"]))
        ano_sel = st.selectbox("Filtrar ano", options=anos, index=0)
        view = base if ano_sel=="Todos" else base[base["ano"]==ano_sel]
        st.dataframe(view.sort_values(["ano","turma_id","disciplina"]), use_container_width=True)

    with tab2:
        st.subheader("Visão por disciplina")
        cts = base.groupby("disciplina").agg(
            total=("turma_id","count"),
            por_atribuir=("estado", lambda s: (s=="Por atribuir").sum())
        ).reset_index().sort_values("disciplina")
        st.markdown("**Badges:** *por atribuir / total*")
        for i in range(0, len(cts), 4):
            row = cts.iloc[i:i+4]
            cols = st.columns(len(row))
            for col, (_, r) in zip(cols, row.iterrows()):
                col.metric(label=str(r["disciplina"]), value=f"{int(r['por_atribuir'])}", delta=f"de {int(r['total'])}")
        dis = ["Todos"] + cts["disciplina"].astype(str).tolist()
        disc_sel = st.selectbox("Filtrar disciplina", options=dis, index=0)
        view = base if disc_sel=="Todos" else base[base["disciplina"]==disc_sel]
        st.dataframe(view.sort_values(["disciplina","turma_id"]), use_container_width=True)

# ===============================
# Cargas por docente e regras
# ===============================
st.markdown("---")
st.header("Cargas por docente e conformidade de regras")
out_df_all = assignments_df()
if out_df_all.empty:
    st.info("Sem atribuições ainda.")
else:
    mat_key = matriz[["ciclo","ano","disciplina","carga_sem_min"]].drop_duplicates()
    rep = out_df_all.merge(mat_key, how="left", on=["ciclo","ano","disciplina"])
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
    out_df = assignments_df()
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

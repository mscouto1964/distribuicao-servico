
import streamlit as st
import pandas as pd
import io, zipfile, re

st.set_page_config(page_title="Distribuição de Serviço Docente — Completa", layout="wide")

# ======================================================
# Robust CSV reader + header normalization + aliases
# ======================================================
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
                if df.shape[1] >= 1:
                    return df
            except Exception:
                continue
    return None

def normalize_cols(df):
    mapping = {}
    for c in df.columns:
        key = re.sub(r'[^a-z0-9]+','', str(c).strip().lower())
        mapping[c] = key
    return df.rename(columns=mapping)

ALIASES_DOC = {
    "id": ["id","docenteid","codigo","cod","iddocente","id_docente","num","numero","mecanografico"],
    "nome": ["nome","docente","professor","name"],
    "grupo": ["grupo","grupoderecrutamento","gr","codigo_grupo","grupo_codigo"],
    "reducao79_min": ["reducao79_min","reducao79","art79","artigo79","art79min","artigo79min","min79"],
}
ALIASES_TUR = {
    "id":["id","turma","cod","codigo"],
    "ciclo":["ciclo"],
    "ano":["ano","serie"],
    "curso":["curso","cursosigla","curso_sigla"],
    "n_alunos":["nalunos","alunos","n","numalunos"],
    "escola":["escola","estabelecimento"]
}
ALIASES_MAT = {
    "ciclo":["ciclo"],
    "ano":["ano"],
    "disciplina":["disciplina","disc","nome"],
    "carga_sem_min":["carga_sem_min","carga","min","min_sem","minsemanais"]
}
ALIASES_CAR = {
    "id":["id","codigo","cod"],
    "cargo":["cargo","funcao","função","designacao","descricao","descrição"],
    "carga_min":["carga_min","cargamin","carga","min","minutos"]
}

def apply_aliases(df, aliases):
    cols = set(df.columns)
    ren = {}
    for canon, alts in aliases.items():
        if canon in cols:
            continue
        for a in alts:
            if a in cols:
                ren[a] = canon
                break
    if ren:
        df = df.rename(columns=ren)
    return df

def ensure(df, cols_defaults: dict, label=""):
    for c, default in cols_defaults.items():
        if c not in df.columns:
            df[c] = default
    return df

def norm_ciclo(x):
    if pd.isna(x): return ""
    s=str(x).strip().lower()
    if s.startswith(("pré","pre")): return "Pré"
    if s.startswith("1"): return "1º"
    if s.startswith("2"): return "2º"
    if s.startswith("3"): return "3º"
    if s.startswith(("sec","secund")): return "Sec"
    return str(x)

def norm_ano(x):
    if pd.isna(x): return ""
    s=str(x).strip().lower()
    if s.startswith(("pré","pre")): return "Pré"
    m = re.search(r"\d+", s)
    return m.group(0) if m else str(x)

# ======================================================
# Session state
# ======================================================
if "assignments" not in st.session_state:
    st.session_state.assignments = []  # turmas/disciplinas -> docente
if "cargos_atr" not in st.session_state:
    st.session_state.cargos_atr = []   # cargos atribuídos (id,cargo,carga_min,docente_id,imputacao)
if "te_global" not in st.session_state:
    st.session_state.te_global = 150

def assignments_df():
    if not st.session_state.assignments:
        return pd.DataFrame(columns=["turma_id","ciclo","ano","disciplina","docente_id"])
    df = pd.DataFrame(st.session_state.assignments)
    if not df.empty:
        df["docente_id"] = df["docente_id"].astype(str)
    return df

def cargos_df():
    if not st.session_state.cargos_atr:
        return pd.DataFrame(columns=["id","cargo","carga_min","docente_id","imputacao"])
    df = pd.DataFrame(st.session_state.cargos_atr)
    if not df.empty:
        df["docente_id"] = df["docente_id"].astype(str)
        df["imputacao"] = df["imputacao"].astype(str).str.upper()
        df["carga_min"] = pd.to_numeric(df["carga_min"], errors="coerce").fillna(0).astype(int)
    return df

# ======================================================
# Uploads + modelos + TE + modo
# ======================================================
st.sidebar.header("Carregar dados")
up_doc = st.sidebar.file_uploader("docentes.csv", type=["csv"])
up_tur = st.sidebar.file_uploader("turmas.csv", type=["csv"])
up_mat = st.sidebar.file_uploader("matriz.csv", type=["csv"])
up_car = st.sidebar.file_uploader("cargos.csv", type=["csv"])

# modelos CSV
st.sidebar.markdown("### Modelos CSV")
st.sidebar.download_button("Modelo docentes.csv", "id,nome,grupo,reducao79_min\nD1,Ana Silva,510,0\nPre1,Carla,100,0\n", file_name="docentes.csv")
st.sidebar.download_button("Modelo turmas.csv", "id,ciclo,ano,curso,n_alunos,escola\n7A,3º,7,Reg,26,Sede\n10A,Sec,10,CH,28,Sede\n", file_name="turmas.csv")
st.sidebar.download_button("Modelo matriz.csv", "ciclo,ano,disciplina,carga_sem_min\n3º,7,Português,150\nSec,10,Física,150\nPré,Pré,At. Let.,1500\n", file_name="matriz.csv")
st.sidebar.download_button("Modelo cargos.csv", "id,cargo,carga_min\nC1,Diretor de Turma,45\nC2,Coord. Departamento,90\nC3,Adjunto Direção,150\n", file_name="cargos.csv")

# TE GLOBAL
st.sidebar.subheader("Configurações Globais")
st.session_state.te_global = st.sidebar.slider("Trabalho de Escola (TE) — global", 0, 150, st.session_state.te_global, step=5)

# Carregar/normalizar dados
if up_doc is not None:
    docentes = read_csv_robust(up_doc)
else:
    docentes = pd.DataFrame([{"id":"D1","nome":"Ana Silva","grupo":"510","reducao79_min":0},
                             {"id":"Pre1","nome":"Carla","grupo":"100","reducao79_min":0}])
docentes = normalize_cols(docentes)
docentes = apply_aliases(docentes, ALIASES_DOC)
docentes = ensure(docentes, {"id":"", "nome":"", "grupo":"", "reducao79_min":0}, "docentes")
docentes["id"] = docentes["id"].astype(str)
docentes["grupo"] = docentes["grupo"].astype(str)

if up_tur is not None:
    turmas = read_csv_robust(up_tur)
else:
    turmas = pd.DataFrame([{"id":"7A","ciclo":"3º","ano":"7","curso":"Reg","n_alunos":26,"escola":"Sede"},
                           {"id":"10A","ciclo":"Sec","ano":"10","curso":"CH","n_alunos":28,"escola":"Sede"}])
turmas = normalize_cols(turmas)
turmas = apply_aliases(turmas, ALIASES_TUR)
turmas = ensure(turmas, {"id":"", "ciclo":"", "ano":"", "curso":"", "n_alunos":0, "escola":""}, "turmas")
turmas["ciclo"] = turmas["ciclo"].map(norm_ciclo)
turmas["ano"] = turmas["ano"].map(norm_ano)
turmas["id"] = turmas["id"].astype(str)

if up_mat is not None:
    matriz = read_csv_robust(up_mat)
else:
    matriz = pd.DataFrame([{"ciclo":"3º","ano":"7","disciplina":"Português","carga_sem_min":150},
                           {"ciclo":"Sec","ano":"10","disciplina":"Física","carga_sem_min":150},
                           {"ciclo":"Pré","ano":"Pré","disciplina":"At. Let.","carga_sem_min":1500}])
matriz = normalize_cols(matriz)
matriz = apply_aliases(matriz, ALIASES_MAT)
matriz = ensure(matriz, {"ciclo":"", "ano":"", "disciplina":"", "carga_sem_min":0}, "matriz")
matriz["ciclo"] = matriz["ciclo"].map(norm_ciclo)
matriz["ano"] = matriz["ano"].map(norm_ano)
matriz["carga_sem_min"] = pd.to_numeric(matriz["carga_sem_min"], errors="coerce").fillna(0).astype(int)

if up_car is not None:
    cargos = read_csv_robust(up_car)
else:
    cargos = pd.DataFrame([{"id":"C1","cargo":"Diretor de Turma","carga_min":45},
                           {"id":"C2","cargo":"Coord. Departamento","carga_min":90}])
cargos = normalize_cols(cargos)
cargos = apply_aliases(cargos, ALIASES_CAR)
cargos = ensure(cargos, {"id":"", "cargo":"", "carga_min":0}, "cargos")
cargos["carga_min"] = pd.to_numeric(cargos["carga_min"], errors="coerce").fillna(0).astype(int)

# ======================================================
# Sidebar: lista de docentes e modo
# ======================================================
st.sidebar.markdown("### Professores")
grp_opts = ["Todos"] + sorted(docentes["grupo"].unique().tolist())
gsel = st.sidebar.selectbox("Filtrar por grupo", options=grp_opts, index=0)
q = st.sidebar.text_input("Pesquisa por nome/id","")
dv = docentes.copy()
if gsel!="Todos":
    dv = dv[dv["grupo"]==gsel]
if q.strip():
    ql = q.lower()
    dv = dv[dv.apply(lambda r: ql in str(r["nome"]).lower() or ql in str(r["id"]).lower(), axis=1)]
for _, r in dv.iterrows():
    st.sidebar.write(f"**{r['id']}** — {r['nome']} ({r['grupo']})")

st.sidebar.markdown("---")
modo = st.sidebar.radio("Modo de trabalho", ["Por turma","Por docente","Por disciplina/ano","Resumo","Cargos"], index=0)

# ======================================================
# Helper: calcular letiva por docente a partir das atribuições + cargos LETIVA
# ======================================================
def calc_letiva_por_docente(assign_df, matriz_df, cargos_df, docentes_df):
    # letiva por disciplinas
    if assign_df.empty:
        let_disc = pd.DataFrame(columns=["docente_id","letiva_from_disc_min"])
    else:
        mat_key = matriz_df[["ciclo","ano","disciplina","carga_sem_min"]].drop_duplicates()
        rep = assign_df.merge(mat_key, how="left", on=["ciclo","ano","disciplina"])
        rep["carga_sem_min"] = pd.to_numeric(rep["carga_sem_min"], errors="coerce").fillna(0).astype(int)
        let_disc = rep.groupby("docente_id")["carga_sem_min"].sum().reset_index().rename(columns={"carga_sem_min":"letiva_from_disc_min"})
    # letiva por cargos LETIVA
    if cargos_df.empty:
        let_car = pd.DataFrame(columns=["docente_id","letiva_from_cargos_min"])
    else:
        let_ct = cargos_df[cargos_df["imputacao"]=="LETIVA"].groupby("docente_id")["carga_min"].sum().reset_index().rename(columns={"carga_min":"letiva_from_cargos_min"})
        let_car = let_ct
    # base docentes
    base = docentes_df[["id","nome","grupo","reducao79_min"]].copy().rename(columns={"id":"docente_id"})
    base["docente_id"]=base["docente_id"].astype(str); base["grupo"]=base["grupo"].astype(str)
    base["reducao79_min"]=pd.to_numeric(base["reducao79_min"], errors="coerce").fillna(0).astype(int)
    # merge
    base = base.merge(let_disc, how="left", on="docente_id").merge(let_car, how="left", on="docente_id")
    base["letiva_from_disc_min"]=base["letiva_from_disc_min"].fillna(0).astype(int)
    base["letiva_from_cargos_min"]=base["letiva_from_cargos_min"].fillna(0).astype(int)
    base["letiva_total_min"]=base["letiva_from_disc_min"]+base["letiva_from_cargos_min"]
    return base

# ======================================================
# Pages
# ======================================================
if modo=="Por turma":
    st.title("Distribuição — Por Turma")
    turma_sel = st.selectbox("Selecionar turma", options=list(turmas["id"]))
    trow = turmas[turmas["id"]==turma_sel].iloc[0]
    ciclo_sel, ano_sel = trow["ciclo"], trow["ano"]
    disc_list = matriz[(matriz["ciclo"]==ciclo_sel) & (matriz["ano"]==ano_sel)]["disciplina"].dropna().astype(str).tolist()
    ass = assignments_df()
    ass_map = ass[ass["turma_id"]==turma_sel].set_index("disciplina")["docente_id"].to_dict()
    df = pd.DataFrame({"disciplina": disc_list})
    df["docente_id"] = df["disciplina"].map(ass_map).fillna("")
    sel_opts = [""] + list(docentes["id"].astype(str))
    edited = st.data_editor(df, column_config={
        "docente_id": st.column_config.SelectboxColumn("Docente", options=sel_opts)
    }, hide_index=True, use_container_width=True)
    c1,c2,c3 = st.columns([1,1,2])
    with c1:
        if st.button("Guardar turma"):
            new = assignments_df()
            new = new[new["turma_id"]!=turma_sel]
            lines = []
            for _, r in edited.iterrows():
                if str(r["docente_id"]).strip()!="":
                    lines.append({"turma_id":turma_sel,"ciclo":ciclo_sel,"ano":ano_sel,"disciplina":r["disciplina"],"docente_id":str(r["docente_id"])})
            if lines:
                new = pd.concat([new, pd.DataFrame(lines)], ignore_index=True)
            st.session_state.assignments = new.to_dict(orient="records")
            st.success("Turma guardada.")
    with c2:
        if st.button("Limpar turma"):
            st.session_state.assignments = [r for r in st.session_state.assignments if r["turma_id"]!=turma_sel]
            st.info("Atribuições removidas.")
    with c3:
        dest = st.selectbox("Atribuir todas as disciplinas a…", options=sel_opts, index=0)
        if st.button("Aplicar"):
            if dest!="":
                lines = [{"turma_id":turma_sel,"ciclo":ciclo_sel,"ano":ano_sel,"disciplina":d,"docente_id":dest} for d in disc_list]
                st.session_state.assignments = [r for r in st.session_state.assignments if r["turma_id"]!=turma_sel] + lines
                st.success("Atribuições efetuadas.")
            else:
                st.warning("Escolha um docente.")

elif modo=="Por docente":
    st.title("Distribuição — Por Docente")
    docente_sel = st.selectbox("Docente", options=list(docentes["id"].astype(str)))
    td = turmas.merge(matriz, how="left", on=["ciclo","ano"])
    td = td[["id","ciclo","ano","disciplina","carga_sem_min"]].dropna(subset=["disciplina"]).rename(columns={"id":"turma_id"})
    ass = assignments_df()
    amap = ass.set_index(["turma_id","disciplina"])["docente_id"].to_dict()
    td["atribuido_a"] = td.apply(lambda r: amap.get((r["turma_id"], r["disciplina"]),"") ,axis=1)
    td["atribuir"] = td["atribuido_a"]==docente_sel
    edited = st.data_editor(td, column_config={"atribuir": st.column_config.CheckboxColumn("Atribuir")}, hide_index=True, use_container_width=True)
    if st.button("Guardar atribuições do docente"):
        ass_new = ass.copy()
        # remove atribuições atuais do docente se desmarcadas
        to_keep=[]
        for _, r in ass_new.iterrows():
            key = (r["turma_id"], r["disciplina"])
            m = edited[(edited["turma_id"]==r["turma_id"]) & (edited["disciplina"]==r["disciplina"])]
            if len(m)>0 and not bool(m.iloc[0]["atribuir"]) and r["docente_id"]==docente_sel:
                continue
            to_keep.append(r)
        ass_new = pd.DataFrame(to_keep) if to_keep else pd.DataFrame(columns=ass.columns)
        # add marcadas
        for _, r in edited.iterrows():
            if bool(r["atribuir"]):
                ass_new = ass_new[~((ass_new["turma_id"]==r["turma_id"]) & (ass_new["disciplina"]==r["disciplina"]))]
                ass_new = pd.concat([ass_new, pd.DataFrame([{
                    "turma_id": r["turma_id"], "ciclo": r["ciclo"], "ano": r["ano"],
                    "disciplina": r["disciplina"], "docente_id": docente_sel
                }])], ignore_index=True)
        st.session_state.assignments = ass_new.to_dict(orient="records")
        st.success("Atribuições guardadas.")

elif modo=="Por disciplina/ano":
    st.title("Distribuição — Por Disciplina/Ano")
    disc_sel = st.selectbox("Disciplina", options=sorted(matriz["disciplina"].unique().tolist()))
    ano_sel = st.selectbox("Ano", options=sorted(matriz["ano"].unique().tolist()))
    ciclos = ["(auto)"] + sorted(matriz.loc[matriz["disciplina"]==disc_sel, "ciclo"].unique().tolist())
    ciclo_hint = st.selectbox("Ciclo (opcional)", options=ciclos, index=0)
    msub = matriz[(matriz["disciplina"]==disc_sel) & (matriz["ano"]==ano_sel)]
    if ciclo_hint!="(auto)":
        msub = msub[msub["ciclo"]==ciclo_hint]
    tsub = turmas.merge(msub[["ciclo","ano","disciplina","carga_sem_min"]], how="inner", on=["ciclo","ano"]) \
                 .rename(columns={"id":"turma_id"})[["id","ciclo","ano","disciplina","carga_sem_min"]]
    tsub = tsub.rename(columns={"id":"turma_id"})
    amap = assignments_df().set_index(["turma_id","disciplina"])["docente_id"].to_dict()
    tsub["docente_id"] = tsub.apply(lambda r: amap.get((r["turma_id"], r["disciplina"]),"") ,axis=1)
    sel = [""] + list(docentes["id"].astype(str))
    edited = st.data_editor(tsub, column_config={"docente_id": st.column_config.SelectboxColumn("Docente", options=sel)}, hide_index=True, use_container_width=True)
    c1,c2 = st.columns([1,2])
    with c1:
        if st.button("Guardar atribuições (disciplina/ano)"):
            ass = assignments_df()
            if ciclo_hint=="(auto)":
                ass_new = ass[~((ass["disciplina"]==disc_sel)&(ass["ano"]==ano_sel))].copy()
            else:
                ass_new = ass[~((ass["disciplina"]==disc_sel)&(ass["ano"]==ano_sel)&(ass["ciclo"]==ciclo_hint))].copy()
            for _, r in edited.iterrows():
                did = str(r["docente_id"]).strip()
                if did=="":
                    continue
                ass_new = pd.concat([ass_new, pd.DataFrame([{
                    "turma_id": r["turma_id"], "ciclo": r["ciclo"], "ano": r["ano"],
                    "disciplina": r["disciplina"], "docente_id": did
                }])], ignore_index=True)
            st.session_state.assignments = ass_new.to_dict(orient="records")
            st.success("Guardado.")
    with c2:
        dest = st.selectbox("Atribuir todas a…", options=sel, index=0)
        if st.button("Aplicar atribuição total"):
            if dest!="":
                ass = assignments_df()
                if ciclo_hint=="(auto)":
                    ass_new = ass[~((ass["disciplina"]==disc_sel)&(ass["ano"]==ano_sel))].copy()
                else:
                    ass_new = ass[~((ass["disciplina"]==disc_sel)&(ass["ano"]==ano_sel)&(ass["ciclo"]==ciclo_hint))].copy()
                novas = [{
                    "turma_id": r["turma_id"], "ciclo": r["ciclo"], "ano": r["ano"],
                    "disciplina": r["disciplina"], "docente_id": dest
                } for _, r in edited.iterrows()]
                st.session_state.assignments = (pd.concat([ass_new, pd.DataFrame(novas)], ignore_index=True)).to_dict(orient="records")
                st.success("Aplicado.")
            else:
                st.warning("Escolha um docente.")

elif modo=="Resumo":
    st.title("Resumo — Badges por ano e disciplina")
    out_df = assignments_df()
    base = turmas.merge(matriz, how="left", on=["ciclo","ano"])[["id","ciclo","ano","disciplina"]].dropna(subset=["disciplina"]).rename(columns={"id":"turma_id"})
    who = out_df.set_index(["turma_id","disciplina"])["docente_id"].to_dict()
    base["atribuido_a"] = base.apply(lambda r: who.get((r["turma_id"], r["disciplina"]),"") ,axis=1)
    base["estado"] = base["atribuido_a"].apply(lambda x: "Atribuída" if str(x).strip()!="" else "Por atribuir")
    tab1, tab2 = st.tabs(["Por ano","Por disciplina"])
    with tab1:
        cts = base.groupby("ano").agg(total=("disciplina","count"), por_atribuir=("estado", lambda s: (s=="Por atribuir").sum())).reset_index()
        st.markdown("**Badges:** *por atribuir / total*")
        cols = st.columns(len(cts)) if len(cts)>0 else []
        for col, (_, r) in zip(cols, cts.iterrows()):
            col.metric(label=f"Ano {r['ano']}", value=int(r['por_atribuir']), delta=f"de {int(r['total'])}")
        ano_sel = st.selectbox("Filtrar ano", options=["Todos"]+list(cts["ano"]), index=0)
        view = base if ano_sel=="Todos" else base[base["ano"]==ano_sel]
        st.dataframe(view.sort_values(["ano","turma_id","disciplina"]), use_container_width=True)
    with tab2:
        cts = base.groupby("disciplina").agg(total=("turma_id","count"), por_atribuir=("estado", lambda s: (s=="Por atribuir").sum())).reset_index()
        for i in range(0, len(cts), 4):
            row = cts.iloc[i:i+4]
            cols = st.columns(len(row))
            for col, (_, r) in zip(cols, row.iterrows()):
                col.metric(label=r["disciplina"], value=int(r["por_atribuir"]), delta=f"de {int(r['total'])}")
        disc_sel = st.selectbox("Filtrar disciplina", options=["Todos"]+list(cts["disciplina"]), index=0)
        view = base if disc_sel=="Todos" else base[base["disciplina"]==disc_sel]
        st.dataframe(view.sort_values(["disciplina","turma_id"]), use_container_width=True)

else:  # CARGOS
    st.title("Gestão de Cargos")
    st.caption("Atribua cargos e escolha imputação (LETIVA / ART79 / TE).")
    base = cargos.copy()
    if "docente_id" not in base.columns: base["docente_id"]=""
    if "imputacao" not in base.columns: base["imputacao"]="LETIVA"
    sel = [""] + list(docentes["id"].astype(str))
    edited = st.data_editor(base[["id","cargo","carga_min","docente_id","imputacao"]],
        column_config={
            "docente_id": st.column_config.SelectboxColumn("Docente", options=sel),
            "imputacao": st.column_config.SelectboxColumn("Imputação", options=["LETIVA","ART79","TE"]),
            "carga_min": st.column_config.NumberColumn("Carga (min)", min_value=0, step=5),
        }, hide_index=True, use_container_width=True)
    c1,c2 = st.columns(2)
    with c1:
        if st.button("Guardar cargos"):
            st.session_state.cargos_atr = edited.to_dict(orient="records")
            st.success("Cargos guardados.")
    with c2:
        if st.button("Limpar cargos"):
            st.session_state.cargos_atr = []
            st.info("Atribuições de cargos limpas.")
    st.subheader("Cargos atribuídos (atual)")
    st.dataframe(cargos_df(), use_container_width=True)

# ======================================================
# Cargas por docente + Semáforo
# ======================================================
st.markdown("---")
st.header("Cargas por docente, regras e semáforo (inclui cargos)")

assign_all = assignments_df()
cargos_all = cargos_df()

base_c = calc_letiva_por_docente(assign_all, matriz, cargos_all, docentes)
# Art79 total = base (reducao79_min) + cargos imputados ART79
art79_extra = cargos_all[cargos_all["imputacao"]=="ART79"].groupby("docente_id")["carga_min"].sum().reset_index().rename(columns={"carga_min":"art79_from_cargos_min"}) if not cargos_all.empty else pd.DataFrame(columns=["docente_id","art79_from_cargos_min"])
base_c = base_c.merge(art79_extra, how="left", on="docente_id")
base_c["art79_from_cargos_min"]=base_c["art79_from_cargos_min"].fillna(0).astype(int)
base_c["art79_total_min"]=base_c["reducao79_min"]+base_c["art79_from_cargos_min"]
# TE total = TE global + cargos TE
te_extra = cargos_all[cargos_all["imputacao"]=="TE"].groupby("docente_id")["carga_min"].sum().reset_index().rename(columns={"carga_min":"te_from_cargos_min"}) if not cargos_all.empty else pd.DataFrame(columns=["docente_id","te_from_cargos_min"])
base_c = base_c.merge(te_extra, how="left", on="docente_id")
base_c["te_from_cargos_min"]=base_c["te_from_cargos_min"].fillna(0).astype(int)
base_c["te_total_min"]=int(st.session_state.te_global)+base_c["te_from_cargos_min"]

# Alvos letiva por grupo
base_c["alvo_letiva_min"]=base_c["grupo"].apply(lambda g: 1500 if g in ["100","110"] else 1100)

def avaliar_estado(row):
    letiva = int(row["letiva_total_min"])
    grupo = str(row["grupo"])
    if letiva == 0: return "🔴","Sem componente letiva"
    if grupo in ["100","110"]:
        return ("🟢","Completa (1500 + TE)") if letiva==1500 else ("🟡","Em preenchimento")
    else:
        if letiva>1100: return "🟡", f"Acima de 1100 (+{letiva-1100})"
        rem = 1100 - letiva
        return ("🟢","Completa (remanescente <50 + TE)") if rem<50 else ("🟡","Em preenchimento")

base_c[["semaforo","estado"]] = base_c.apply(lambda r: pd.Series(avaliar_estado(r)), axis=1)

st.dataframe(
    base_c[["docente_id","nome","grupo","letiva_total_min","alvo_letiva_min","art79_total_min","te_total_min","semaforo","estado"]]
    .sort_values("docente_id"),
    use_container_width=True
)

# ======================================================
# CRÉDITO (nova fórmula) + métricas na sidebar
# ======================================================
# nº de turmas dos ciclos 1º, 2º, 3º e Sec
turmas_valid = turmas[turmas["ciclo"].isin(["1º","2º","3º","Sec"])]
n_turmas = int(turmas_valid["id"].nunique())

# total Art79 em "minutos equivalentes": soma por docente;
# regra: grupos 100/110 dividem por 60; restantes dividem por 50; depois somar e multiplicar por 1 (já está em 'unidades'); depois *0.5
# Primeiro, art79_total_min já inclui cargos imputados ART79
g100 = base_c[base_c["grupo"].isin(["100","110"])]["art79_total_min"].sum() / 60.0
g_others = base_c[~base_c["grupo"].isin(["100","110"])]["art79_total_min"].sum() / 50.0
credito_total = 7 * n_turmas - 0.5 * (g100 + g_others)

# Gasto: cargos imputados a LETIVA em unidades (min/60)
credito_gasto = 0.0
if not cargos_all.empty:
    credito_gasto = cargos_all[cargos_all["imputacao"]=="LETIVA"]["carga_min"].sum() / 60.0
credito_restante = credito_total - credito_gasto

st.sidebar.markdown("---")
st.sidebar.subheader("Crédito (nova fórmula)")
st.sidebar.metric("Turmas (1º/2º/3º/Sec)", n_turmas)
st.sidebar.metric("Crédito — total", round(credito_total,2))
st.sidebar.metric("Crédito — gasto (cargos LETIVA)", round(credito_gasto,2))
st.sidebar.metric("Crédito — restante", round(credito_restante,2))

# ======================================================
# Export / Import
# ======================================================
st.markdown("---")
c1,c2,c3 = st.columns(3)
with c1:
    dist_csv = assignments_df().to_csv(index=False).encode("utf-8")
    st.download_button("Descarregar distribuição (CSV)", dist_csv, "distribuicao_servico.csv", "text/csv")
with c2:
    up_dist = st.file_uploader("Repor distribuição (CSV)", type=["csv"], key="up_dist")
    if up_dist is not None:
        imp = read_csv_robust(up_dist)
        need = {"turma_id","ciclo","ano","disciplina","docente_id"}
        if imp is not None and need.issubset(set(normalize_cols(imp).columns)):
            imp = normalize_cols(imp)
            st.session_state.assignments = imp[list(need)].to_dict(orient="records")
            st.success("Distribuição reposta.")
        else:
            st.error("CSV inválido para distribuição.")
with c3:
    cargos_csv = cargos_df().to_csv(index=False).encode("utf-8")
    st.download_button("Descarregar cargos atribuídos (CSV)", cargos_csv, "cargos_atribuidos.csv", "text/csv")


import streamlit as st
import pandas as pd
import io, re

st.set_page_config(page_title="Distribuição de Serviço Docente — Cargos (robusto)", layout="wide")

# =========================
# Robust CSV loader + column normalization
# =========================
def read_csv_robust(file_or_bytes):
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
    df = df.rename(columns=mapping)
    return df

ALIASES_DOCENTES = {
    "id": ["id","docenteid","codigo","cod","id_docente","iddocente","num","numero","nº","mecanografico"],
    "nome": ["nome","docente","professor","name"],
    "grupo": ["grupo","grupoderecrutamento","gr","grupo_codigo","codigo_grupo"],
    "reducao79_min": ["reducao79_min","reducao79","art79","artigo79","art79min","artigo79min","min79"],
}
ALIASES_CARGOS = {
    "id": ["id","codigo","cod"],
    "cargo": ["cargo","funcao","função","designacao","descricao","descrição"],
    "carga_min": ["cargamin","carga","min","minutos","cargasemana","cargasemanal"],
}

def apply_aliases(df, aliases):
    cols = set(df.columns)
    new_names = {}
    for canonical, choices in aliases.items():
        found = None
        for a in choices:
            if a in cols:
                found = a
                break
        if found and found != canonical:
            new_names[found] = canonical
    if new_names:
        df = df.rename(columns=new_names)
    return df

def ensure_columns(df, required, fallback_by_position=None, label=""):
    missing = [c for c in required if c not in df.columns]
    if missing and fallback_by_position:
        for i, cname in fallback_by_position.items():
            if 0 <= i < df.shape[1] and cname in missing:
                df[cname] = df.iloc[:, i]
        missing = [c for c in required if c not in df.columns]
    if missing:
        st.warning(f"{label}: faltam colunas {missing}. Verifique o cabeçalho do CSV.")
    return df

# =========================
# Estado global
# =========================
if "cargos_atr" not in st.session_state:
    st.session_state.cargos_atr = []  # lista de dicts: id,cargo,carga_min,docente_id,imputacao
if "te_global" not in st.session_state:
    st.session_state.te_global = 150
if "credito_total" not in st.session_state:
    st.session_state.credito_total = 500

# =========================
# Sidebar uploads + modelos
# =========================
st.sidebar.header("Carregar ficheiros")
up_doc = st.sidebar.file_uploader("docentes.csv", type=["csv"])
up_car = st.sidebar.file_uploader("cargos.csv", type=["csv"])

st.sidebar.markdown("### Descarregar modelos")
st.sidebar.download_button("Modelo docentes.csv",
    "id,nome,grupo,reducao79_min\nD1,Ana Silva,510,0\nD2,Bruno Sousa,520,0\nPre1,Carla Reis,100,0\n",
    file_name="docentes.csv")
st.sidebar.download_button("Modelo cargos.csv",
    "id,cargo,carga_min\nC1,Diretor de Turma,45\nC2,Coordenador de Departamento,90\nC3,Adjunto de Direção,150\n",
    file_name="cargos.csv")

st.sidebar.subheader("Configurações Globais")
st.session_state.te_global = st.sidebar.slider("Trabalho de Escola (TE) — global", 0, 150, st.session_state.te_global, step=5)
st.session_state.credito_total = st.sidebar.number_input("Crédito LETIVA total (min)", value=st.session_state.credito_total, step=10)

# =========================
# Carregar dados (com robustez)
# =========================
if up_doc is not None:
    docentes = read_csv_robust(up_doc)
else:
    docentes = pd.DataFrame([{"id":"D1","nome":"Ana Silva","grupo":"510","reducao79_min":0}])

docentes = normalize_cols(docentes)
docentes = apply_aliases(docentes, ALIASES_DOCENTES)
docentes = ensure_columns(docentes, ["id","nome","grupo","reducao79_min"], {0:"id",1:"nome"}, label="docentes.csv")

if up_car is not None:
    cargos = read_csv_robust(up_car)
else:
    cargos = pd.DataFrame([
        {"id":"C1","cargo":"Diretor de Turma","carga_min":45},
        {"id":"C2","cargo":"Coordenador de Departamento","carga_min":90},
    ])

cargos = normalize_cols(cargos)
cargos = apply_aliases(cargos, ALIASES_CARGOS)
cargos = ensure_columns(cargos, ["id","cargo","carga_min"], {0:"id",1:"cargo",2:"carga_min"}, label="cargos.csv")

# =========================
# Gestão de Cargos
# =========================
st.title("Gestão de Cargos")
st.caption("Atribua cargos aos docentes e escolha a imputação (LETIVA / ART79 / TE).")

docentes_ids = docentes["id"] if "id" in docentes.columns else docentes.iloc[:,0]
docentes_ids = [""] + list(docentes_ids.astype(str).unique())

edit_cols = ["id","cargo","carga_min","docente_id","imputacao"]
base = cargos.copy()
if "docente_id" not in base.columns:
    base["docente_id"] = ""
if "imputacao" not in base.columns:
    base["imputacao"] = "LETIVA"

edited = st.data_editor(
    base[["id","cargo","carga_min","docente_id","imputacao"]],
    column_config={
        "docente_id": st.column_config.SelectboxColumn("Docente", options=docentes_ids),
        "imputacao": st.column_config.SelectboxColumn("Imputação", options=["LETIVA","ART79","TE"]),
        "carga_min": st.column_config.NumberColumn("Carga (min)", min_value=0, step=5),
    },
    hide_index=True,
    use_container_width=True
)

c1, c2 = st.columns(2)
with c1:
    if st.button("Guardar cargos atribuídos", type="primary"):
        st.session_state.cargos_atr = edited.to_dict(orient="records")
        st.success("Cargos guardados.")
with c2:
    if st.button("Limpar atribuições de cargos"):
        st.session_state.cargos_atr = []
        st.info("Atribuições de cargos limpas.")

atr = pd.DataFrame(st.session_state.cargos_atr) if st.session_state.cargos_atr else pd.DataFrame(columns=edit_cols)
st.subheader("Cargos atribuídos (estado atual)")
st.dataframe(atr, use_container_width=True)

# =========================
# Crédito LETIVA: total, gasto, restante
# =========================
gasto_letiva = 0
if not atr.empty:
    tmp = atr.copy()
    tmp["carga_min"] = pd.to_numeric(tmp["carga_min"], errors="coerce").fillna(0).astype(int)
    gasto_letiva = tmp[tmp["imputacao"]=="LETIVA"]["carga_min"].sum()

st.sidebar.metric("Crédito LETIVA — total", st.session_state.credito_total)
st.sidebar.metric("Crédito LETIVA — gasto (cargos LETIVA)", int(gasto_letiva))
st.sidebar.metric("Crédito LETIVA — restante", int(st.session_state.credito_total - gasto_letiva))

# =========================
# Cargas por docente (efeito dos cargos)
# =========================
st.markdown("---")
st.header("Cargas por docente (inclui cargos)")
res = docentes.copy()
res["letiva_atr_min"] = 0
res["art79_min"] = pd.to_numeric(res.get("reducao79_min", 0), errors="coerce").fillna(0).astype(int)
res["te_min"] = int(st.session_state.te_global)

if not atr.empty:
    for _, r in atr.iterrows():
        did = str(r.get("docente_id","")).strip()
        carga = int(pd.to_numeric(r.get("carga_min",0), errors="coerce"))
        imp = str(r.get("imputacao","LETIVA")).upper()
        if did == "" or carga == 0: 
            continue
        mask = res["id"].astype(str) == did if "id" in res.columns else res.iloc[:,0].astype(str) == did
        if imp == "LETIVA":
            res.loc[mask, "letiva_atr_min"] += carga
        elif imp == "ART79":
            res.loc[mask, "art79_min"] += carga
        elif imp == "TE":
            res.loc[mask, "te_min"] += carga

res = res.rename(columns={"reducao79_min":"reducao79_base_min"})
st.dataframe(res[["id","nome","grupo","letiva_atr_min","reducao79_base_min","art79_min","te_min"]], use_container_width=True)

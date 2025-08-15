
import streamlit as st
import pandas as pd
import zipfile, io

st.set_page_config(page_title="Distribuição de Serviço Docente", layout="wide")

# ---------------------------
# Config Sidebar
# ---------------------------
st.sidebar.header("Configuração")
UNID_MIN = st.sidebar.number_input("Minutos por unidade letiva (aplica-se ao 2º, 3º e Sec.)", 45, 90, 50, 5)
TEIP = st.sidebar.checkbox("Agrupamento TEIP?", value=False)
MAX_TURNOS_DIA = 2
NLET_EST_MIN = st.sidebar.slider("Mínimo de NLet Est. (0–150 min/sem)", 0, 150, 90)
NLET_EST_CAP = 150  # CAP legal máximo

st.sidebar.info("Nota: No Pré-escolar e 1º ciclo, os tempos são **sempre de 60 minutos** e a letiva-alvo é 1500 min.")

st.sidebar.markdown("---")
st.sidebar.header("Dados")
st.sidebar.caption("Carregue um ZIP com docentes.csv, turmas.csv, funcoes.csv, horarios.csv (e opcionalmente matriz.csv) **ou** envie cada CSV individualmente.")

# ---------------------------
# Helpers
# ---------------------------
REQUIRED_SCHEMAS = {
    "docentes": ["id","nome","grupo","reducao79_min"],
    "turmas": ["id","ciclo","curso","n_alunos","escola"],
    "funcoes": ["docente_id","tipo","horas_sem"],
    "horarios": ["docente_id","dia","inicio","fim","tipo","local","turma_id","disciplina"],
}
OPTIONAL_SCHEMAS = {
    "matriz": ["ciclo","disciplina","carga_sem_min"]
}

def normalize_ciclo(x: str):
    if not isinstance(x, str): return ""
    t = x.strip().lower()
    if t.startswith("pré") or t.startswith("pre"): return "Pré"
    if t.startswith("1"): return "1º"
    if "1.º" in t or "1º" in t: return "1º"
    if t.startswith("2"): return "2º"
    if t.startswith("3"): return "3º"
    if t.startswith("sec") or "secund" in t: return "Sec"
    return x

def load_default_data():
    turmas_default = pd.DataFrame([
        {"id":"JI-A","ciclo":"Pré","curso":"Reg","n_alunos":20,"escola":"JI"},
        {"id":"1A","ciclo":"1º","curso":"Reg","n_alunos":24,"escola":"EB1"},
        {"id":"7A","ciclo":"3º","curso":"Reg","n_alunos":26,"escola":"Sede"},
        {"id":"10ºA","ciclo":"Sec","curso":"CH","n_alunos":28,"escola":"Sede"},
    ])
    docentes_default = pd.DataFrame([
        {"id":"D1","nome":"Ana Silva","grupo":"110","reducao79_min":0},
        {"id":"D2","nome":"Bruno Sousa","grupo":"510","reducao79_min":110},
        {"id":"D3","nome":"Carla Pinto","grupo":"100","reducao79_min":0},
    ])
    funcoes_default = pd.DataFrame([
        {"docente_id":"D1","tipo":"DT","horas_sem":4},
    ])
    horarios_default = pd.DataFrame([
        {"docente_id":"D3","dia":"2ª","inicio":"09:00","fim":"10:00","tipo":"LETIVA","local":"JI","turma_id":"JI-A","disciplina":"Atividades Pré"},
        {"docente_id":"D3","dia":"2ª","inicio":"10:00","fim":"11:00","tipo":"LETIVA","local":"JI","turma_id":"JI-A","disciplina":"Atividades Pré"},
        {"docente_id":"D1","dia":"2ª","inicio":"08:30","fim":"10:10","tipo":"LETIVA","local":"EB1","turma_id":"1A","disciplina":"Português"}, # 100 min -> deverá alertar
        {"docente_id":"D1","dia":"4ª","inicio":"14:00","fim":"15:40","tipo":"NLET_EST","local":"EB1","turma_id":"1A","disciplina":""},
        {"docente_id":"D2","dia":"2ª","inicio":"08:30","fim":"10:10","tipo":"LETIVA","local":"Sede","turma_id":"7A","disciplina":"FQ"},
        {"docente_id":"D2","dia":"2ª","inicio":"14:00","fim":"15:40","tipo":"LETIVA","local":"Sede","turma_id":"10ºA","disciplina":"Física"},
    ])
    matriz_default = pd.DataFrame([
        {"ciclo":"1º","disciplina":"Português","carga_sem_min":300},
        {"ciclo":"3º","disciplina":"FQ","carga_sem_min":150},
        {"ciclo":"Sec","disciplina":"Física","carga_sem_min":150},
    ])
    return docentes_default, turmas_default, funcoes_default, horarios_default, matriz_default

def validate_schema(df: pd.DataFrame, name: str, optional=False):
    required = (OPTIONAL_SCHEMAS if optional else REQUIRED_SCHEMAS)[name]
    missing = [c for c in required if c not in df.columns]
    return missing

def min_between(h1, h2):
    try:
        h1h, h1m = map(int, str(h1).split(":")); h2h, h2m = map(int, str(h2).split(":"))
        return (h2h*60+h2m) - (h1h*60+h1m)
    except Exception:
        return 0

def read_csv_bytes(file):
    try:
        return pd.read_csv(file)
    except Exception as e:
        st.error(f"Erro ao ler CSV ({getattr(file, 'name', 'upload')}): {e}")
        return None

def load_from_zip(zip_bytes):
    datasets = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as z:
            for key in list(REQUIRED_SCHEMAS.keys()) + list(OPTIONAL_SCHEMAS.keys()):
                candidates = [f"{key}.csv", f"{key}.CSV"]
                member = next(
                    (n for n in z.namelist()
                     if n in candidates
                     or n.endswith(f"/{key}.csv")
                     or n.endswith(f"/{key}.CSV")),
                    None
                )
                if member:
                    with z.open(member) as f:
                        datasets[key] = pd.read_csv(f)
    except Exception as e:
        st.error(f"Erro ao ler ZIP: {e}")
    return datasets

# ---------------------------
# Data Loading UI
# ---------------------------
zip_upload = st.file_uploader("ZIP com docentes.csv, turmas.csv, funcoes.csv, horarios.csv (e opcionalmente matriz.csv)", type=["zip"])

uploaded = {}
if zip_upload is not None:
    uploaded.update(load_from_zip(zip_upload.read()))

col1, col2 = st.columns(2)
with col1:
    up_docentes = st.file_uploader("docentes.csv", type=["csv"], key="docentes_up")
    up_turmas   = st.file_uploader("turmas.csv", type=["csv"], key="turmas_up")
    up_matriz   = st.file_uploader("matriz.csv (opcional)", type=["csv"], key="matriz_up")
with col2:
    up_funcoes  = st.file_uploader("funcoes.csv", type=["csv"], key="funcoes_up")
    up_horarios = st.file_uploader("horarios.csv", type=["csv"], key="horarios_up")

if up_docentes: uploaded["docentes"] = read_csv_bytes(up_docentes)
if up_turmas:   uploaded["turmas"]   = read_csv_bytes(up_turmas)
if up_funcoes:  uploaded["funcoes"]  = read_csv_bytes(up_funcoes)
if up_horarios: uploaded["horarios"] = read_csv_bytes(up_horarios)
if up_matriz:   uploaded["matriz"]   = read_csv_bytes(up_matriz)

# Defaults
docentes_default, turmas_default, funcoes_default, horarios_default, matriz_default = load_default_data()

docentes = uploaded.get("docentes", docentes_default)
turmas   = uploaded.get("turmas", turmas_default)
funcoes  = uploaded.get("funcoes", funcoes_default)
horarios = uploaded.get("horarios", horarios_default)
matriz   = uploaded.get("matriz", matriz_default)

# Normalize ciclo values
if "ciclo" in turmas.columns:
    turmas["ciclo"] = turmas["ciclo"].map(normalize_ciclo)

# Validate schemas
problems = []
for name, df in [("docentes", docentes), ("turmas", turmas), ("funcoes", funcoes), ("horarios", horarios)]:
    if df is None:
        problems.append(f"{name}: ficheiro inválido.")
        continue
    missing = validate_schema(df, name)
    if missing:
        problems.append(f"{name}.csv: faltam colunas {missing}")

# Matriz is optional but if provided check schema
if matriz is not None:
    miss_m = validate_schema(matriz, "matriz", optional=True)
    if miss_m:
        problems.append(f"matriz.csv: faltam colunas {miss_m}")

with st.expander("Pré-visualização dos dados carregados"):
    st.write("**docentes**", docentes.head())
    st.write("**turmas**", turmas.head())
    st.write("**funcoes**", funcoes.head())
    st.write("**horarios**", horarios.head())
    if matriz is not None:
        st.write("**matriz**", matriz.head())

if problems:
    st.error("⚠️ Problemas nos ficheiros:")
    for p in problems:
        st.write("- ", p)
    st.stop()

# Index for lookups
turma_ciclo = turmas.set_index("id")["ciclo"].to_dict()

# ---------------------------
# Crédito Horário
# ---------------------------
n_turmas = len(turmas)
horas79_total = docentes["reducao79_min"].sum() / 60.0
CH_calc = (10 if TEIP else 7)*n_turmas - 0.5*horas79_total

# DT: mínimo 2h em CH (simplificação)
dt_horas = funcoes.query("tipo=='DT'")["horas_sem"].sum() if not funcoes.empty else 0
ch_usado = max(0, dt_horas*0.5)
ch_saldo = CH_calc - ch_usado

# ---------------------------
# Validações por docente
# ---------------------------
def validar_docente(df_hor, docente_row):
    df = df_hor[df_hor["docente_id"]==docente_row["id"]].copy()
    if df.empty:
        return {"alvo_min":None,"letiva_h":0,"nlet_est_h":0,"nlet_ind_h":0,"total_h":0,"issues":["Sem horário atribuído"],"fixes":[]}

    # Durations
    df["min"] = df.apply(lambda r: min_between(r["inicio"], r["fim"]), axis=1)
    # Ciclo por registo
    df["ciclo"] = df["turma_id"].map(lambda t: turma_ciclo.get(t, ""))

    letiva_min = df.loc[df["tipo"]=="LETIVA","min"].sum()
    nlet_est_min = df.loc[df["tipo"]=="NLET_EST","min"].sum()
    nlet_ind_min = df.loc[df["tipo"]=="NLET_IND","min"].sum()
    total_min = letiva_min + nlet_est_min + nlet_ind_min

    issues, fixes = [], []

    # Regra blocos 60 min no Pré e 1º
    blocos_60_erros = []
    mask_pre1 = (df["tipo"]=="LETIVA") & (df["ciclo"].isin(["Pré","1º"]))
    for _, r in df.loc[mask_pre1].iterrows():
        dur = int(r["min"])
        if dur % 60 != 0:
            falta = 60 - (dur % 60)
            blocos_60_erros.append((r["dia"], r["inicio"], r["fim"], dur, falta))
    if blocos_60_erros:
        issues.append("Blocos LETIVA no Pré/1º devem ser múltiplos de 60 min.")
        for dia, ini, fim, dur, falta in blocos_60_erros:
            fixes.append(f"Ajustar bloco {dia} {ini}-{fim}: {dur}→{dur+falta} min (acrescentar {falta} min) ou dividir em blocos de 60.")

    # Alvos por grupo
    grupo = str(docente_row.get("grupo","")).strip()
    if grupo in ["100","110"]:
        alvo_min = 1500
        if letiva_min != alvo_min:
            if letiva_min < alvo_min:
                delta = alvo_min - letiva_min
                issues.append("Componente letiva abaixo dos 1500 min (Grupo 100/110).")
                fixes.append(f"Acrescentar {delta} min de LETIVA para atingir 1500 min.")
            else:
                delta = letiva_min - alvo_min
                issues.append("Componente letiva acima dos 1500 min (Grupo 100/110).")
                fixes.append(f"Reduzir {delta} min de LETIVA para cumprir 1500 min.")
    else:
        alvo_min = 1100
        if letiva_min > alvo_min:
            delta = letiva_min - alvo_min
            issues.append("Componente letiva acima do máximo (1100 min).")
            fixes.append(f"Reduzir {delta} min de LETIVA para não exceder 1100 min.")
        else:
            rem = alvo_min - letiva_min
            if rem >= 50:
                add = rem - 49
                issues.append(f"Remanescente = {rem} min (deve ser < 50).")
                fixes.append(f"Acrescentar {add} min de LETIVA (ex.: apoio/coadjuvação) para ficar com remanescente 49 min.")
            # opcional: indicar margem sem quebrar regra
            else:
                margem = 49 - rem
                if margem>0:
                    fixes.append(f"Pode acrescentar até {margem} min de LETIVA sem ultrapassar o limite de remanescente (<50).")

    # NLet Est regras
    if nlet_est_min < NLET_EST_MIN:
        diff = NLET_EST_MIN - nlet_est_min
        issues.append("NLet Est abaixo do mínimo definido.")
        fixes.append(f"Aumentar {diff} min em NLet Est (trabalho de escola).")
    if nlet_est_min > NLET_EST_CAP:
        diff = nlet_est_min - NLET_EST_CAP
        issues.append("NLet Est acima do máximo legal (150 min).")
        fixes.append(f"Reduzir {diff} min em NLet Est (cap 150).")

    # Turnos por dia
    msg_turnos = []
    for dia in df["dia"].dropna().unique():
        blocos = df[df["dia"]==dia].sort_values("inicio")[["inicio","fim"]].values.tolist()
        turnos=1
        for i in range(1,len(blocos)):
            gap = min_between(blocos[i-1][1], blocos[i][0])
            if gap>=120: turnos+=1
        if turnos>2:
            msg_turnos.append(f"{dia}: {turnos} turnos")
    if msg_turnos:
        issues.append("Mais de 2 turnos/dia.")
        fixes.extend([f"Reorganizar {t}" for t in msg_turnos])

    return {
        "alvo_min": alvo_min,
        "letiva_h": round(letiva_min/60,2),
        "nlet_est_h": round(nlet_est_min/60,2),
        "nlet_ind_h": round(nlet_ind_min/60,2),
        "total_h": round(total_min/60,2),
        "issues": issues,
        "fixes": fixes
    }

# ---------------------------
# UI - Top metrics
# ---------------------------
st.title("Distribuição de Serviço Docente — Regras por grupo e blocos de 60 min no Pré/1º")
c1, c2, c3, c4 = st.columns(4)
c1.metric("N.º de turmas", n_turmas)
c2.metric("Crédito Horário (estimado)", f"{CH_calc:.1f} h/sem")
c3.metric("CH usado (DT mínimo)", f"{ch_usado:.1f} h/sem")
c4.metric("Saldo CH", f"{ch_saldo:.1f} h/sem")

# ---------------------------
# Validação por docente
# ---------------------------
st.subheader("Validação por docente")
for _, d in docentes.iterrows():
    v = validar_docente(horarios, d)
    ok = not v["issues"]
    color = "✅" if ok else ("🟧" if any("NLet" in x or "Blocos" in x for x in v["issues"]) else "🟥")
    alvo_h = int(v["alvo_min"]//60) if v["alvo_min"] else None
    alvo_txt = f"Alvo letiva: {alvo_h}h" if alvo_h else "Sem alvo"
    st.markdown(f"**{color} {d['nome']} ({d['grupo']})** — {alvo_txt} | Letiva {v['letiva_h']}h | NLet Est {v['nlet_est_h']}h | NLet Ind {v['nlet_ind_h']}h | Total {v['total_h']}h")
    if v["issues"]:
        st.write("**Problemas detetados:**")
        for i in v["issues"]:
            st.write(f"- {i}")
    if v["fixes"]:
        st.write("**Sugestões de correção:**")
        for f in v["fixes"]:
            st.write(f"- {f}")

# ---------------------------
# Validação da Matriz (se fornecida)
# ---------------------------
if matriz is not None and not matriz.empty:
    st.subheader("Conformidade com a matriz curricular")
    # Normalizar ciclos na matriz
    if "ciclo" in matriz.columns:
        matriz["ciclo"] = matriz["ciclo"].map(normalize_ciclo)

    # Somar minutos letivos por turma x disciplina
    letiva = horarios[horarios["tipo"]=="LETIVA"].copy()
    if not letiva.empty:
        letiva["min"] = letiva.apply(lambda r: min_between(r["inicio"], r["fim"]), axis=1)
        letiva["ciclo"] = letiva["turma_id"].map(lambda t: turma_ciclo.get(t, ""))
        agg = letiva.groupby(["turma_id","ciclo","disciplina"], dropna=False)["min"].sum().reset_index()
        # Juntar com matriz por ciclo+disciplina
        rep = agg.merge(matriz, how="left", on=["ciclo","disciplina"])
        def estado(r):
            if pd.isna(r["carga_sem_min"]): return "Sem referência"
            if r["min"] == r["carga_sem_min"]: return "OK"
            if r["min"] < r["carga_sem_min"]: return "Parcial"
            return "Excedido"
        rep["estado"] = rep.apply(estado, axis=1)
        st.dataframe(rep.sort_values(["turma_id","disciplina"]))
    else:
        st.info("Sem registos letivos para verificar a matriz.")

st.divider()
with st.expander("Modelos de CSV para download"):
    st.download_button("docentes.csv (modelo)",
                       pd.DataFrame(columns=REQUIRED_SCHEMAS["docentes"]).to_csv(index=False).encode(),
                       "docentes.csv","text/csv")
    st.download_button("turmas.csv (modelo)",
                       pd.DataFrame(columns=REQUIRED_SCHEMAS["turmas"]).to_csv(index=False).encode(),
                       "turmas.csv","text/csv")
    st.download_button("funcoes.csv (modelo)",
                       pd.DataFrame(columns=REQUIRED_SCHEMAS["funcoes"]).to_csv(index=False).encode(),
                       "funcoes.csv","text/csv")
    st.download_button("horarios.csv (modelo)",
                       pd.DataFrame(columns=REQUIRED_SCHEMAS["horarios"]).to_csv(index=False).encode(),
                       "horarios.csv","text/csv")
    st.download_button("matriz.csv (modelo)",
                       pd.DataFrame(columns=OPTIONAL_SCHEMAS["matriz"]).to_csv(index=False).encode(),
                       "matriz.csv","text/csv")

st.caption("Regras: Grupos 100/110 = 1500 min; restantes ≤1100 com remanescente < 50; NLet Est cap 150; Pré/1º com blocos de 60 min.")


import streamlit as st
import pandas as pd
import zipfile
import io

st.set_page_config(page_title="Distribuição de Serviço Docente", layout="wide")

# ---------------------------
# Config Sidebar
# ---------------------------
st.sidebar.header("Configuração")
UNID_MIN = st.sidebar.number_input("Minutos por unidade letiva", 50, 90, 50, 5)
TEIP = st.sidebar.checkbox("Agrupamento TEIP?", value=False)
MAX_TURNOS_DIA = 2
MIN_NLET_EST_MAX150 = st.sidebar.slider("Mín. NLet Est. (min/sem, até 150)", 0, 150, 90)

st.sidebar.markdown("---")
st.sidebar.header("Dados")
st.sidebar.caption("Pode carregar um ZIP com os 4 CSVs, **ou** enviar cada CSV individualmente.")

# ---------------------------
# Helpers
# ---------------------------
REQUIRED_SCHEMAS = {
    "docentes": ["id","nome","grupo","reducao79_min"],
    "turmas": ["id","ciclo","curso","n_alunos","escola"],
    "funcoes": ["docente_id","tipo","horas_sem"],
    "horarios": ["docente_id","dia","inicio","fim","tipo","local","turma_id"],
}

def load_default_data():
    turmas_default = pd.DataFrame([
        {"id":"7A","ciclo":"3º","curso":"CH","n_alunos":26,"escola":"Sede"},
        {"id":"10ºA","ciclo":"Sec","curso":"CH","n_alunos":28,"escola":"Sede"},
    ])
    docentes_default = pd.DataFrame([
        {"id":"D1","nome":"Ana Silva","grupo":"510","reducao79_min":0},
        {"id":"D2","nome":"Bruno Sousa","grupo":"520","reducao79_min":110},
    ])
    funcoes_default = pd.DataFrame([
        {"docente_id":"D1","tipo":"DT","horas_sem":4},
    ])
    horarios_default = pd.DataFrame([
        {"docente_id":"D1","dia":"2ª","inicio":"08:30","fim":"10:10","tipo":"LETIVA","local":"Sede","turma_id":"7A"},
        {"docente_id":"D1","dia":"2ª","inicio":"10:20","fim":"12:00","tipo":"LETIVA","local":"Sede","turma_id":"7A"},
        {"docente_id":"D1","dia":"4ª","inicio":"14:00","fim":"15:40","tipo":"NLET_EST","local":"Sede","turma_id":""},
        {"docente_id":"D2","dia":"2ª","inicio":"08:30","fim":"10:10","tipo":"LETIVA","local":"Sede","turma_id":"10ºA"},
        {"docente_id":"D2","dia":"2ª","inicio":"14:00","fim":"15:40","tipo":"LETIVA","local":"Sede","turma_id":"10ºA"},
    ])
    return docentes_default, turmas_default, funcoes_default, horarios_default

def validate_schema(df: pd.DataFrame, name: str):
    required = REQUIRED_SCHEMAS[name]
    missing = [c for c in required if c not in df.columns]
    return missing

def min_between(h1, h2):
    h1h, h1m = map(int, h1.split(":")); h2h, h2m = map(int, h2.split(":"))
    return (h2h*60+h2m) - (h1h*60+h1m)

def read_csv_bytes(file):
    try:
        return pd.read_csv(file)
    except Exception as e:
        st.error(f"Erro ao ler CSV ({file.name if hasattr(file,'name') else 'upload'}): {e}")
        return None

def load_from_zip(zip_bytes):
    datasets = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as z:
            for key in REQUIRED_SCHEMAS.keys():
                candidate_names = [f"{key}.csv", f"{key}.CSV"]
                member = next((n for n in z.namelist() if n in candidate_names or n.endswith(f"/{key}.csv") or n.endswith(f"/{key}.CSV")), None)
                if member:
                    with z.open(member) as f:
                        datasets[key] = pd.read_csv(f)
    except Exception as e:
        st.error(f"Erro ao ler ZIP: {e}")
    return datasets

# ---------------------------
# Data Loading UI
# ---------------------------
zip_upload = st.file_uploader("Carregar ZIP com docentes.csv, turmas.csv, funcoes.csv, horarios.csv", type=["zip"])

uploaded = {}
if zip_upload is not None:
    uploaded.update(load_from_zip(zip_upload.read()))

col1, col2 = st.columns(2)
with col1:
    up_docentes = st.file_uploader("docentes.csv", type=["csv"], key="docentes_up")
    up_turmas   = st.file_uploader("turmas.csv", type=["csv"], key="turmas_up")
with col2:
    up_funcoes  = st.file_uploader("funcoes.csv", type=["csv"], key="funcoes_up")
    up_horarios = st.file_uploader("horarios.csv", type=["csv"], key="horarios_up")

if up_docentes: uploaded["docentes"] = read_csv_bytes(up_docentes)
if up_turmas:   uploaded["turmas"]   = read_csv_bytes(up_turmas)
if up_funcoes:  uploaded["funcoes"]  = read_csv_bytes(up_funcoes)
if up_horarios: uploaded["horarios"] = read_csv_bytes(up_horarios)

# Defaults
docentes_default, turmas_default, funcoes_default, horarios_default = load_default_data()

docentes = uploaded.get("docentes", docentes_default)
turmas   = uploaded.get("turmas", turmas_default)
funcoes  = uploaded.get("funcoes", funcoes_default)
horarios = uploaded.get("horarios", horarios_default)

# Validate schemas
problems = []
for name, df in [("docentes", docentes), ("turmas", turmas), ("funcoes", funcoes), ("horarios", horarios)]:
    if df is None:
        problems.append(f"{name}: ficheiro inválido.")
        continue
    missing = validate_schema(df, name)
    if missing:
        problems.append(f"{name}.csv: faltam colunas {missing}")

with st.expander("Pré-visualização dos dados carregados"):
    st.write("**docentes**", docentes.head())
    st.write("**turmas**", turmas.head())
    st.write("**funcoes**", funcoes.head())
    st.write("**horarios**", horarios.head())

if problems:
    st.error("⚠️ Problemas nos ficheiros:")
    for p in problems:
        st.write("- ", p)
    st.stop()

# ---------------------------
# Cálculo do Crédito Horário
# ---------------------------
n_turmas = len(turmas)
horas79_total = docentes["reducao79_min"].sum() / 60.0
CH_calc = (10 if TEIP else 7)*n_turmas - 0.5*horas79_total

# DT: mínimo 2h em CH (de 4h totais)
dt_horas = funcoes.query("tipo=='DT'")["horas_sem"].sum()
ch_usado = max(0, dt_horas*0.5)
ch_saldo = CH_calc - ch_usado

# ---------------------------
# Validações por docente
# ---------------------------
def validar_docente(df_hor, docente_row):
    df = df_hor[df_hor["docente_id"]==docente_row["id"]].copy()
    if df.empty:
        return {"letiva_h":0,"nlet_est_h":0,"nlet_ind_h":0,"total_h":0,"issues":["Sem horário atribuído"]}
    df["min"] = df.apply(lambda r: min_between(str(r["inicio"]), str(r["fim"])), axis=1)
    letiva_min = df.loc[df["tipo"]=="LETIVA","min"].sum()
    nlet_est_min = df.loc[df["tipo"]=="NLET_EST","min"].sum()
    nlet_ind_min = df.loc[df["tipo"]=="NLET_IND","min"].sum()
    total_min = letiva_min + nlet_est_min + nlet_ind_min

    # MVP: alvo 22h; (futuro: 25h para 1.º ciclo/Pré, por ciclo/nível)
    alvo_letiva_min = 22*60

    # turnos/dia (simplificação: gap >= 120 min => novo turno)
    msg_turnos = []
    for dia in df["dia"].unique():
        blocos = df[df["dia"]==dia].sort_values("inicio")[["inicio","fim"]].values.tolist()
        turnos=1
        for i in range(1,len(blocos)):
            gap = min_between(blocos[i-1][1], blocos[i][0])
            if gap>=120: turnos+=1
        if turnos>2:
            msg_turnos.append(f"{dia}: {turnos} turnos (>2)")

    issues = []
    if letiva_min < alvo_letiva_min:
        issues.append(f"Componente letiva insuficiente: {letiva_min//60:.0f}h{int(letiva_min%60):02d} (alvo 22h)")
    if nlet_est_min < MIN_NLET_EST_MAX150:
        issues.append(f"NLet Est. < {MIN_NLET_EST_MAX150} min/sem")
    if msg_turnos:
        issues.append("Mais de 2 turnos em: " + ", ".join(msg_turnos))

    return {
        "letiva_h": round(letiva_min/60,2),
        "nlet_est_h": round(nlet_est_min/60,2),
        "nlet_ind_h": round(nlet_ind_min/60,2),
        "total_h": round(total_min/60,2),
        "issues": issues
    }

# ---------------------------
# UI
# ---------------------------
st.title("Distribuição de Serviço Docente – MVP (com uploads)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("N.º de turmas", n_turmas)
c2.metric("Crédito Horário (estimado)", f"{CH_calc:.1f} h/sem")
c3.metric("CH usado (DT mínimo)", f"{ch_usado:.1f} h/sem")
c4.metric("Saldo CH", f"{ch_saldo:.1f} h/sem")

st.subheader("Validação por docente")
for _, d in docentes.iterrows():
    v = validar_docente(horarios, d)
    color = "✅" if not v["issues"] else ("🟧" if any("NLet" in x for x in v["issues"]) else "🟥")
    st.markdown(f"**{color} {d['nome']} ({d['grupo']})** — Letiva {v['letiva_h']}h | NLet Est {v['nlet_est_h']}h | NLet Ind {v['nlet_ind_h']}h | Total {v['total_h']}h")
    if v["issues"]:
        for i in v["issues"]:
            st.write(f"- {i}")

st.divider()
with st.expander("Modelos de CSV para download"):
    st.download_button("docentes.csv (modelo)",
                       pd.DataFrame(columns=REQUIRED_SCHEMAS["docentes"]).to_csv(index=False).encode(),
                       "docentes.csv",
                       "text/csv")
    st.download_button("turmas.csv (modelo)",
                       pd.DataFrame(columns=REQUIRED_SCHEMAS["turmas"]).to_csv(index=False).encode(),
                       "turmas.csv",
                       "text/csv")
    st.download_button("funcoes.csv (modelo)",
                       pd.DataFrame(columns=REQUIRED_SCHEMAS["funcoes"]).to_csv(index=False).encode(),
                       "funcoes.csv",
                       "text/csv")
    st.download_button("horarios.csv (modelo)",
                       pd.DataFrame(columns=REQUIRED_SCHEMAS["horarios"]).to_csv(index=False).encode(),
                       "horarios.csv",
                       "text/csv")

st.caption("Pode carregar um ZIP com os quatro ficheiros (nomes exatos: docentes.csv, turmas.csv, funcoes.csv, horarios.csv) ou carregar cada um separadamente.")

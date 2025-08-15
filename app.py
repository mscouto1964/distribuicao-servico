
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Distribuição de Serviço Docente", layout="wide")

# --- Parâmetros globais ---
UNID_MIN = st.sidebar.number_input("Minutos por unidade letiva", 50, 90, 50, 5)
TEIP = st.sidebar.checkbox("Agrupamento TEIP?", value=False)
MAX_TURNOS_DIA = 2
MIN_NLET_EST_MAX150 = st.sidebar.slider("Mín. NLet Est. (min/sem, até 150)", 0, 150, 90)

# --- Dados (carregar CSVs opcionais) ---
def load_df(default_df, csv_name):
    try:
        return pd.read_csv(csv_name)
    except Exception:
        return default_df

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

turmas = load_df(turmas_default, "turmas.csv")
docentes = load_df(docentes_default, "docentes.csv")
funcoes = load_df(funcoes_default, "funcoes.csv")
horarios = load_df(horarios_default, "horarios.csv")

st.sidebar.download_button("Exportar docentes.csv", docentes.to_csv(index=False).encode(), "docentes.csv", "text/csv")
st.sidebar.download_button("Exportar turmas.csv", turmas.to_csv(index=False).encode(), "turmas.csv", "text/csv")
st.sidebar.download_button("Exportar funcoes.csv", funcoes.to_csv(index=False).encode(), "funcoes.csv", "text/csv")
st.sidebar.download_button("Exportar horarios.csv", horarios.to_csv(index=False).encode(), "horarios.csv", "text/csv")

st.sidebar.write("Para usar os seus dados, carregue CSVs com estes nomes na pasta da app.")

def min_between(h1, h2):
    h1h, h1m = map(int, h1.split(":")); h2h, h2m = map(int, h2.split(":"))
    return (h2h*60+h2m) - (h1h*60+h1m)

# --- Cálculo do Crédito Horário ---
n_turmas = len(turmas)
horas79_total = docentes["reducao79_min"].sum() / 60.0
CH_calc = (10 if TEIP else 7)*n_turmas - 0.5*horas79_total

# --- Saldo CH (considerar DT: mínimo 2h em CH) ---
dt_horas = funcoes.query("tipo=='DT'")["horas_sem"].sum()
ch_usado = max(0, dt_horas*0.5)  # simplificação: pelo menos 2h das 4h DT em CH
ch_saldo = CH_calc - ch_usado

# --- Validações por docente ---
def validar_docente(df_hor, docente_row):
    df = df_hor[df_hor["docente_id"]==docente_row["id"]].copy()
    if df.empty:
        return {"letiva_h":0,"nlet_est_h":0,"nlet_ind_h":0,"total_h":0,"issues":["Sem horário atribuído"]}
    df["min"] = df.apply(lambda r: min_between(r["inicio"], r["fim"]), axis=1)
    letiva_min = df.loc[df["tipo"]=="LETIVA","min"].sum()
    nlet_est_min = df.loc[df["tipo"]=="NLET_EST","min"].sum()
    nlet_ind_min = df.loc[df["tipo"]=="NLET_IND","min"].sum()
    total_min = letiva_min + nlet_est_min + nlet_ind_min

    alvo_letiva_min = 22*60  # a app pode futuramente ajustar por nível

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
        issues.append(f"Componente letiva insuficiente: {letiva_min//60:.0f}h{letiva_min%60:02d} (alvo 22h)")
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

st.title("Distribuição de Serviço Docente – MVP")
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
st.caption("MVP baseado no Despacho Normativo n.º 10‑B/2018. Esta versão é demonstrativa e será afinada por nível de ensino e desdobramentos.")

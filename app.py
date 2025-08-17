import streamlit as st
import pandas as pd
import zipfile, io, os, re

st.set_page_config(page_title="Distribuição de Serviço Docente", layout="wide")

st.sidebar.header("Configuração")
UNID_MIN = st.sidebar.number_input("Minutos por unidade letiva (2º/3º/Sec)", 45, 90, 50, 5)
TEIP = st.sidebar.checkbox("Agrupamento TEIP?", value=False)
NLET_EST_MIN = st.sidebar.slider("Mín. NLet Est. (0–150)", 0, 150, 90)
NLET_EST_CAP = 150
MAX_TURNOS_DIA = 2

st.sidebar.markdown("---")
st.sidebar.header("Carregamento de dados")
st.sidebar.caption("Carregue um ZIP com todos os ficheiros (CSV/XLSX) **ou** ficheiros individuais.")

REQUIRED = {
    "docentes": ["id","nome","grupo","reducao79_min"],
    "turmas": ["id","ciclo","ano","curso","n_alunos","escola"],
    "funcoes": ["docente_id","tipo","horas_sem"],
    "horarios": ["docente_id","dia","inicio","fim","tipo","local","turma_id","disciplina"],
}
OPTIONAL = {"matriz": ["ciclo","ano","disciplina","carga_sem_min"]}

def normalize_ciclo(x: str):
    if not isinstance(x, str): return ""
    t = x.strip().lower()
    if t.startswith("pré") or t.startswith("pre"): return "Pré"
    if t.startswith("1"): return "1º"
    if t.startswith("2"): return "2º"
    if t.startswith("3"): return "3º"
    if t.startswith("sec") or "secund" in t: return "Sec"
    return x

def mins_between(h1, h2):
    try:
        sh, sm = map(int, str(h1).split(":"))
        eh, em = map(int, str(h2).split(":"))
        return (eh*60+em) - (sh*60+sm)
    except Exception:
        return 0

def _normalize_token(s: str) -> str:
    if not isinstance(s, str): s = str(s)
    s = s.strip().lower()
    accents = str.maketrans("áàãâéêíóôõúçºª", "aaaaeeioooucoo")
    s = s.translate(accents)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")

SYNONYMS = {
    "id": ["id","codigo","cod","docente_id"],
    "nome": ["nome","docente","professor","nome_docente"],
    "grupo": ["grupo","grupo_recrutamento","grupo_de_recrutamento","grupo_recrut"],
    "reducao79_min": ["reducao79_min","reducao79","reducao_art79_min","reducao_art_79_min"],
    "ciclo": ["ciclo"],
    "ano": ["ano","ano_escolaridade","ano_de_escolaridade"],
    "curso": ["curso"],
    "n_alunos": ["n_alunos","numero_alunos","num_alunos","n__alunos","n_aluno","n_de_alunos"],
    "escola": ["escola","estabelecimento","edificio"],
    "tipo": ["tipo","funcao","cargo"],
    "horas_sem": ["horas_sem","horas","horas_semanais","h_sem"],
    "dia": ["dia","dia_semana"],
    "inicio": ["inicio","hora_inicio","inicio_hora","inicio_"],
    "fim": ["fim","hora_fim","fim_hora","termino"],
    "local": ["local","escola","edificio","sala"],
    "turma_id": ["turma_id","turma","id_turma"],
    "disciplina": ["disciplina","dis"],
    "carga_sem_min": ["carga_sem_min","carga_horaria_min_sem","carga","carga_sem"],
}

def smart_rename(df: pd.DataFrame, expected_cols: list) -> pd.DataFrame:
    rename_map = {}
    norm_to_orig = {_normalize_token(c): c for c in df.columns}
    for exp in expected_cols:
        candidates = [exp] + SYNONYMS.get(exp, [])
        candidates = [_normalize_token(c) for c in candidates]
        for cand in candidates:
            if cand in norm_to_orig:
                rename_map[norm_to_orig[cand]] = exp
                break
    return df.rename(columns=rename_map).copy()

def read_table_from_bytes(data: bytes, filename: str):
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        try:
            return pd.read_excel(io.BytesIO(data))
        except Exception as e:
            st.error(f"Erro a ler Excel {filename}: {e}")
            return None
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
                if len(df.columns) >= 1:
                    return df
            except Exception:
                continue
    st.error(f"Não foi possível ler o ficheiro {filename}.")
    return None

def read_uploaded(file):
    data = file.read()
    return read_table_from_bytes(data, getattr(file, "name", "upload"))

def load_from_zip(zip_bytes):
    datasets = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as z:
            names = z.namelist()
            for key in list(REQUIRED.keys()) + list(OPTIONAL.keys()):
                match = None
                for n in names:
                    base = os.path.basename(n).lower()
                    if base in {f"{key}.csv", f"{key}.xlsx", f"{key}.xls"}:
                        match = n; break
                if match:
                    data = z.read(match)
                    df = read_table_from_bytes(data, match)
                    if df is not None:
                        datasets[key] = df
    except Exception as e:
        st.error(f"Erro ao ler ZIP: {e}")
    return datasets

def validate_schema(df, name, optional=False):
    exp = (OPTIONAL if optional else REQUIRED)[name]
    df2 = smart_rename(df, exp)
    missing = [c for c in exp if c not in df2.columns]
    return missing, df2

# Defaults
docentes_def = pd.DataFrame([
    {"id":"D1","nome":"Ana Silva","grupo":"110","reducao79_min":0},
    {"id":"D2","nome":"Bruno Sousa","grupo":"510","reducao79_min":110},
])
turmas_def = pd.DataFrame([
    {"id":"1A","ciclo":"1º","ano":1,"curso":"Reg","n_alunos":24,"escola":"EB1"},
    {"id":"7A","ciclo":"3º","ano":7,"curso":"Reg","n_alunos":26,"escola":"Sede"},
    {"id":"10A","ciclo":"Sec","ano":10,"curso":"CH","n_alunos":28,"escola":"Sede"},
])
funcoes_def = pd.DataFrame([
    {"docente_id":"D1","tipo":"DT","horas_sem":4},
])
horarios_def = pd.DataFrame([
    {"docente_id":"D1","dia":"2ª","inicio":"08:30","fim":"09:30","tipo":"LETIVA","local":"EB1","turma_id":"1A","disciplina":"Português"},
    {"docente_id":"D1","dia":"2ª","inicio":"09:30","fim":"10:30","tipo":"LETIVA","local":"EB1","turma_id":"1A","disciplina":"Estudo do Meio"},
    {"docente_id":"D1","dia":"4ª","inicio":"14:00","fim":"15:30","tipo":"NLET_EST","local":"EB1","turma_id":"","disciplina":""},
    {"docente_id":"D2","dia":"2ª","inicio":"08:30","fim":"10:10","tipo":"LETIVA","local":"Sede","turma_id":"7A","disciplina":"Físico-Química"},
    {"docente_id":"D2","dia":"2ª","inicio":"14:00","fim":"15:40","tipo":"LETIVA","local":"Sede","turma_id":"10A","disciplina":"Física"},
])
matriz_def = pd.DataFrame([
    {"ciclo":"1º","ano":1,"disciplina":"Português","carga_sem_min":300},
    {"ciclo":"1º","ano":1,"disciplina":"Estudo do Meio","carga_sem_min":150},
    {"ciclo":"3º","ano":7,"disciplina":"Físico-Química","carga_sem_min":150},
    {"ciclo":"Sec","ano":10,"disciplina":"Física","carga_sem_min":150},
])

# Uploads
zip_upload = st.file_uploader("ZIP com docentes/turmas/funcoes/horarios (e opcionalmente matriz) — CSV ou Excel", type=["zip"])
uploaded = {}
if zip_upload is not None:
    uploaded.update(load_from_zip(zip_upload.read()))

c1, c2 = st.columns(2)
with c1:
    up_docentes = st.file_uploader("docentes (CSV/XLSX)", type=["csv","xlsx","xls"], key="docentes_up")
    up_turmas   = st.file_uploader("turmas (CSV/XLSX)",   type=["csv","xlsx","xls"], key="turmas_up")
    up_matriz   = st.file_uploader("matriz (opcional)",    type=["csv","xlsx","xls"], key="matriz_up")
with c2:
    up_funcoes  = st.file_uploader("funcoes (CSV/XLSX)",  type=["csv","xlsx","xls"], key="funcoes_up")
    up_horarios = st.file_uploader("horarios (CSV/XLSX)", type=["csv","xlsx","xls"], key="horarios_up")

if up_docentes: uploaded["docentes"] = read_uploaded(up_docentes)
if up_turmas:   uploaded["turmas"]   = read_uploaded(up_turmas)
if up_funcoes:  uploaded["funcoes"]  = read_uploaded(up_funcoes)
if up_horarios: uploaded["horarios"] = read_uploaded(up_horarios)
if up_matriz:   uploaded["matriz"]   = read_uploaded(up_matriz)

docentes_raw = uploaded.get("docentes", docentes_def)
turmas_raw   = uploaded.get("turmas", turmas_def)
funcoes_raw  = uploaded.get("funcoes", funcoes_def)
horarios_raw = uploaded.get("horarios", horarios_def)
matriz_raw   = uploaded.get("matriz", matriz_def)

if "ciclo" in turmas_raw.columns:
    turmas_raw["ciclo"] = turmas_raw["ciclo"].map(normalize_ciclo)
if "ciclo" in matriz_raw.columns:
    matriz_raw["ciclo"] = matriz_raw["ciclo"].map(normalize_ciclo)

problems = []
docentes_miss, docentes = validate_schema(docentes_raw, "docentes")
turmas_miss,   turmas   = validate_schema(turmas_raw, "turmas")
funcoes_miss,  funcoes  = validate_schema(funcoes_raw, "funcoes")
horarios_miss, horarios = validate_schema(horarios_raw, "horarios")
matriz_miss,   matriz   = validate_schema(matriz_raw, "matriz", optional=True)

if docentes_miss: problems.append(f"docentes: faltam colunas {docentes_miss}")
if turmas_miss:   problems.append(f"turmas: faltam colunas {turmas_miss}")
if funcoes_miss:  problems.append(f"funcoes: faltam colunas {funcoes_miss}")
if horarios_miss: problems.append(f"horarios: faltam colunas {horarios_miss}")
if matriz_miss:   problems.append(f"matriz: faltam colunas {matriz_miss}")

with st.expander("Ficheiros detetados e pré-visualização"):
    shapes = {k:v.shape for k,v in [("docentes",docentes),("turmas",turmas),("funcoes",funcoes),("horarios",horarios),("matriz",matriz)] if isinstance(v,pd.DataFrame)}
    st.write("Dimensões:", shapes)
    st.write("**docentes**", docentes.head())
    st.write("**turmas**", turmas.head())
    st.write("**funcoes**", funcoes.head())
    st.write("**horarios**", horarios.head())
    if isinstance(matriz, pd.DataFrame) and not matriz.empty:
        st.write("**matriz**", matriz.head())

if problems:
    st.error("⚠️ Problemas nos ficheiros:")
    for p in problems: st.write("- ", p)
    st.stop()

# Métricas globais
n_turmas = len(turmas)
horas79_total = (docentes["reducao79_min"].sum() / 60.0) if "reducao79_min" in docentes else 0
CH_calc = (10 if TEIP else 7)*n_turmas - 0.5*horas79_total
dt_horas = funcoes.query("tipo=='DT'")["horas_sem"].sum() if not funcoes.empty else 0
ch_usado = max(0, dt_horas*0.5)
ch_saldo = CH_calc - ch_usado

st.title("Distribuição de Serviço Docente — Versão Robusta (uploads)")
m1, m2, m3, m4 = st.columns(4)
m1.metric("N.º turmas", n_turmas)
m2.metric("Crédito Horário (estim.)", f"{CH_calc:.1f} h/sem")
m3.metric("CH usado (DT mínimo)", f"{ch_usado:.1f} h/sem")
m4.metric("Saldo CH", f"{ch_saldo:.1f} h/sem")

turma_ciclo = turmas.set_index("id")["ciclo"].to_dict()
turma_ano   = turmas.set_index("id")["ano"].to_dict()

def validar_docente(docente):
    d_id = docente["id"]
    grupo = str(docente.get("grupo","")).strip()
    df = horarios[horarios["docente_id"]==d_id].copy()
    if df.empty:
        return {"alvo":"—","letiva":0,"nlet_est":0,"nlet_ind":0,"issues":["Sem horário atribuído"],"sugestoes":[]}
    df["min"] = df.apply(lambda r: mins_between(r["inicio"], r["fim"]), axis=1)
    letiva = int(df.loc[df["tipo"]=="LETIVA","min"].sum())
    nlet_est = int(df.loc[df["tipo"]=="NLET_EST","min"].sum())
    nlet_ind = int(df.loc[df["tipo"]=="NLET_IND","min"].sum())
    total = letiva + nlet_est + nlet_ind

    issues, sug = [], []

    pre1 = df[(df["tipo"]=="LETIVA") & (df["turma_id"].map(lambda t: turma_ciclo.get(t,"") in ["Pré","1º"]))]
    for i, r in pre1.iterrows():
        dur = int(r["min"])
        if dur % 60 != 0:
            falta = 60 - (dur % 60)
            issues.append(f"Bloco não múltiplo de 60 min (Pré/1º): {r['dia']} {r['inicio']}-{r['fim']} ({dur} min)")
            sug.append(f"Acrescentar {falta} min ou ajustar para múltiplos de 60.")

    if grupo in ["100","110"]:
        alvo = 1500
        if letiva != alvo:
            if letiva < alvo:
                issues.append(f"Letiva abaixo dos 1500 min (grupo {grupo}).")
                sug.append(f"Acrescentar {alvo - letiva} min de LETIVA para atingir 1500.")
            else:
                issues.append(f"Letiva acima dos 1500 min (grupo {grupo}).")
                sug.append(f"Reduzir {letiva - alvo} min de LETIVA para cumprir 1500.")
    else:
        alvo = 1100
        if letiva > alvo:
            issues.append("Letiva acima do máximo (1100 min).")
            sug.append(f"Reduzir {letiva - alvo} min de LETIVA para ficar em 1100.")
        elif letiva < alvo:
            rem = alvo - letiva
            if rem >= 50:
                need = rem - 49
                issues.append(f"Letiva abaixo de 1100 min com remanescente {rem} min (>=50).")
                sug.append(f"Acrescentar {need} min de LETIVA (ex.: apoio/coadjuvação) para remanescente ≤ 49 min.")
            else:
                sug.append(f"Pode acrescentar até {49 - rem} min sem ultrapassar o limite de remanescente.")

    if nlet_est < NLET_EST_MIN:
        issues.append(f"NLet Est abaixo do mínimo definido ({NLET_EST_MIN} min).")
        sug.append(f"Aumentar {NLET_EST_MIN - nlet_est} min na NLet Est.")
    if nlet_est > NLET_EST_CAP:
        issues.append(f"NLet Est acima do máximo legal (150 min).")
        sug.append(f"Reduzir {nlet_est - NLET_EST_CAP} min na NLet Est.")

    return {"alvo":alvo,"letiva":letiva,"nlet_est":nlet_est,"nlet_ind":nlet_ind,"total":total,"issues":issues,"sugestoes":sug}

st.subheader("Validação por docente")
for _, d in docentes.iterrows():
    v = validar_docente(d)
    ok = not v["issues"]
    color = "✅" if ok else ("🟧" if any("NLet Est" in x for x in v["issues"]) else "🟥")
    st.markdown(f"**{color} {d['nome']} ({d['grupo']})** — Alvo letiva: {int(v['alvo']//60)}h | Letiva {v['letiva']//60}h{v['letiva']%60:02d} | NLet Est {v['nlet_est']//60}h{v['nlet_est']%60:02d} | NLet Ind {v['nlet_ind']//60}h{v['nlet_ind']%60:02d}")
    if v["issues"]:
        st.write("**Problemas detetados:**")
        for i in v["issues"]:
            st.write("- ", i)
    if v["sugestoes"]:
        st.write("**Sugestões de correção:**")
        for s in v["sugestoes"]:
            st.write("- ", s)

if isinstance(matriz_raw, pd.DataFrame) and not matriz_raw.empty:
    st.subheader("Conformidade com a matriz curricular (ciclo + ano + disciplina)")
    letiva = horarios[horarios["tipo"]=="LETIVA"].copy()
    if not letiva.empty:
        letiva["min"] = letiva.apply(lambda r: mins_between(r["inicio"], r["fim"]), axis=1)
        letiva["ciclo"] = letiva["turma_id"].map(lambda t: turma_ciclo.get(t,""))
        letiva["ano"]   = letiva["turma_id"].map(lambda t: turma_ano.get(t,""))
        agg = letiva.groupby(["turma_id","ciclo","ano","disciplina"], dropna=False)["min"].sum().reset_index()

        matriz = smart_rename(matriz_raw, OPTIONAL["matriz"])
        matriz["ciclo"] = matriz["ciclo"].map(normalize_ciclo)
        rep = agg.merge(matriz, how="left", on=["ciclo","ano","disciplina"], suffixes=("","_mat"))
        fb = matriz.groupby(["ciclo","disciplina"])["carga_sem_min"].mean().reset_index().rename(columns={"carga_sem_min":"carga_fallback"})
        rep = rep.merge(fb, how="left", on=["ciclo","disciplina"])
        rep["carga_ref"] = rep["carga_sem_min"].fillna(rep["carga_fallback"])

        def estado(row):
            if pd.isna(row["carga_ref"]): return "Sem referência"
            if row["min"] == row["carga_ref"]: return "OK"
            if row["min"] < row["carga_ref"]: return "Parcial"
            return "Excedido"

        rep["estado"] = rep.apply(estado, axis=1)
        st.dataframe(rep[["turma_id","ciclo","ano","disciplina","min","carga_ref","estado"]].sort_values(["turma_id","disciplina"]), use_container_width=True)
    else:
        st.info("Sem registos letivos para verificar a matriz.")

st.divider()
with st.expander("Modelos de ficheiros para download"):
    st.download_button("docentes (modelo)", pd.DataFrame(columns=REQUIRED["docentes"]).to_csv(index=False).encode(), "docentes.csv","text/csv")
    st.download_button("turmas (modelo)",   pd.DataFrame(columns=REQUIRED["turmas"]).to_csv(index=False).encode(), "turmas.csv","text/csv")
    st.download_button("funcoes (modelo)",  pd.DataFrame(columns=REQUIRED["funcoes"]).to_csv(index=False).encode(), "funcoes.csv","text/csv")
    st.download_button("horarios (modelo)", pd.DataFrame(columns=REQUIRED["horarios"]).to_csv(index=False).encode(), "horarios.csv","text/csv")
    st.download_button("matriz (modelo)",   pd.DataFrame(columns=OPTIONAL["matriz"]).to_csv(index=False).encode(), "matriz.csv","text/csv")

st.caption("Uploads robustos: aceita CSV/Excel; nomes insensíveis a maiúsculas; deteção de separador/codificação; normalização de cabeçalhos.")

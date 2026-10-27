import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";

type Row = Record<string, any>;
type User = { username: string; role: "admin" | "clinician" | "auditor" };
class ApiError extends Error { constructor(public status: number, m: string) { super(m); } }

const csrf = () => document.cookie.split("; ").find((c) => c.startsWith("tb_csrf="))?.split("=")[1] ?? "";
async function api<T = Row>(path: string, init?: RequestInit): Promise<T> {
  const unsafe = !!init?.method && init.method !== "GET";
  const r = await fetch("/api/v1" + path, { credentials: "same-origin", headers: { "Content-Type": "application/json", ...(unsafe ? { "X-CSRF-Token": csrf() } : {}) }, ...init });
  if (!r.ok) {
    let m = r.status >= 500 ? "Error del servidor. Inténtalo de nuevo." : "Solicitud rechazada.";
    try { const j = await r.json(); m = typeof j.detail === "string" ? j.detail : "Datos inválidos: revisa los campos marcados."; } catch { /* sin cuerpo */ }
    throw new ApiError(r.status, m);
  }
  return (r.status === 204 ? undefined : await r.json()) as T;
}
const post = (p: string, b: unknown) => api(p, { method: "POST", body: JSON.stringify(b) });

function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null); const [error, setError] = useState(""); const [loading, setLoading] = useState(true);
  const reload = useCallback(() => { setLoading(true); setError(""); api<T>(path).then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false)); }, [path]);
  useEffect(reload, [reload]);
  return { data, error, loading, reload };
}
function State({ loading, error, empty, children }: { loading: boolean; error: string; empty?: boolean; children: ReactNode }) {
  if (loading) return <p className="empty" role="status">Cargando…</p>;
  if (error) return <p className="msg err" role="alert">{error}</p>;
  if (empty) return <p className="empty">Aún no hay registros. Crea el primero desde su sección.</p>;
  return <>{children}</>;
}
const Risk = ({ r }: { r: string }) => <span className={`badge ${r}`}>{r}</span>;
const statusText = (s: string) => (s === "PENDIENTE_DE_VALIDACION_CLINICA" ? "pendiente de validación clínica" : s);
const fmt = (s: string) => new Date(s).toLocaleString("es-CO");

function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const f = new FormData(e.currentTarget); setBusy(true); setErr("");
    try { onLogin((await post("/auth/login", { username: f.get("u"), password: f.get("p") })) as User); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  return <div className="login card"><h1>Thinker Bell</h1><p style={{ color: "var(--mute)" }}>Apoyo a la evaluación NEWS2. Entorno de demostración con datos sintéticos.</p>
    <form onSubmit={submit} className="grid"><label>Usuario<input name="u" autoComplete="username" required /></label>
      <label>Contraseña<input name="p" type="password" autoComplete="current-password" required /></label>
      {err && <p className="msg err" role="alert">{err}</p>}<button className="primary" disabled={busy}>{busy ? "Entrando…" : "Iniciar sesión"}</button></form></div>;
}

function Dashboard() {
  const { data, error, loading } = useLoad<Row>("/dashboard/summary");
  const dist = Object.entries((data?.risk_distribution ?? {}) as Record<string, number>); const max = Math.max(1, ...dist.map(([, n]) => n));
  const days = (data?.per_day ?? []) as { day: string; count: number }[]; const dmax = Math.max(1, ...days.map((d) => d.count));
  return <State loading={loading} error={error}>{data && <div className="grid">
    <div className="grid kpis"><div className="card kpi"><span>Evaluaciones registradas</span><b>{data.evaluations}</b></div>
      <div className="card kpi"><span>Pacientes registrados</span><b>{data.patients}</b></div>
      <div className="card kpi danger"><span>Evaluaciones con riesgo alto</span><b>{data.risk_distribution["Alto"] ?? 0}</b></div></div>
    {data.evaluations === 0 ? <p className="card empty">Sin evaluaciones todavía. Registra un paciente y realiza una evaluación para ver aquí los indicadores.</p> :
    <><div className="grid two"><div className="card"><h2>Distribución por categoría de riesgo</h2>
      {dist.map(([k, n]) => <div className="bar" key={k}><span>{k}</span><i className={k} style={{ width: `${(n / max) * 70}%` }} /><span>{n}</span></div>)}</div>
      <div className="card"><h2>Evaluaciones por día (últimos 7 con actividad)</h2><div className="cols">{days.map((d) => <div key={d.day}><i style={{ height: `${(d.count / dmax) * 90}px` }} />{d.count}<br />{d.day.slice(5)}</div>)}</div></div></div>
    <div className="card"><h2>Actividad reciente</h2><EvalTable rows={data.recent} /></div></>}</div>}</State>;
}

function EvalTable({ rows }: { rows: Row[] }) {
  return <div className="wrap" tabIndex={0} role="region" aria-label="Tabla de datos"><table><caption>Evaluaciones más recientes</caption><thead><tr><th scope="col">Fecha</th><th>Paciente</th><th>Puntaje</th><th>Riesgo</th><th>Versión de reglas</th></tr></thead>
    <tbody>{rows.map((r) => <tr key={r.evaluation_id}><td>{fmt(r.timestamp)}</td><td>{r.patient_id}</td><td>{r.total_score}</td><td><Risk r={r.clinical_risk} /></td><td>{r.algorithm_version}</td></tr>)}</tbody></table></div>;
}

const LABELS: Record<string, string> = { respiratory_rate: "Frecuencia respiratoria", oxygen_saturation: "Saturación de O₂", supplemental_oxygen: "Oxígeno suplementario",
  systolic_bp: "Presión sistólica", heart_rate: "Frecuencia cardiaca", consciousness: "Conciencia", temperature: "Temperatura" };

function NewEvaluation() {
  const pts = useLoad<Row>("/patients?limit=100"); const [res, setRes] = useState<Row | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const f = new FormData(e.currentTarget); setBusy(true); setErr(""); setRes(null);
    const n = (k: string) => Number(f.get(k));
    try { setRes(await post("/triage/evaluate", { patient_id: f.get("patient_id"), vitals: { respiratory_rate: n("rr"), oxygen_saturation: n("spo2"),
      supplemental_oxygen: f.get("o2") === "on", spo2_scale_2: f.get("s2") === "on", systolic_bp: n("sbp"), heart_rate: n("hr"), consciousness: f.get("c"), temperature: n("t") } })); }
    catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }
  return <div className="grid"><State loading={pts.loading} error={pts.error} empty={pts.data?.total === 0}>
    <form className="card f" onSubmit={submit}>
      <label>Paciente<select name="patient_id" required defaultValue="">{<option value="" disabled>Selecciona…</option>}{pts.data?.items.map((p: Row) => <option key={p.patient_id} value={p.patient_id}>{p.patient_id} · {p.full_name}</option>)}</select></label>
      <label>Frecuencia respiratoria (rpm)<input name="rr" type="number" min={1} max={70} required /></label>
      <label>SpO₂ (%)<input name="spo2" type="number" min={50} max={100} required /></label>
      <label>Presión sistólica (mmHg)<input name="sbp" type="number" min={40} max={300} required /></label>
      <label>Frecuencia cardiaca (lpm)<input name="hr" type="number" min={20} max={250} required /></label>
      <label>Temperatura (°C)<input name="t" type="number" step="0.1" min={30} max={45} required /></label>
      <label>Conciencia<select name="c" defaultValue="A"><option value="A">Alerta</option><option value="C">Confusión nueva</option><option value="V">Responde a voz</option><option value="P">Responde a dolor</option><option value="U">No responde</option></select></label>
      <label className="chk"><input name="o2" type="checkbox" />Recibe oxígeno suplementario</label>
      <label className="chk"><input name="s2" type="checkbox" />Escala 2 de SpO₂ (indicada por profesional)</label>
      <div><button className="primary" disabled={busy}>{busy ? "Calculando…" : "Calcular y guardar"}</button></div></form></State>
    {err && <p className="msg err" role="alert">{err}</p>}
    {res && <div className="card" role="status"><h2>Resultado: {res.total_score} puntos <Risk r={res.clinical_risk} /></h2><p>{res.recommended_response}</p>
      <div className="wrap" tabIndex={0} role="region" aria-label="Tabla de datos"><table><tbody>{Object.entries(res.parameter_scores as Record<string, number>).map(([k, v]) => <tr key={k}><td>{LABELS[k] ?? k}</td><td>{v}</td></tr>)}</tbody></table></div>
      <p className="msg ok">Guardado con las reglas {res.algorithm_version} ({statusText(res.rules_status)}). No es un diagnóstico.</p></div>}</div>;
}

function Patients({ user }: { user: User }) {
  const [q, setQ] = useState(""); const { data, error, loading, reload } = useLoad<Row>(`/patients?limit=50&q=${encodeURIComponent(q)}`);
  const [err, setErr] = useState(""); const can = user.role !== "auditor";
  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = e.currentTarget; const f = new FormData(form); setErr("");
    try { await post("/patients", { patient_id: f.get("id"), full_name: f.get("n"), age: Number(f.get("a")), gender: f.get("g") }); form.reset(); reload(); } catch (x) { setErr((x as Error).message); }
  }
  return <div className="grid">{can && <form className="card f" onSubmit={add}><label>Identificador interno<input name="id" pattern="[A-Za-z0-9_-]{1,64}" required placeholder="SYN-001" /></label>
    <label>Nombre (sintético)<input name="n" required /></label><label>Edad<input name="a" type="number" min={0} max={120} required /></label>
    <label>Sexo<select name="g" defaultValue="unknown"><option value="unknown">No especificado</option><option value="female">Femenino</option><option value="male">Masculino</option><option value="other">Otro</option></select></label>
    <div><button className="primary">Registrar paciente</button></div>{err && <p className="msg err" role="alert">{err}</p>}</form>}
    <div className="card"><label>Buscar por identificador<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Comienza con el identificador" /></label>
      <State loading={loading} error={error} empty={data?.total === 0 && !q}>{data?.total === 0 ? <p className="empty">Sin coincidencias.</p> :
      <div className="wrap" tabIndex={0} role="region" aria-label="Tabla de datos"><table><thead><tr><th>ID</th><th>Nombre</th><th>Edad</th><th>Sexo</th></tr></thead><tbody>{data?.items.map((p: Row) => <tr key={p.patient_id}><td>{p.patient_id}</td><td>{p.full_name ?? "Oculto por rol"}</td><td>{p.age ?? "—"}</td><td>{p.gender}</td></tr>)}</tbody></table></div>}</State></div></div>;
}

function History() {
  const [risk, setRisk] = useState(""); const [page, setPage] = useState(0); const L = 15;
  const { data, error, loading } = useLoad<Row>(`/triage/evaluations?limit=${L}&offset=${page * L}${risk ? `&risk=${risk}` : ""}`);
  return <div className="card"><label>Categoría de riesgo<select value={risk} onChange={(e) => { setRisk(e.target.value); setPage(0); }}><option value="">Todas</option>{["Bajo", "Bajo-Medio", "Medio", "Alto"].map((r) => <option key={r}>{r}</option>)}</select></label>
    <State loading={loading} error={error} empty={data?.total === 0}>{data && <><EvalTable rows={data.items} />
      <p>{data.total} evaluaciones · <button className="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>Anterior</button> <button className="ghost" disabled={(page + 1) * L >= data.total} onClick={() => setPage(page + 1)}>Siguiente</button></p></>}</State></div>;
}

function Motor() {
  const { data, error, loading } = useLoad<Row>("/news2/info");
  return <State loading={loading} error={error}>{data && <div className="card"><h2>Motor NEWS2</h2>
    <p className="banner">Estado: {statusText(data.rules_status)}. {data.notice}</p>
    <p>Versión de reglas implementada: <b>{data.algorithm_version}</b></p><p>Fuente de referencia: {data.source}</p>
    <p>Las reglas residen únicamente en el servidor. Cada evaluación guarda la versión usada y los datos de entrada para poder reproducirla.</p></div>}</State>;
}

function Docs() {
  return <div className="card"><h2>Documentación</h2><p>Thinker Bell calcula el puntaje NEWS2 a partir de signos vitales y conserva el historial de evaluaciones y su auditoría.</p>
    <h2>Alcance y limitaciones</h2><p>Entorno de demostración con datos sintéticos. El motor NEWS2 está pendiente de validación clínica; no es un diagnóstico ni un producto sanitario autorizado, y no sustituye el juicio profesional ni el protocolo institucional. No hay modelos de IA ni integraciones externas activas.</p>
    <h2>Guía de uso</h2><p>1) Registra un paciente. 2) Crea una evaluación con sus signos vitales (rol clínico). 3) Consulta el panel y el historial. Los auditores tienen acceso de solo lectura.</p>
    <p>Detalles técnicos y de seguridad: README.md y docs/ en el repositorio.</p></div>;
}

const NAV = [["dash", "Panel de control"], ["eval", "Nueva evaluación"], ["pts", "Pacientes"], ["hist", "Historial"], ["news2", "Motor NEWS2"], ["docs", "Documentación"]] as const;

export default function App() {
  const [user, setUser] = useState<User | null>(null); const [ready, setReady] = useState(false); const [view, setView] = useState<string>("dash"); const [menu, setMenu] = useState(false);
  useEffect(() => { api<User>("/auth/me").then(setUser).catch(() => setUser(null)).finally(() => setReady(true)); }, []);
  if (!ready) return <p className="empty" role="status">Cargando…</p>;
  if (!user) return <Login onLogin={setUser} />;
  const nav = NAV.filter(([k]) => k !== "eval" || user.role === "clinician"); const cur = nav.some(([k]) => k === view) ? view : "dash";
  return <div className="shell"><div className="mobilebar"><b>Thinker Bell</b><button className="ghost" aria-expanded={menu} aria-controls="nav" onClick={() => setMenu(!menu)}>{menu ? "Cerrar menú" : "Menú"}</button></div>
    <nav id="nav" className={menu ? "open" : ""} aria-label="Principal"><div className="brand">Thinker Bell</div>
    {nav.map(([k, l]) => <button key={k} aria-current={cur === k ? "page" : undefined} onClick={() => { setView(k); setMenu(false); }}>{l}</button>)}
    <div className="who">{user.username} · {user.role}<br /><button className="ghost" onClick={() => post("/auth/logout", {}).finally(() => setUser(null))}>Cerrar sesión</button></div></nav>
    <main><header className="top"><h1>{nav.find(([k]) => k === cur)![1]}</h1></header>
      <p className="banner">Demostración con datos sintéticos · Reglas NEWS2 pendientes de validación clínica · No es un diagnóstico.</p>
      {cur === "dash" && <Dashboard />}{cur === "eval" && <NewEvaluation />}{cur === "pts" && <Patients user={user} />}{cur === "hist" && <History />}{cur === "news2" && <Motor />}{cur === "docs" && <Docs />}</main></div>;
}

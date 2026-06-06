"use client";
import { useEffect, useRef, useState } from "react";
type Job = {
  id: string;
  title: string;
  company: string;
  location: string;
  source: string;
  url: string;
  description: string;
  work_mode: string;
  job_type: string;
  score: number;
  match_type: string;
  explanation: string;
  matched_skills: string[];
  missing_skills: string[];
};
type Search = {
  results: Job[];
  total_count: number;
  page: number;
  has_more: boolean;
  duration_ms: number;
  dataset: string;
  model: string;
};
type Query = {
  query: string;
  profile: string;
  work_mode: string;
  job_type: string;
  countries: string[];
  sources: string[];
  mode: string;
  page: number;
  page_size: number;
};
type Meta = {
  countries: string[];
  sources: string[];
  jobs: number;
  dataset: string;
  collected_at: string;
};
export default function Home() {
  const [query, setQuery] = useState("");
  const [profile, setProfile] = useState("");
  const [work, setWork] = useState("");
  const [type, setType] = useState("");
  const [country, setCountry] = useState("");
  const [source, setSource] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [meta, setMeta] = useState<Meta>();
  const [data, setData] = useState<Search>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<Job[]>([]);
  const [savedView, setSavedView] = useState(false);
  const [detail, setDetail] = useState<Job>();
  const [arabic, setArabic] = useState(false);
  const submitted = useRef<Query | null>(null);
  const abort = useRef<AbortController | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const t = (en: string, ar: string) => (arabic ? ar : en);
  useEffect(() => {
    fetch("/api/v1/metadata")
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then(setMeta)
      .catch(() =>
        setError("The API is unavailable. Start the local services and retry."),
      );
    try {
      const v = JSON.parse(localStorage.getItem("nextrole-saved") || "[]");
      if (Array.isArray(v))
        setSaved(
          v.filter(
            (j) => j && typeof j.id === "string" && typeof j.title === "string",
          ),
        );
    } catch {
      /* stale browser storage */
    }
    return () => abort.current?.abort();
  }, []);
  useEffect(() => {
    document.documentElement.lang = arabic ? "ar" : "en";
    document.documentElement.dir = arabic ? "rtl" : "ltr";
  }, [arabic]);
  useEffect(() => {
    if (detail) dialog.current?.showModal();
  }, [detail]);
  function save(job: Job) {
    const next = saved.some((j) => j.id === job.id)
      ? saved.filter((j) => j.id !== job.id)
      : [...saved, job];
    setSaved(next);
    try {
      localStorage.setItem("nextrole-saved", JSON.stringify(next));
    } catch {
      setError(
        "Browser storage is unavailable; saved jobs will last for this session.",
      );
    }
  }
  async function search(nextPage = false, override?: string) {
    const text = (override ?? query).trim();
    if (!nextPage && !text) {
      setError(
        t(
          "Enter a role or skill to search.",
          "أدخل المسمى الوظيفي أو المهارة.",
        ),
      );
      return;
    }
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    const request: Query =
      nextPage && submitted.current
        ? { ...submitted.current, page: (data?.page ?? 1) + 1 }
        : {
            query: text,
            profile,
            work_mode: work,
            job_type: type,
            countries: country ? [country] : [],
            sources: source ? [source] : [],
            mode,
            page: 1,
            page_size: 8,
          };
    setBusy(true);
    setError("");
    setSavedView(false);
    if (!nextPage) setData(undefined);
    try {
      const res = await fetch("/api/v1/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: controller.signal,
      });
      const result = await res.json();
      if (!res.ok) throw Error(result.error || "Search failed");
      if (controller.signal.aborted) return;
      submitted.current = request;
      setData((old) => ({
        ...result,
        results: nextPage
          ? [...(old?.results ?? []), ...result.results]
          : result.results,
      }));
    } catch (e) {
      if (!controller.signal.aborted)
        setError(
          e instanceof Error ? e.message : "Search failed. Please retry.",
        );
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  const results = savedView ? saved : (data?.results ?? []);
  const sourceURL = (url: string) => {
    try {
      const u = new URL(url);
      return u.protocol === "https:" ? u.href : undefined;
    } catch {
      return undefined;
    }
  };
  return (
    <>
      <a href="#search" className="skip">
        Skip to search
      </a>
      <header className="top">
        <a href="/" className="brand" aria-label="NextRole home">
          <span className="logo">N↗</span>NextRole
        </a>
        <nav aria-label="Main navigation">
          <button
            className={!savedView ? "nav active" : "nav"}
            onClick={() => setSavedView(false)}
          >
            {t("Discover", "اكتشف")}
          </button>
          <button
            className={savedView ? "nav active" : "nav"}
            onClick={() => setSavedView(true)}
          >
            {t("Saved", "المحفوظة")}{" "}
            <span className="count">{saved.length}</span>
          </button>
        </nav>
        <button className="language" onClick={() => setArabic(!arabic)}>
          {arabic ? "English" : "العربية"}
        </button>
      </header>
      <main>
        <section className="hero">
          <div className="eyebrow">
            {t("YOUR NEXT CHAPTER", "خطوتك المهنية القادمة")}
          </div>
          <h1>
            {t("Good work starts with", "الفرصة المناسبة تبدأ بـ")}
            <br />
            <em>{t("the right match.", "التوافق المناسب.")}</em>
          </h1>
          <p>
            {t(
              "Explore roles around your skills, your preferences, and where you want to go next. Understand every recommendation.",
              "اكتشف الفرص حسب مهاراتك وتفضيلاتك وطموحاتك، وافهم سبب كل توصية.",
            )}
          </p>
          <div className="hero-note">
            <span className="dot" />
            {t(
              "No account. No behavioural tracking. You’re in control.",
              "دون حساب أو تتبع سلوكي. أنت تتحكم بالتفضيلات.",
            )}
          </div>
        </section>
        <div className="workspace">
          <aside>
            <form
              id="search"
              onSubmit={(e) => {
                e.preventDefault();
                void search();
              }}
            >
              <div className="section-label">
                01 / {t("YOUR SEARCH", "بحثك")}
              </div>
              <h2>{t("What’s next for you?", "ما خطوتك القادمة؟")}</h2>
              <label htmlFor="role">
                {t("Role or skills", "المسمى أو المهارات")}
              </label>
              <input
                id="role"
                maxLength={200}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("e.g. Flutter Developer", "مثال: مطور تطبيقات")}
                required
              />
              <label htmlFor="profile">
                {t("Candidate context", "نبذة عن الخبرات")}{" "}
                <span>{t("(optional)", "(اختياري)")}</span>
              </label>
              <textarea
                id="profile"
                maxLength={6000}
                rows={4}
                value={profile}
                onChange={(e) => setProfile(e.target.value)}
                placeholder={t(
                  "Paste relevant skills and experience. Omit your name and contact details.",
                  "أضف المهارات والخبرات دون الاسم أو بيانات الاتصال.",
                )}
              />
              <p className="hint">
                {t(
                  "Processed locally for this request. Not stored by the API. Long text is truncated by the encoder.",
                  "تعالج محلياً لهذا الطلب ولا تخزن في الخادم. النص الطويل يختصر بواسطة النموذج.",
                )}
              </p>
              <div className="pair">
                <div>
                  <label htmlFor="work">{t("Work style", "نمط العمل")}</label>
                  <select
                    id="work"
                    value={work}
                    onChange={(e) => setWork(e.target.value)}
                  >
                    <option value="">{t("Any style", "الكل")}</option>
                    <option value="remote">Remote</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="onsite">On-site</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="type">{t("Job type", "نوع الوظيفة")}</label>
                  <select
                    id="type"
                    value={type}
                    onChange={(e) => setType(e.target.value)}
                  >
                    <option value="">{t("Any type", "الكل")}</option>
                    <option value="full_time">Full-time</option>
                    <option value="part_time">Part-time</option>
                    <option value="contract">Contract</option>
                    <option value="internship">Internship</option>
                  </select>
                </div>
              </div>
              <label htmlFor="country">{t("Country", "الدولة")}</label>
              <select
                id="country"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
              >
                <option value="">
                  {t("All / unspecified", "الكل / غير محدد")}
                </option>
                {meta?.countries.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
              <label htmlFor="source">{t("Source", "المصدر")}</label>
              <select
                id="source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
              >
                <option value="">{t("All sources", "كل المصادر")}</option>
                {meta?.sources.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
              <details>
                <summary>
                  {t("Recommendation settings", "إعدادات التوصية")}
                </summary>
                <label htmlFor="mode">
                  {t("Ranking strategy", "طريقة الترتيب")}
                </label>
                <select
                  id="mode"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
                  <option value="hybrid">Hybrid · exact + semantic</option>
                  <option value="exact">Exact title only</option>
                  <option value="semantic">Semantic only</option>
                </select>
              </details>
              <button className="primary" disabled={busy} type="submit">
                {busy
                  ? t("Finding your matches…", "جار البحث…")
                  : t("Find my next role ↗", "ابحث عن فرصتي ↗")}
              </button>
            </form>
            <div className="aside-note">
              <strong>{t("A score, explained.", "درجة مع تفسير.")}</strong>
              <p>
                {t(
                  "Similarity helps you explore. It is not a qualification check or a prediction of being hired.",
                  "التشابه يساعدك على الاستكشاف ولا يتحقق من المؤهلات أو يتنبأ بالتوظيف.",
                )}
              </p>
            </div>
          </aside>
          <section
            className="results"
            aria-labelledby="results-title"
            aria-busy={busy}
          >
            <div className="result-head">
              <div>
                <div className="section-label">
                  02 / {t("OPPORTUNITIES", "الفرص")}
                </div>
                <h2 id="results-title">
                  {savedView
                    ? t("Your shortlist", "قائمتك المختصرة")
                    : t("Discover your possibilities", "اكتشف فرصك")}
                </h2>
              </div>
              <span className="pill">
                {savedView
                  ? saved.length
                  : (data?.total_count ?? meta?.jobs ?? "—")}{" "}
                {t("roles", "وظيفة")}
              </span>
            </div>
            <p className="dataset">
              {meta?.dataset === "synthetic-functional-fixtures"
                ? t(
                    "Demonstration dataset · fictional vacancies for reproducible testing.",
                    "بيانات تجريبية · وظائف خيالية لاختبار قابل للتكرار.",
                  )
                : t("Public-feed snapshot", "لقطة بيانات عامة")}{" "}
              {meta?.sources.join(" + ")}
              {meta?.collected_at ? " · " + meta.collected_at.slice(0, 10) : ""}
            </p>
            {error && (
              <div className="error" role="alert">
                {error}
                <button onClick={() => void search()} disabled={busy}>
                  {t("Retry search", "إعادة المحاولة")}
                </button>
              </div>
            )}
            <div role="status" aria-live="polite" className="status">
              {busy
                ? t("Searching…", "جار البحث…")
                : data && !savedView
                  ? `${data.total_count} ${t("matches", "نتيجة")} · ${Math.round(data.duration_ms)} ms · ${submitted.current?.mode}`
                  : ""}
            </div>
            {!data && !busy && !savedView && (
              <div className="welcome">
                <span className="compass">↗</span>
                <h3>
                  {t(
                    "A little direction. A lot of possibility.",
                    "حدد اتجاهك واستكشف الفرص.",
                  )}
                </h3>
                <p>
                  {t(
                    "Start with a role, or try a suggestion below. Add your experience to discover related titles too.",
                    "ابدأ بمسمى أو جرّب أحد الاقتراحات. أضف خبرتك لاكتشاف مسميات مشابهة.",
                  )}
                </p>
                <div className="chips">
                  {[
                    "Flutter Developer",
                    "Data Analyst",
                    "Backend Developer",
                    "مطور تطبيقات",
                  ].map((s) => (
                    <button
                      key={s}
                      onClick={() => {
                        setQuery(s);
                        void search(false, s);
                      }}
                    >
                      {s} ↗
                    </button>
                  ))}
                </div>
              </div>
            )}
            {!busy && results.length === 0 && (data || savedView) && (
              <div className="welcome">
                <h3>
                  {t(
                    savedView
                      ? "Your shortlist starts here."
                      : "No matches for these preferences.",
                    "لا توجد نتائج حالياً.",
                  )}
                </h3>
                <p>
                  {t(
                    savedView
                      ? "Save a role to compare it later on this device."
                      : "Try a broader role or remove a filter. Unknown attributes are excluded when a filter is selected.",
                    "جرّب مسمى أوسع أو أزل أحد المرشحات.",
                  )}
                </p>
              </div>
            )}
            <div className="cards">
              {results.map((job) => (
                <article className="job" key={job.id}>
                  <div className="job-top">
                    <span className="company-mark">
                      {job.company.slice(0, 2).toUpperCase()}
                    </span>
                    <div className="company">
                      {job.company}
                      <small>
                        {job.location ||
                          t("Location not specified", "الموقع غير محدد")}
                      </small>
                    </div>
                    <button
                      aria-label={`${saved.some((j) => j.id === job.id) ? "Unsave" : "Save"} ${job.title}`}
                      aria-pressed={saved.some((j) => j.id === job.id)}
                      className="save"
                      onClick={() => save(job)}
                    >
                      {saved.some((j) => j.id === job.id) ? "★" : "☆"}
                    </button>
                  </div>
                  <h3>
                    <button
                      className="title-button"
                      onClick={() => setDetail(job)}
                    >
                      {job.title}
                    </button>
                  </h3>
                  <div className="tags">
                    <span>
                      {job.work_mode ||
                        t("Work style unspecified", "النمط غير محدد")}
                    </span>
                    <span>{job.source}</span>
                  </div>
                  <p className="description">
                    {job.description.slice(0, 155)}
                    {job.description.length > 155 ? "…" : ""}
                  </p>
                  <div className="match">
                    <span>
                      {job.match_type === "exact"
                        ? t("Exact title match", "تطابق المسمى")
                        : t("Semantic similarity", "تشابه دلالي")}
                    </span>
                    <strong>{job.score.toFixed(2)}</strong>
                  </div>
                  <button className="explain" onClick={() => setDetail(job)}>
                    {t("Why this role?", "لماذا هذه الوظيفة؟")} <span>↗</span>
                  </button>
                </article>
              ))}
            </div>
            {data?.has_more && !savedView && (
              <button
                className="load"
                onClick={() => void search(true)}
                disabled={busy}
              >
                {t("Load more opportunities", "تحميل المزيد")}
              </button>
            )}
          </section>
        </div>
      </main>
      <footer>
        NextRole{" "}
        <span>
          CM3070 · {t("Transparent job discovery", "اكتشاف الوظائف بشفافية")}
        </span>
      </footer>
      <dialog
        ref={dialog}
        onClose={() => setDetail(undefined)}
        aria-labelledby="detail-title"
      >
        <button
          className="close"
          onClick={() => dialog.current?.close()}
          aria-label="Close details"
        >
          ×
        </button>
        {detail && (
          <>
            <div className="section-label">{detail.company}</div>
            <h2 id="detail-title">{detail.title}</h2>
            <p>
              {detail.location} · {detail.source}
            </p>
            <div className="explanation">
              <strong>
                {t("Why this role appeared", "سبب ظهور هذه الوظيفة")}
              </strong>
              <p>{detail.explanation}</p>
              <p>
                {t("Ranking score", "درجة الترتيب")}: {detail.score.toFixed(3)}{" "}
                · {detail.match_type}
              </p>
            </div>
            <h3>
              {t("Skills mentioned in your text", "مهارات مذكورة في نصك")}
            </h3>
            <p>
              {detail.matched_skills.join(", ") ||
                t("No explicit overlap detected.", "لم يتم رصد تطابق صريح.")}
            </p>
            <h3>
              {t("Skills to check against the vacancy", "مهارات للتحقق منها")}
            </h3>
            <p>
              {detail.missing_skills.join(", ") ||
                t(
                  "No additional recognised skills.",
                  "لا توجد مهارات إضافية معروفة.",
                )}
            </p>
            <p className="hint">
              {t(
                "This is text overlap, not an assessment of your ability. Skills lists use a small fixed vocabulary.",
                "هذه مقارنة نصية وليست تقييماً لقدراتك، وتستخدم قائمة مهارات محدودة.",
              )}
            </p>
            <h3>{t("About the role", "عن الوظيفة")}</h3>
            <p className="full-description">{detail.description}</p>
            {sourceURL(detail.url) && (
              <a
                className="primary external"
                href={sourceURL(detail.url)}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("View original vacancy ↗", "عرض الوظيفة الأصلية ↗")}
              </a>
            )}
          </>
        )}
      </dialog>
    </>
  );
}

#!/usr/bin/env python3
"""
Chrome 사용기록 분석기 (로컬 전용 데스크톱 GUI)

이 PC에 저장된 Chrome(또는 Chromium 계열 브라우저)의 History SQLite 파일을 읽어
방문 도메인 통계, 시간대별 방문 분포, 검색어 사용 현황을 보여주는 도구입니다.
모든 분석은 로컬에서만 수행되며 어떤 데이터도 외부로 전송하지 않습니다.

실행 방법:
    python3 chrome_history_analyzer.py

필요 사항:
    - Python 3.8 이상
    - tkinter (Windows/macOS 공식 설치본은 기본 포함. Linux는 `sudo apt install python3-tk` 필요할 수 있음)
    - 표준 라이브러리 외 추가 설치 불필요
"""

import csv
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
import tkinter as tk
import webbrowser
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import parse_qs, urlparse

CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)
DISPLAY_ROW_CAP = 5000

PERIOD_OPTIONS = ["전체", "최근 7일", "최근 30일", "최근 90일", "최근 1년"]
PERIOD_DAYS = {"전체": None, "최근 7일": 7, "최근 30일": 30, "최근 90일": 90, "최근 1년": 365}

SEARCH_ENGINE_PARAMS = [
    ("google.", "q"),
    ("naver.com", "query"),
    ("daum.net", "q"),
    ("bing.com", "q"),
    ("yahoo.", "p"),
    ("duckduckgo.com", "q"),
]


# ---------------------------------------------------------------------------
# Chrome time helpers
# ---------------------------------------------------------------------------

def chrome_time_to_local_dt(chrome_time):
    """Chrome/WebKit timestamp(1601-01-01 기준 마이크로초) -> 로컬 timezone-aware datetime"""
    if not chrome_time:
        return None
    try:
        dt_utc = CHROME_EPOCH + timedelta(microseconds=chrome_time)
        return dt_utc.astimezone()
    except (OverflowError, OSError, ValueError):
        return None


def local_dt_to_chrome_time(dt):
    dt_utc = dt.astimezone(timezone.utc)
    delta = dt_utc - CHROME_EPOCH
    return int(delta.total_seconds() * 1_000_000)


# ---------------------------------------------------------------------------
# Profile discovery
# ---------------------------------------------------------------------------

def discover_profiles():
    """OS별 기본 경로에서 Chrome/Chromium/Edge 프로필의 History 파일을 찾는다."""
    results = []
    system = platform.system()
    home = Path.home()
    bases = []

    if system == "Windows":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            bases.append(("Chrome", Path(local_appdata) / "Google" / "Chrome" / "User Data"))
            bases.append(("Edge", Path(local_appdata) / "Microsoft" / "Edge" / "User Data"))
    elif system == "Darwin":
        bases.append(("Chrome", home / "Library" / "Application Support" / "Google" / "Chrome"))
        bases.append(("Edge", home / "Library" / "Application Support" / "Microsoft Edge"))
    else:
        bases.append(("Chrome", home / ".config" / "google-chrome"))
        bases.append(("Chromium", home / ".config" / "chromium"))
        bases.append(("Edge", home / ".config" / "microsoft-edge"))

    for browser_name, base in bases:
        if not base.exists():
            continue
        try:
            entries = sorted(base.iterdir())
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name == "Default" or entry.name.startswith("Profile "):
                hist = entry / "History"
                if hist.exists():
                    results.append((f"{browser_name} - {entry.name}", str(hist)))
    return results


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def open_history_db(path):
    """Chrome 실행 중이라 파일이 잠겨 있어도 읽을 수 있도록 읽기전용/immutable로 연다.
    실패하면 임시 위치로 복사해서 연다."""
    resolved = Path(path).resolve()
    uri = f"file:{resolved.as_posix()}?immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.execute("SELECT 1 FROM urls LIMIT 1")
        return conn, None
    except sqlite3.Error:
        pass

    tmp_dir = tempfile.mkdtemp(prefix="chrome_history_")
    tmp_path = Path(tmp_dir) / "History_copy"
    shutil.copy2(resolved, tmp_path)
    conn = sqlite3.connect(str(tmp_path))
    return conn, tmp_dir


def load_visits(conn, since_dt=None):
    query = (
        "SELECT urls.url, urls.title, urls.visit_count, visits.visit_time "
        "FROM visits JOIN urls ON visits.url = urls.id"
    )
    params = []
    if since_dt is not None:
        query += " WHERE visits.visit_time >= ?"
        params.append(local_dt_to_chrome_time(since_dt))
    query += " ORDER BY visits.visit_time DESC"

    rows = []
    for url, title, visit_count, visit_time in conn.execute(query, params):
        dt = chrome_time_to_local_dt(visit_time)
        if dt is None:
            continue
        domain = urlparse(url).netloc or "(알 수 없음)"
        rows.append({
            "url": url,
            "title": (title or "").strip() or "(제목 없음)",
            "visit_count": visit_count,
            "visit_time": dt,
            "domain": domain,
        })
    return rows


def guess_search_engine(url):
    domain = urlparse(url).netloc
    if "google." in domain:
        return "Google"
    if "naver.com" in domain:
        return "Naver"
    if "daum.net" in domain:
        return "Daum"
    if "bing.com" in domain:
        return "Bing"
    if "yahoo." in domain:
        return "Yahoo"
    if "duckduckgo.com" in domain:
        return "DuckDuckGo"
    return domain or "기타"


def load_search_terms_from_keyword_table(conn, since_dt=None):
    results = []
    try:
        query = (
            "SELECT kst.term, urls.url, urls.last_visit_time "
            "FROM keyword_search_terms kst JOIN urls ON kst.url_id = urls.id"
        )
        for term, url, last_visit_time in conn.execute(query):
            dt = chrome_time_to_local_dt(last_visit_time)
            if since_dt is not None and dt is not None and dt < since_dt:
                continue
            if not term:
                continue
            results.append({"term": term, "engine": guess_search_engine(url), "last_visit": dt})
    except sqlite3.OperationalError:
        pass
    return results


def extract_search_terms_fallback(rows):
    extracted = []
    for r in rows:
        parsed = urlparse(r["url"])
        qs = parse_qs(parsed.query)
        for domain_key, param in SEARCH_ENGINE_PARAMS:
            if domain_key in r["domain"] and param in qs:
                term = (qs[param][0] or "").strip()
                if term:
                    extracted.append({"term": term, "engine": guess_search_engine(r["url"]), "last_visit": r["visit_time"]})
                break
    return extracted


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_domains(rows):
    counter = Counter()
    first_seen = {}
    last_seen = {}
    for r in rows:
        d = r["domain"]
        counter[d] += 1
        if d not in first_seen or r["visit_time"] < first_seen[d]:
            first_seen[d] = r["visit_time"]
        if d not in last_seen or r["visit_time"] > last_seen[d]:
            last_seen[d] = r["visit_time"]
    return counter, first_seen, last_seen


def aggregate_hourly(rows):
    hours = [0] * 24
    for r in rows:
        hours[r["visit_time"].hour] += 1
    return hours


def aggregate_search_terms(terms):
    counter = Counter()
    engine_map = {}
    last_seen = {}
    for t in terms:
        key = t["term"]
        counter[key] += 1
        engine_map[key] = t["engine"]
        if t["last_visit"] and (key not in last_seen or t["last_visit"] > last_seen[key]):
            last_seen[key] = t["last_visit"]
    return counter, engine_map, last_seen


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class ChromeHistoryAnalyzerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chrome 사용기록 분석기 (로컬 전용)")
        self.geometry("1180x760")
        self.minsize(900, 600)

        self.profiles = discover_profiles()
        self.manual_path = None
        self.rows = []
        self.search_terms = []

        self._build_top_bar()
        self._build_notebook()
        self._build_footer()

        if self.profiles:
            self.profile_combo.current(0)
        else:
            self.status_label.config(text="자동으로 감지된 Chrome 프로필이 없습니다. '파일 직접 선택'을 이용하세요.")

    # -- layout -------------------------------------------------------
    def _build_top_bar(self):
        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="프로필:").pack(side="left")
        self.profile_combo = ttk.Combobox(
            bar, state="readonly", width=32,
            values=[label for label, _ in self.profiles],
        )
        self.profile_combo.pack(side="left", padx=(4, 8))

        ttk.Button(bar, text="새로고침", command=self.refresh_profiles).pack(side="left")
        ttk.Button(bar, text="파일 직접 선택...", command=self.choose_file).pack(side="left", padx=(6, 14))

        ttk.Label(bar, text="분석 기간:").pack(side="left")
        self.period_combo = ttk.Combobox(bar, state="readonly", width=12, values=PERIOD_OPTIONS)
        self.period_combo.current(0)
        self.period_combo.pack(side="left", padx=(4, 14))

        ttk.Button(bar, text="분석 시작", command=self.run_analysis).pack(side="left")

        self.status_label = ttk.Label(bar, text="프로필과 기간을 선택한 뒤 '분석 시작'을 누르세요.")
        self.status_label.pack(side="left", padx=(16, 0))

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 8))

        self.tab_summary = ttk.Frame(self.notebook)
        self.tab_domains = ttk.Frame(self.notebook)
        self.tab_visits = ttk.Frame(self.notebook)
        self.tab_search = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_summary, text="요약")
        self.notebook.add(self.tab_domains, text="도메인별 통계")
        self.notebook.add(self.tab_visits, text="방문 기록 상세")
        self.notebook.add(self.tab_search, text="검색어 분석")

        self._build_summary_tab()
        self._build_domains_tab()
        self._build_visits_tab()
        self._build_search_tab()

    def _build_summary_tab(self):
        top = ttk.Frame(self.tab_summary, padding=10)
        top.pack(side="top", fill="x")
        self.summary_info = ttk.Label(top, text="", justify="left", font=("TkDefaultFont", 10))
        self.summary_info.pack(side="left")

        charts = ttk.Frame(self.tab_summary, padding=10)
        charts.pack(side="top", fill="both", expand=True)

        left = ttk.LabelFrame(charts, text="가장 많이 방문한 도메인 Top 10")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.domain_chart = tk.Canvas(left, background="white", height=340)
        self.domain_chart.pack(fill="both", expand=True, padx=6, pady=6)

        right = ttk.LabelFrame(charts, text="시간대별 방문 분포 (0~23시)")
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.hour_chart = tk.Canvas(right, background="white", height=340)
        self.hour_chart.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_domains_tab(self):
        toolbar = ttk.Frame(self.tab_domains, padding=(10, 6))
        toolbar.pack(side="top", fill="x")
        ttk.Button(toolbar, text="CSV로 내보내기", command=self.export_domains_csv).pack(side="right")

        columns = ("rank", "domain", "count", "pct", "first", "last")
        headers = {"rank": "순위", "domain": "도메인", "count": "방문 횟수", "pct": "비율(%)", "first": "최초 방문", "last": "최근 방문"}
        self.domain_tree = ttk.Treeview(self.tab_domains, columns=columns, show="headings")
        for c in columns:
            self.domain_tree.heading(c, text=headers[c])
            self.domain_tree.column(c, width=140 if c != "domain" else 260, anchor="w")
        self.domain_tree.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

    def _build_visits_tab(self):
        toolbar = ttk.Frame(self.tab_visits, padding=(10, 6))
        toolbar.pack(side="top", fill="x")
        ttk.Label(toolbar, text="검색:").pack(side="left")
        self.visit_search_var = tk.StringVar()
        self.visit_search_var.trace_add("write", lambda *_: self.render_visits())
        ttk.Entry(toolbar, textvariable=self.visit_search_var, width=40).pack(side="left", padx=(4, 14))
        ttk.Button(toolbar, text="선택 항목 브라우저에서 열기", command=self.open_selected_visit).pack(side="left")
        ttk.Button(toolbar, text="CSV로 내보내기", command=self.export_visits_csv).pack(side="right")

        columns = ("time", "title", "url", "domain")
        headers = {"time": "방문시각", "title": "제목", "url": "URL", "domain": "도메인"}
        self.visit_tree = ttk.Treeview(self.tab_visits, columns=columns, show="headings")
        for c in columns:
            self.visit_tree.heading(c, text=headers[c])
        self.visit_tree.column("time", width=150, anchor="w")
        self.visit_tree.column("title", width=260, anchor="w")
        self.visit_tree.column("url", width=380, anchor="w")
        self.visit_tree.column("domain", width=160, anchor="w")
        self.visit_tree.pack(side="top", fill="both", expand=True, padx=10)

        self.visit_cap_label = ttk.Label(self.tab_visits, text="")
        self.visit_cap_label.pack(side="top", anchor="w", padx=10, pady=(4, 10))

    def _build_search_tab(self):
        toolbar = ttk.Frame(self.tab_search, padding=(10, 6))
        toolbar.pack(side="top", fill="x")
        ttk.Button(toolbar, text="CSV로 내보내기", command=self.export_search_csv).pack(side="right")

        columns = ("term", "engine", "count", "last")
        headers = {"term": "검색어", "engine": "검색엔진", "count": "검색 횟수", "last": "최근 검색일"}
        self.search_tree = ttk.Treeview(self.tab_search, columns=columns, show="headings")
        for c in columns:
            self.search_tree.heading(c, text=headers[c])
            self.search_tree.column(c, width=200 if c == "term" else 140, anchor="w")
        self.search_tree.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

    def _build_footer(self):
        ttk.Separator(self).pack(side="top", fill="x")
        ttk.Label(
            self,
            text="본 프로그램은 이 PC에 저장된 Chrome 방문 기록만 로컬에서 읽어 분석하며, 어떤 데이터도 외부로 전송하지 않습니다.",
            padding=(10, 6),
            foreground="#666",
        ).pack(side="top", fill="x")

    # -- profile handling ----------------------------------------------
    def refresh_profiles(self):
        self.profiles = discover_profiles()
        self.profile_combo["values"] = [label for label, _ in self.profiles]
        if self.profiles:
            self.profile_combo.current(0)
            self.manual_path = None
            self.status_label.config(text=f"{len(self.profiles)}개 프로필을 찾았습니다.")
        else:
            self.status_label.config(text="자동으로 감지된 프로필이 없습니다. '파일 직접 선택'을 이용하세요.")

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Chrome History 파일 선택",
            filetypes=[("Chrome History (SQLite)", "History"), ("모든 파일", "*.*")],
        )
        if path:
            self.manual_path = path
            self.profile_combo.set("")
            self.status_label.config(text=f"선택된 파일: {path}")

    def get_selected_history_path(self):
        if self.manual_path:
            return self.manual_path
        idx = self.profile_combo.current()
        if idx is None or idx < 0 or idx >= len(self.profiles):
            return None
        return self.profiles[idx][1]

    def get_since_datetime(self):
        label = self.period_combo.get() or "전체"
        days = PERIOD_DAYS.get(label)
        if days is None:
            return None
        return datetime.now(timezone.utc).astimezone() - timedelta(days=days)

    # -- analysis --------------------------------------------------------
    def run_analysis(self):
        path = self.get_selected_history_path()
        if not path:
            messagebox.showwarning("알림", "먼저 Chrome 프로필을 선택하거나 History 파일을 지정하세요.")
            return
        if not Path(path).exists():
            messagebox.showerror("오류", f"파일을 찾을 수 없습니다:\n{path}")
            return

        self.status_label.config(text="분석 중...")
        self.update_idletasks()

        tmp_dir = None
        try:
            conn, tmp_dir = open_history_db(path)
            since_dt = self.get_since_datetime()
            self.rows = load_visits(conn, since_dt)
            terms = load_search_terms_from_keyword_table(conn, since_dt)
            if not terms:
                terms = extract_search_terms_fallback(self.rows)
            self.search_terms = terms
            conn.close()
        except Exception as e:
            messagebox.showerror("오류", f"History 파일을 분석하는 중 문제가 발생했습니다:\n{e}")
            self.status_label.config(text="분석 실패")
            return
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        self.render_summary()
        self.render_domains()
        self.render_visits()
        self.render_search_terms()

        period_label = self.period_combo.get() or "전체"
        self.status_label.config(
            text=f"[{period_label}] 총 {len(self.rows):,}건의 방문 기록, 검색어 {len(self.search_terms):,}건을 불러왔습니다."
        )

    # -- rendering: summary ------------------------------------------
    def render_summary(self):
        rows = self.rows
        if not rows:
            self.summary_info.config(text="표시할 데이터가 없습니다.")
            self.domain_chart.delete("all")
            self.hour_chart.delete("all")
            return

        counter, first_seen, last_seen = aggregate_domains(rows)
        earliest = min(r["visit_time"] for r in rows)
        latest = max(r["visit_time"] for r in rows)
        fmt = "%Y-%m-%d %H:%M"
        info_text = (
            f"분석 기간: {earliest.strftime(fmt)}  ~  {latest.strftime(fmt)}\n"
            f"총 방문 횟수: {len(rows):,}건\n"
            f"고유 도메인 수: {len(counter):,}개"
        )
        self.summary_info.config(text=info_text)

        top10 = counter.most_common(10)
        self.after(50, lambda: draw_horizontal_bars(self.domain_chart, top10))

        hours = aggregate_hourly(rows)
        self.after(50, lambda: draw_hour_bars(self.hour_chart, hours))

    # -- rendering: domains --------------------------------------------
    def render_domains(self):
        for item in self.domain_tree.get_children():
            self.domain_tree.delete(item)
        if not self.rows:
            return
        counter, first_seen, last_seen = aggregate_domains(self.rows)
        total = sum(counter.values()) or 1
        fmt = "%Y-%m-%d %H:%M"
        for rank, (domain, count) in enumerate(counter.most_common(), start=1):
            pct = round(count / total * 100, 1)
            self.domain_tree.insert("", "end", values=(
                rank, domain, count, pct,
                first_seen[domain].strftime(fmt), last_seen[domain].strftime(fmt),
            ))

    def export_domains_csv(self):
        if not self.rows:
            messagebox.showinfo("알림", "내보낼 데이터가 없습니다.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="domain_stats.csv")
        if not path:
            return
        counter, first_seen, last_seen = aggregate_domains(self.rows)
        total = sum(counter.values()) or 1
        fmt = "%Y-%m-%d %H:%M"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Rank", "Domain", "VisitCount", "Percent", "FirstVisit", "LastVisit"])
            for rank, (domain, count) in enumerate(counter.most_common(), start=1):
                w.writerow([rank, domain, count, round(count / total * 100, 1),
                            first_seen[domain].strftime(fmt), last_seen[domain].strftime(fmt)])
        messagebox.showinfo("완료", f"저장되었습니다:\n{path}")

    # -- rendering: visits ------------------------------------------------
    def filtered_visits(self):
        term = (self.visit_search_var.get() or "").strip().lower()
        if not term:
            return self.rows
        return [r for r in self.rows if term in r["title"].lower() or term in r["url"].lower() or term in r["domain"].lower()]

    def render_visits(self):
        for item in self.visit_tree.get_children():
            self.visit_tree.delete(item)
        rows = self.filtered_visits()
        fmt = "%Y-%m-%d %H:%M:%S"
        shown = rows[:DISPLAY_ROW_CAP]
        for r in shown:
            self.visit_tree.insert("", "end", values=(r["visit_time"].strftime(fmt), r["title"], r["url"], r["domain"]))
        if len(rows) > DISPLAY_ROW_CAP:
            self.visit_cap_label.config(
                text=f"전체 {len(rows):,}건 중 최신 {DISPLAY_ROW_CAP:,}건만 표시됩니다. 전체 내역은 CSV로 내보내세요."
            )
        else:
            self.visit_cap_label.config(text=f"{len(rows):,}건 표시 중")

    def open_selected_visit(self):
        sel = self.visit_tree.selection()
        if not sel:
            messagebox.showinfo("알림", "먼저 목록에서 항목을 선택하세요.")
            return
        url = self.visit_tree.item(sel[0], "values")[2]
        webbrowser.open(url)

    def export_visits_csv(self):
        rows = self.filtered_visits()
        if not rows:
            messagebox.showinfo("알림", "내보낼 데이터가 없습니다.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="visit_history.csv")
        if not path:
            return
        fmt = "%Y-%m-%d %H:%M:%S"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["VisitTime", "Title", "URL", "Domain", "VisitCount"])
            for r in rows:
                w.writerow([r["visit_time"].strftime(fmt), r["title"], r["url"], r["domain"], r["visit_count"]])
        messagebox.showinfo("완료", f"저장되었습니다:\n{path}")

    # -- rendering: search terms ------------------------------------------
    def render_search_terms(self):
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        if not self.search_terms:
            return
        counter, engine_map, last_seen = aggregate_search_terms(self.search_terms)
        fmt = "%Y-%m-%d %H:%M"
        for term, count in counter.most_common():
            last = last_seen.get(term)
            self.search_tree.insert("", "end", values=(
                term, engine_map.get(term, ""), count, last.strftime(fmt) if last else "-",
            ))

    def export_search_csv(self):
        if not self.search_terms:
            messagebox.showinfo("알림", "내보낼 검색어 데이터가 없습니다.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="search_terms.csv")
        if not path:
            return
        counter, engine_map, last_seen = aggregate_search_terms(self.search_terms)
        fmt = "%Y-%m-%d %H:%M"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Term", "Engine", "Count", "LastSearched"])
            for term, count in counter.most_common():
                last = last_seen.get(term)
                w.writerow([term, engine_map.get(term, ""), count, last.strftime(fmt) if last else ""])
        messagebox.showinfo("완료", f"저장되었습니다:\n{path}")


# ---------------------------------------------------------------------------
# Canvas chart helpers
# ---------------------------------------------------------------------------

def draw_horizontal_bars(canvas, data):
    canvas.delete("all")
    canvas.update_idletasks()
    width = max(int(canvas.winfo_width()), 300)
    height = max(int(canvas.winfo_height()), 200)
    if not data:
        canvas.create_text(10, 10, anchor="nw", text="데이터가 없습니다.")
        return
    max_val = max(v for _, v in data) or 1
    n = len(data)
    bar_h = max(18, (height - 20) // n)
    label_col_w = 170
    for i, (label, val) in enumerate(data):
        y = 10 + i * bar_h
        bar_w = int((val / max_val) * (width - label_col_w - 70))
        display_label = label if len(label) <= 24 else label[:23] + "…"
        canvas.create_text(6, y + bar_h / 2, anchor="w", text=display_label, font=("TkDefaultFont", 9))
        canvas.create_rectangle(label_col_w, y + 4, label_col_w + max(bar_w, 2), y + bar_h - 4,
                                 fill="#2f6fdb", outline="")
        canvas.create_text(label_col_w + bar_w + 8, y + bar_h / 2, anchor="w", text=f"{val:,}",
                            font=("TkDefaultFont", 9))


def draw_hour_bars(canvas, hours):
    canvas.delete("all")
    canvas.update_idletasks()
    width = max(int(canvas.winfo_width()), 300)
    height = max(int(canvas.winfo_height()), 200)
    max_val = max(hours) or 1
    n = 24
    margin = 20
    bar_w = (width - margin * 2) / n
    base_y = height - 24
    for h, val in enumerate(hours):
        bar_h = (val / max_val) * (height - 50)
        x0 = margin + h * bar_w
        x1 = x0 + bar_w - 3
        y0 = base_y - bar_h
        y1 = base_y
        canvas.create_rectangle(x0, y0, x1, y1, fill="#2f9e58", outline="")
        if h % 3 == 0:
            canvas.create_text((x0 + x1) / 2, base_y + 10, text=str(h), font=("TkDefaultFont", 8))


def main():
    app = ChromeHistoryAnalyzerApp()
    app.mainloop()


if __name__ == "__main__":
    main()

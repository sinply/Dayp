const PALETTE = [
  "#4f8cff", "#36c5a8", "#ffb86c", "#ff6b6b", "#bd93f9",
  "#50fa7b", "#f1fa8c", "#8be9fd", "#ff79c6", "#6272a4",
  "#00b894", "#0984e3", "#e17055", "#fdcb6e", "#a29bfe"
];

function color(i) { return PALETTE[i % PALETTE.length]; }

function fmtSec(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}h${String(m).padStart(2, "0")}m`;
  if (m > 0) return `${m}m${String(s).padStart(2, "0")}s`;
  return `${s}s`;
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function escapeHtml(s) {
  if (!s) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

let todayChart = null;
let weekChart = null;
let currentNewsSource = "";

async function loadTodayUsage() {
  try {
    const data = await getJson("/api/usage/today");
    document.getElementById("todayTotal").textContent = data.total_fmt || "0s";

    const list = document.getElementById("todayList");
    list.innerHTML = data.apps.slice(0, 15).map((a, i) => `
      <div class="app-item">
        <span class="app-name" title="${escapeHtml(a.process_name)}">${escapeHtml(a.process_name)}</span>
        <span class="app-bar"><span class="app-bar-fill" style="width:${a.pct}%;background:${color(i)}"></span></span>
        <span class="app-time">${a.total_fmt}</span>
        <span class="app-pct">${a.pct}%</span>
      </div>
    `).join("");

    const top = data.apps.slice(0, 8);
    if (todayChart) todayChart.destroy();
    todayChart = new Chart(document.getElementById("todayChart"), {
      type: "doughnut",
      data: {
        labels: top.map(a => a.process_name),
        datasets: [{
          data: top.map(a => a.total_sec),
          backgroundColor: top.map((_, i) => color(i)),
          borderWidth: 0,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "right",
            labels: { color: "#8b8f9a", font: { size: 11 }, boxWidth: 12 }
          },
          tooltip: {
            callbacks: { label: (c) => ` ${c.label}: ${fmtSec(c.raw)}` }
          }
        }
      }
    });
  } catch (e) {
    document.getElementById("todayList").innerHTML = `<div class="email-snippet">加载失败: ${escapeHtml(e.message)}</div>`;
  }
}

async function loadWeekUsage() {
  try {
    const data = await getJson("/api/usage/week");
    if (weekChart) weekChart.destroy();
    weekChart = new Chart(document.getElementById("weekChart"), {
      type: "bar",
      data: {
        labels: data.dates.map(d => d.slice(5)),
        datasets: data.series.map((s, i) => ({
          label: s.process_name,
          data: s.data,
          backgroundColor: color(i),
          stack: "stack",
        }))
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { stacked: true, ticks: { color: "#8b8f9a" }, grid: { color: "#2a2e3a" } },
          y: {
            stacked: true,
            ticks: { color: "#8b8f9a", callback: (v) => fmtSec(v) },
            grid: { color: "#2a2e3a" }
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${fmtSec(c.raw)}` } }
        }
      }
    });
  } catch (e) {
    console.error("week usage error", e);
  }
}

async function loadNews() {
  try {
    const url = currentNewsSource
      ? `/api/news?limit=50&source=${encodeURIComponent(currentNewsSource)}`
      : `/api/news?limit=50`;
    const data = await getJson(url);
    const el = document.getElementById("newsList");
    if (!data.items || data.items.length === 0) {
      el.innerHTML = '<div class="email-snippet">暂无新闻，请先启动 agent</div>';
      return;
    }
    el.innerHTML = data.items.map(n => {
      const sourceLabel = n.source === "hn" ? "HN"
        : (n.source === "36kr" ? "36氪"
        : (n.source === "leiphone" ? "雷锋"
        : (n.source === "ifanr" ? "爱范儿"
        : (n.source === "aibase" ? "AIbase"
        : (n.source === "huxiu" ? "虎嗅"
        : n.source)))));
      const scoreHtml = n.source === "hn" && n.score ? `<span class="news-score">${n.score}</span>` : `<span class="news-tag source-${n.source}">${sourceLabel}</span>`;
      return `
      <a class="news-item" href="${escapeHtml(n.url || '#')}" target="_blank" rel="noopener">
        <span class="news-title">${escapeHtml(n.title || '(无标题)')}</span>
        <span class="news-meta">
          ${scoreHtml}
          ${n.by ? `by ${escapeHtml(n.by)} · ` : ''}${fmtDate(n.time)}
        </span>
      </a>
    `}).join("");
  } catch (e) {
    document.getElementById("newsList").innerHTML = `<div class="email-snippet">加载失败: ${escapeHtml(e.message)}</div>`;
  }
}

async function loadEmails() {
  try {
    const days = document.getElementById("emailDays").value;
    const data = await getJson(`/api/emails?days=${days}`);
    const el = document.getElementById("emailList");
    if (!data.emails || data.emails.length === 0) {
      el.innerHTML = '<div class="email-snippet">暂无邮件，请先启动 agent 并确保 Outlook 已登录</div>';
      return;
    }
    el.innerHTML = data.emails.slice(0, 50).map(m => `
      <div class="email-item clickable" data-entry-id="${escapeHtml(m.entry_id || '')}" title="点击在 Outlook 中打开">
        <div class="email-subject">${escapeHtml(m.subject || '(无主题)')}</div>
        <span class="email-from">${escapeHtml(m.sender || '')}</span>
        <span class="email-time">${fmtDate(m.received_at)}</span>
        ${m.snippet ? `<div class="email-snippet">${escapeHtml(m.snippet)}</div>` : ''}
      </div>
    `).join("");

    el.querySelectorAll(".email-item.clickable").forEach(item => {
      item.addEventListener("click", async () => {
        const entryId = item.dataset.entryId;
        if (!entryId) return;
        try {
          item.classList.add("loading");
          const r = await fetch(`/api/emails/${encodeURIComponent(entryId)}/open`);
          if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: r.statusText }));
            alert("打开邮件失败: " + (err.detail || r.statusText));
          }
        } catch (e) {
          alert("打开邮件失败: " + e.message);
        } finally {
          item.classList.remove("loading");
        }
      });
    });
  } catch (e) {
    document.getElementById("emailList").innerHTML = `<div class="email-snippet">加载失败: ${escapeHtml(e.message)}</div>`;
  }
}

async function loadSummary() {
  try {
    const data = await getJson("/api/summary/week");
    document.getElementById("summaryText").textContent = data.text || "无数据";
  } catch (e) {
    document.getElementById("summaryText").textContent = `加载失败: ${e.message}`;
  }
}

document.getElementById("copySummary").addEventListener("click", async () => {
  const text = document.getElementById("summaryText").textContent;
  try {
    await navigator.clipboard.writeText(text);
    const btn = document.getElementById("copySummary");
    const orig = btn.textContent;
    btn.textContent = "已复制";
    setTimeout(() => { btn.textContent = orig; }, 1500);
  } catch (e) {
    alert("复制失败: " + e.message);
  }
});

document.getElementById("refreshBtn").addEventListener("click", async () => {
  const btn = document.getElementById("refreshBtn");
  btn.disabled = true;
  btn.textContent = "刷新中...";
  await Promise.all([
    loadTodayUsage(),
    loadWeekUsage(),
    loadNews(),
    loadEmails(),
    loadSummary(),
  ]);
  btn.disabled = false;
  btn.textContent = "刷新";
});

document.querySelectorAll("#newsFilter .chip").forEach(chip => {
  chip.addEventListener("click", () => {
    document.querySelectorAll("#newsFilter .chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    currentNewsSource = chip.dataset.source;
    loadNews();
  });
});

document.getElementById("emailDays").addEventListener("change", () => {
  loadEmails();
});

function updateClock() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  document.getElementById("clock").textContent =
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

async function init() {
  updateClock();
  setInterval(updateClock, 1000);
  await Promise.all([
    loadTodayUsage(),
    loadWeekUsage(),
    loadNews(),
    loadEmails(),
    loadSummary(),
  ]);
}

init();
setInterval(() => {
  loadTodayUsage();
  loadNews();
  loadEmails();
  loadSummary();
}, 60000);

setInterval(() => {
  fetch("/api/heartbeat", { method: "POST" }).catch(() => {});
}, 5000);
fetch("/api/heartbeat", { method: "POST" }).catch(() => {});

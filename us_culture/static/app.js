const root = document.body;
const date = root.dataset.date;
const playBtn = document.getElementById("play-btn");
const player = document.getElementById("player");
const playerHint = document.getElementById("player-hint");
const jobMsg = document.getElementById("job-msg");
const fetchBtn = document.getElementById("fetch-btn");
const localBtn = document.getElementById("local-btn");
const runBtn = document.getElementById("run-btn");
const jobButtons = [fetchBtn, localBtn, runBtn];

function pad(n) {
  return String(n).padStart(2, "0");
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function safeUrl(url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.href;
    }
  } catch (err) {
    return "";
  }
  return "";
}

function render(data) {
  const brand = document.getElementById("brand-line");
  brand.textContent = `${data.brand.market} · ${data.brand.audience} · ${data.brand.product_line}`;

  const next = document.getElementById("next-run");
  if (data.schedule.next_run_text) {
    next.textContent = `下次推送 ${data.schedule.next_run_text}`;
  } else {
    next.textContent = `每天 ${pad(data.schedule.hour)}:${pad(data.schedule.minute)} ${data.schedule.timezone}`;
  }

  const title = document.getElementById("brief-title");
  const insight = document.getElementById("insight");
  const sectionsEl = document.getElementById("sections");
  const topicsEl = document.getElementById("topics");
  sectionsEl.replaceChildren();
  topicsEl.replaceChildren();

  if (data.briefing) {
    title.textContent = data.briefing.title;
    insight.hidden = false;
    insight.replaceChildren();
    const signal = el("p");
    signal.append(el("strong", "", "今日文化信号 "), document.createTextNode(data.briefing.culture_signal));
    const product = el("p");
    product.append(el("strong", "", "眼睛产品线观察 "), document.createTextNode(data.briefing.product_insight));
    insight.append(signal, product);
    data.briefing.sections.forEach((section) => {
      const wrap = el("div", "section");
      wrap.append(el("h3", "", section.category));
      section.items.forEach((item) => {
        const div = el("div", "item");
        div.append(el("strong", "", item.headline), el("p", "", item.takeaway));
        wrap.append(div);
      });
      sectionsEl.append(wrap);
    });
  } else {
    title.textContent = "今日简报尚未生成";
    insight.hidden = true;
  }

  if (data.topics) {
    const grouped = {};
    data.topics.items.forEach((item) => {
      grouped[item.category] = grouped[item.category] || [];
      grouped[item.category].push(item);
    });
    const heading = el("div", "section");
    heading.append(el("h3", "", "已抓取热点"));
    topicsEl.append(heading);
    data.categories.forEach((category) => {
      const list = grouped[category] || [];
      if (!list.length) return;
      const wrap = el("div", "section");
      wrap.append(el("h3", "", `${category}来源`));
      const ul = el("ul", "topic-list");
      list.forEach((item) => {
        const li = document.createElement("li");
        const href = safeUrl(item.url);
        if (href) {
          const a = el("a", "", item.title);
          a.href = href;
          a.target = "_blank";
          a.rel = "noreferrer";
          li.append(a, document.createTextNode(` · ${item.source}`));
        } else {
          li.textContent = `${item.title} · ${item.source}`;
        }
        ul.append(li);
      });
      wrap.append(ul);
      topicsEl.append(wrap);
    });
  }

  if (data.has_audio && data.audio_url) {
    player.src = data.audio_url;
    playBtn.disabled = false;
    playerHint.textContent = "可在本页直接播放，飞书群里也会收到可点开的语音。";
  } else {
    playBtn.disabled = true;
    player.removeAttribute("src");
    playerHint.textContent = "还没有音频。先生成简报，或等早上定时任务。";
  }
}

async function load() {
  const res = await fetch(`/api/today?date=${encodeURIComponent(date)}`);
  const data = await res.json();
  render(data);
}

playBtn.addEventListener("click", async () => {
  try {
    await player.play();
  } catch (err) {
    jobMsg.textContent = "浏览器拦截了自动播放，请用下方进度条播放。";
  }
});

async function post(url, body) {
  jobMsg.textContent = "任务执行中，请稍候。";
  jobButtons.forEach((btn) => {
    btn.disabled = true;
  });
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data.error || "任务失败");
    }
    jobMsg.textContent = "完成。";
    if (data.date && data.date !== date) {
      window.location.href = `/?date=${data.date}`;
      return;
    }
    await load();
  } catch (err) {
    jobMsg.textContent = err.message;
  } finally {
    jobButtons.forEach((btn) => {
      btn.disabled = false;
    });
  }
}

fetchBtn.addEventListener("click", () => post("/api/fetch"));
localBtn.addEventListener("click", () => post("/api/run", { push: false }));
runBtn.addEventListener("click", () => post("/api/run", { push: true }));

load().catch((err) => {
  jobMsg.textContent = err.message;
});

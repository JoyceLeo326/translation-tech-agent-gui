const galleryItems = {
  overview: {
    image: "./assets/workbench-overview.png",
    alt: "译述开始页面",
    kicker: "开始",
    title: "把素材交给译述，系统自动进入对应流程",
    description: "图片、Word、音频或视频都可以直接选择，测试素材与已有成果在首页即可打开。",
  },
  production: {
    image: "./assets/workbench-production.png",
    alt: "译述文件翻译页面",
    kicker: "文件翻译",
    title: "图片、Word 与音视频共享同一套审校逻辑",
    description: "测试文件、审校表与回填按钮已经接入，不需要使用者手动寻找项目目录。",
  },
  agent: {
    image: "./assets/workbench-agent.png",
    alt: "译述 Coze 多模型精译页面",
    kicker: "Coze 多模型精译",
    title: "重要译文由多路模型初译、互评再融合",
    description: "术语、风格、多路初译、交叉评价和融合终稿都有说明与可验证证据。",
  },
  terms: {
    image: "./assets/workbench-terms.png",
    alt: "译述文化术语库页面",
    kicker: "文化术语",
    title: "译法、出处页码和上下文一起查",
    description: "统一多人协作中的文化概念表达，为人工审校保留来源依据。",
  },
  workflow: {
    image: "./assets/workbench-workflow.png",
    alt: "译述批量处理工作流页面",
    kicker: "批量流程",
    title: "状态、证据和输出位置清楚可查",
    description: "从资源扫描到最终报告，所有环节在同一页面形成完整处理记录。",
  },
  outputs: {
    image: "./assets/workbench-outputs.png",
    alt: "译述导出文件页面",
    kicker: "导出文件",
    title: "老师和审核人员可以直接打开最终成品",
    description: "Word、表格、配音、图片与验收记录集中呈现，不再按协作组查找。",
  },
  settings: {
    image: "./assets/workbench-settings.png",
    alt: "译述模型接口配置页面",
    kicker: "模型接口",
    title: "连接自己的 API，启用在线模型处理",
    description: "支持 OpenAI、Ollama、LM Studio、其他兼容服务和 Coze；密钥只保存在 Windows 本机。",
  },
};

const playgroundItems = {
  text: {
    icon: "languages",
    title: "一段需要精译的中文",
    input: "可补充标题、读者年龄、语气和使用场景。",
    route: ["文化术语与文体判断", "Coze 三路初译与互评", "人工确认终稿"],
    outputTitle: "可审校的融合终稿",
    output: ["术语与儿童文学风格已经约束", "三路初译和交叉评议过程可解释", "终稿仍可由人工修改后入库"],
  },
  image: {
    icon: "scan-text",
    title: "一张含中文的图片",
    input: "支持 JPG、PNG、WebP 等常见格式，视觉模型读取可见文字。",
    route: ["视觉识别与阅读顺序", "术语约束下的中英翻译", "模糊文字人工确认"],
    outputTitle: "中英对照与位置说明",
    output: ["逐条列出中文、英文和所在位置", "主动标记看不清或可能误识别的内容", "可继续进入图文替换和版面回填"],
  },
  docx: {
    icon: "file-text",
    title: "一份需要保留版式的 Word",
    input: "正文、表格、页眉和页脚会统一提取，不直接修改源文档。",
    route: ["生成 Excel 译文确认表", "模型分批翻译 + 人工审校", "Word XML 精确回填"],
    outputTitle: "英文 Word 与回填报告",
    output: ["原有图片、段落和版式结构继续保留", "人工审核列优先于机器译文", "命中条目与中文残留都有验收记录"],
  },
  audio: {
    icon: "audio-waveform",
    title: "一段中文音频或视频",
    input: "在线模型先转写，再按句生成可编辑的 Excel 审校表。",
    route: ["音频转写与逐句切分", "术语约束翻译 + 人工审核", "在线 TTS / 本机语音回退"],
    outputTitle: "英文配音、文本与二维码",
    output: ["每句机器译文都能单独修改", "在线接口支持时优先生成模型语音", "同时导出 WAV、朗读文本和本机播放二维码"],
  },
};

const reviewSamples = {
  museum: {
    clear:
      "After the Beginning of Autumn, the mountain air turns cool. The children collect sweet osmanthus blossoms in paper bags and bring them back to class to explore where their fragrance comes from.",
    natural:
      "Once autumn begins, a coolness settles over the mountains. The children gather sweet osmanthus in paper bags and take it to class to discover what gives the flowers their scent.",
    imagery:
      "After Lìqiū, the first breath of cool air moves through the mountains. The children tuck sweet osmanthus blossoms into paper bags and carry their fragrance back to the classroom for a closer look.",
  },
  children: {
    clear:
      "After the first day of autumn, the mountain breeze feels cooler. The children put sweet-smelling osmanthus flowers into paper bags and take them to class to find out where the scent comes from.",
    natural:
      "Autumn has just begun, and the mountain wind feels cool. The children gather tiny osmanthus flowers, carry them to class in paper bags, and investigate their lovely smell.",
    imagery:
      "When autumn tiptoes into the mountains, the breeze turns cool. The children catch the scent of osmanthus in paper bags and bring it to class to uncover its secret.",
  },
  voice: {
    clear:
      "After the start of autumn, cool air reaches the mountains. Children collect sweet osmanthus blossoms, take them to class, and study where the fragrance begins.",
    natural:
      "Autumn arrives. The mountain air turns cool. Children gather osmanthus blossoms and bring their fragrance back to the classroom to explore.",
    imagery:
      "With autumn's first cool breath, the mountains change. Children carry paper bags of osmanthus into class, following the flowers' fragrance to its source.",
  },
};

const reviewNotes = {
  clear: "取舍：补出节气含义，文化门槛更低；句子相对说明性。",
  natural: "取舍：英语衔接自然；“立秋”的文化名称不单独保留。",
  imagery: "取舍：保留 Lìqiū 与画面感；需要读者从上下文理解节气。",
};

const reviewStorageKey = "yishu-review-history-v1";
const reviewState = { scene: "museum", priority: "clarity", selected: "clear", confirmed: false };

const getReviewHistory = () => {
  try {
    return JSON.parse(localStorage.getItem(reviewStorageKey) || "[]");
  } catch {
    return [];
  }
};

const saveReviewHistory = (history) => {
  try {
    localStorage.setItem(reviewStorageKey, JSON.stringify(history.slice(0, 6)));
  } catch {
    // The workbench still functions when private browsing blocks local storage.
  }
};

const renderHistory = () => {
  const list = document.querySelector("[data-history-list]");
  if (!list) return;
  const history = getReviewHistory();
  if (!history.length) {
    list.innerHTML = '<li class="empty-history">还没有确认记录。完成一次选择后会显示在这里。</li>';
    return;
  }
  list.innerHTML = history
    .map(
      (item) => `<li><strong>${item.label}</strong><span>${item.scene} · ${item.time}</span><p>${item.translation}</p></li>`,
    )
    .join("");
};

const candidateOrderForPriority = (priority) => {
  if (priority === "imagery") return ["imagery", "natural", "clear"];
  if (priority === "rhythm") return ["natural", "imagery", "clear"];
  return ["clear", "natural", "imagery"];
};

const renderReviewCandidates = ({ announce = false } = {}) => {
  const samples = reviewSamples[reviewState.scene] || reviewSamples.museum;
  const grid = document.querySelector(".candidate-grid");
  const cards = candidateOrderForPriority(reviewState.priority)
    .map((key) => document.querySelector(`[data-candidate="${key}"]`))
    .filter(Boolean);
  cards.forEach((card) => grid?.appendChild(card));
  Object.entries(samples).forEach(([key, copy]) => {
    const copyNode = document.querySelector(`[data-candidate-copy="${key}"]`);
    const noteNode = document.querySelector(`[data-candidate-note="${key}"]`);
    if (copyNode) copyNode.textContent = copy;
    if (noteNode) noteNode.textContent = reviewNotes[key];
  });
  const active = samples[reviewState.selected] ? reviewState.selected : cards[0]?.dataset.candidate || "clear";
  reviewState.selected = active;
  document.querySelectorAll("[data-candidate]").forEach((card) => {
    const selected = card.dataset.candidate === active;
    card.classList.toggle("is-selected", selected);
    const radio = card.querySelector('input[type="radio"]');
    if (radio) radio.checked = selected;
  });
  const editor = document.querySelector("[data-final-translation]");
  if (editor) editor.value = samples[active];
  reviewState.confirmed = false;
  const download = document.querySelector("[data-download-result]");
  if (download) download.disabled = true;
  const feedback = document.querySelector("[data-feedback-form]");
  if (feedback) feedback.hidden = true;
  const status = document.querySelector("[data-review-status]");
  if (announce && status) status.textContent = "三种方向已更新，请比较取舍后确认。";
};

const downloadReviewReceipt = () => {
  const source = document.querySelector("[data-source-input]")?.value.trim() || "";
  const translation = document.querySelector("[data-final-translation]")?.value.trim() || "";
  const receipt = {
    product: "YISHU browser review sample",
    sampleOnly: true,
    savedAt: new Date().toISOString(),
    source,
    scene: reviewState.scene,
    priority: reviewState.priority,
    selectedDirection: reviewState.selected,
    translation,
    note: reviewNotes[reviewState.selected],
  };
  const blob = new Blob([JSON.stringify(receipt, null, 2)], { type: "application/json;charset=utf-8" });
  const href = URL.createObjectURL(blob);
  const download = document.createElement("a");
  download.href = href;
  download.download = `yishu-review-${new Date().toISOString().slice(0, 10)}.json`;
  download.click();
  URL.revokeObjectURL(href);
};

const header = document.querySelector("[data-header]");
const video = document.querySelector("[data-demo-video]");
const videoCover = document.querySelector(".video-cover");
const galleryFrame = document.querySelector(".product-frame");
const galleryImage = document.querySelector("[data-gallery-image]");
const galleryKicker = document.querySelector("[data-gallery-kicker]");
const galleryTitle = document.querySelector("[data-gallery-title]");
const galleryDescription = document.querySelector("[data-gallery-description]");

document.querySelector("[data-brief-form]")?.addEventListener("submit", (event) => {
  event.preventDefault();
  reviewState.scene = document.querySelector("[data-scene-input]")?.value || "museum";
  reviewState.priority = document.querySelector("[data-priority-input]")?.value || "clarity";
  reviewState.selected = candidateOrderForPriority(reviewState.priority)[0];
  renderReviewCandidates({ announce: true });
});

document.querySelectorAll('[name="candidate"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    reviewState.selected = radio.value;
    document.querySelectorAll("[data-candidate]").forEach((card) => {
      card.classList.toggle("is-selected", card.dataset.candidate === reviewState.selected);
    });
    const editor = document.querySelector("[data-final-translation]");
    if (editor) editor.value = reviewSamples[reviewState.scene][reviewState.selected];
    reviewState.confirmed = false;
    const download = document.querySelector("[data-download-result]");
    if (download) download.disabled = true;
  });
});

document.querySelector("[data-confirm-candidate]")?.addEventListener("click", () => {
  const translation = document.querySelector("[data-final-translation]")?.value.trim();
  const status = document.querySelector("[data-review-status]");
  if (!translation) {
    if (status) status.textContent = "请保留或写入一版译文后再确认。";
    return;
  }
  const labels = { clear: "清楚版", natural: "自然版", imagery: "意象版" };
  const scenes = { museum: "文化展签", children: "儿童读物", voice: "英文配音" };
  const history = getReviewHistory();
  history.unshift({
    label: labels[reviewState.selected],
    scene: scenes[reviewState.scene],
    translation,
    time: new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date()),
  });
  saveReviewHistory(history);
  renderHistory();
  reviewState.confirmed = true;
  const download = document.querySelector("[data-download-result]");
  if (download) download.disabled = false;
  const feedback = document.querySelector("[data-feedback-form]");
  if (feedback) feedback.hidden = false;
  if (status) status.textContent = "已确认并保存在这台设备。现在可下载记录，或反馈下一轮方向。";
});

document.querySelector("[data-download-result]")?.addEventListener("click", downloadReviewReceipt);

document.querySelector("[data-feedback-form]")?.addEventListener("submit", (event) => {
  event.preventDefault();
  const choice = new FormData(event.currentTarget).get("feedback") || "clear";
  reviewState.priority = choice === "natural" ? "rhythm" : choice === "imagery" ? "imagery" : "clarity";
  reviewState.selected = candidateOrderForPriority(reviewState.priority)[0];
  renderReviewCandidates();
  const status = document.querySelector("[data-review-status]");
  if (status) status.textContent = `已根据“${choice === "natural" ? "更自然" : choice === "imagery" ? "更有画面" : "更清楚"}”重排候选。`;
});

document.querySelector("[data-reset-review]")?.addEventListener("click", () => {
  const source = document.querySelector("[data-source-input]");
  if (source) source.value = "立秋之后，山里的风有了凉意。孩子们把桂花收进纸袋，带回教室观察香气从哪里来。";
  reviewState.scene = "museum";
  reviewState.priority = "clarity";
  reviewState.selected = "clear";
  const scene = document.querySelector("[data-scene-input]");
  const priority = document.querySelector("[data-priority-input]");
  if (scene) scene.value = "museum";
  if (priority) priority.value = "clarity";
  renderReviewCandidates({ announce: true });
});

document.querySelector("[data-clear-history]")?.addEventListener("click", () => {
  saveReviewHistory([]);
  renderHistory();
});

const renderPlayground = (key) => {
  const item = playgroundItems[key];
  if (!item) return;
  const icon = document.querySelector("[data-playground-icon]");
  const title = document.querySelector("[data-playground-title]");
  const input = document.querySelector("[data-playground-input]");
  const route = document.querySelector("[data-playground-route]");
  const outputTitle = document.querySelector("[data-playground-output-title]");
  const output = document.querySelector("[data-playground-output]");
  if (icon) icon.setAttribute("data-lucide", item.icon);
  if (title) title.textContent = item.title;
  if (input) input.textContent = item.input;
  if (route) {
    route.innerHTML = item.route
      .map((step, index) => `${index ? '<i data-lucide="arrow-right" aria-hidden="true"></i>' : ""}<span>${step}</span>`)
      .join("");
  }
  if (outputTitle) outputTitle.textContent = item.outputTitle;
  if (output) output.innerHTML = item.output.map((line) => `<li>${line}</li>`).join("");
};

const syncHeader = () => {
  header?.classList.toggle("is-scrolled", window.scrollY > 24);
};

window.addEventListener("scroll", syncHeader, { passive: true });
syncHeader();

document.querySelectorAll("[data-play-demo]").forEach((button) => {
  button.addEventListener("click", async () => {
    document.querySelector("#demo")?.scrollIntoView({ behavior: "smooth", block: "center" });
    videoCover?.classList.add("is-hidden");
    try {
      await video?.play();
    } catch {
      video?.setAttribute("controls", "");
    }
  });
});

video?.addEventListener("play", () => videoCover?.classList.add("is-hidden"));

document.querySelectorAll("[data-playground]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-playground]").forEach((tab) => {
      const active = tab === button;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    renderPlayground(button.dataset.playground);
  });
});

document.querySelectorAll("[data-gallery]").forEach((button) => {
  button.addEventListener("click", () => {
    const key = button.dataset.gallery;
    const item = galleryItems[key];
    if (!item || !galleryFrame || !galleryImage) return;

    document.querySelectorAll("[data-gallery]").forEach((tab) => {
      const active = tab === button;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });

    galleryFrame.classList.add("is-changing");
    window.setTimeout(() => {
      galleryImage.src = item.image;
      galleryImage.alt = item.alt;
      galleryKicker.textContent = item.kicker;
      galleryTitle.textContent = item.title;
      galleryDescription.textContent = item.description;
      galleryFrame.classList.remove("is-changing");
    }, 160);
  });
});

renderReviewCandidates();
renderHistory();

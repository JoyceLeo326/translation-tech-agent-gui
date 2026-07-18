const galleryItems = {
  overview: {
    image: "./assets/workbench-overview.png",
    alt: "译述开始页面",
    kicker: "开始",
    title: "把素材交给译述，系统自动进入对应流程",
    description: "图片、Word、音频或视频都可以直接选择，完整示例与真实成果在首页即可打开。",
  },
  production: {
    image: "./assets/workbench-production.png",
    alt: "译述文件翻译页面",
    kicker: "文件翻译",
    title: "图片、Word 与音视频共享同一套审校逻辑",
    description: "真实测试文件、审校表与回填按钮已经接入，不需要使用者手动寻找项目目录。",
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
    title: "连接自己的 API，让离线演示切换为真实在线处理",
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

const header = document.querySelector("[data-header]");
const video = document.querySelector("[data-demo-video]");
const videoCover = document.querySelector(".video-cover");
const galleryFrame = document.querySelector(".product-frame");
const galleryImage = document.querySelector("[data-gallery-image]");
const galleryKicker = document.querySelector("[data-gallery-kicker]");
const galleryTitle = document.querySelector("[data-gallery-title]");
const galleryDescription = document.querySelector("[data-gallery-description]");

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
  window.lucide?.createIcons({ "stroke-width": 1.8 });
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

if (window.lucide) {
  window.lucide.createIcons({ "stroke-width": 1.8 });
}

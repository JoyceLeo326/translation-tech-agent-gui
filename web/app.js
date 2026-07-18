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
    alt: "译述扣子多模型精译页面",
    kicker: "多模型精译",
    title: "看得懂扣子工作流具体做了什么",
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
};

const header = document.querySelector("[data-header]");
const video = document.querySelector("[data-demo-video]");
const videoCover = document.querySelector(".video-cover");
const galleryFrame = document.querySelector(".product-frame");
const galleryImage = document.querySelector("[data-gallery-image]");
const galleryKicker = document.querySelector("[data-gallery-kicker]");
const galleryTitle = document.querySelector("[data-gallery-title]");
const galleryDescription = document.querySelector("[data-gallery-description]");

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

const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const baseUrl = process.argv[2] || "http://127.0.0.1:4173";
const outputDir = process.argv[3] || path.join(process.cwd(), ".web-verify");
fs.mkdirSync(outputDir, { recursive: true });

async function verifyViewport(browser, name, viewport) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const consoleErrors = [];
  const requestFailures = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    requestFailures.push(`${request.method()} ${request.url()} :: ${request.failure()?.errorText}`);
  });

  const response = await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 45_000 });
  if (!response?.ok()) throw new Error(`${name}: page returned ${response?.status()}`);

  await page.locator("h1").waitFor({ state: "visible" });
  await page.waitForFunction(
    () => [...document.images]
      .filter((image) => image.getAttribute("src"))
      .every((image) => image.complete && image.naturalWidth > 0),
    { timeout: 45_000 },
  );
  await page.locator("[data-gallery='agent']").click();
  await page.waitForFunction(
    () => {
      const image = document.querySelector("[data-gallery-image]");
      return image?.getAttribute("src")?.includes("workbench-agent.png")
        && image.complete
        && image.naturalWidth > 0;
    },
    { timeout: 45_000 },
  );
  const gallerySrc = await page.locator("[data-gallery-image]").getAttribute("src");
  if (!gallerySrc?.includes("workbench-agent.png")) {
    throw new Error(`${name}: gallery did not switch to the agent screen`);
  }
  await page.locator("[data-playground='audio']").click();
  const playgroundTitle = await page.locator("[data-playground-output-title]").textContent();
  if (!playgroundTitle?.includes("英文配音")) throw new Error(`${name}: playground did not switch to audio`);
  await page.locator("[data-gallery='settings']").click();
  await page.waitForFunction(
    () => {
      const image = document.querySelector("[data-gallery-image]");
      return image?.getAttribute("src")?.includes("workbench-settings.png")
        && image.complete
        && image.naturalWidth > 0;
    },
    { timeout: 45_000 },
  );
  const settingsSrc = await page.locator("[data-gallery-image]").getAttribute("src");
  if (!settingsSrc?.includes("workbench-settings.png")) throw new Error(`${name}: settings screen missing`);

  const dimensions = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    h1: document.querySelector("h1")?.textContent?.replace(/\s+/g, " ").trim(),
    images: [...document.images].map((image) => ({
      src: image.currentSrc,
      declaredSrc: image.getAttribute("src"),
      complete: image.complete,
      width: image.naturalWidth,
      className: image.className,
    })),
    iconCount: document.querySelectorAll("svg.lucide").length,
    videoSource: document.querySelector("video source")?.src,
    downloadHref: document.querySelector(".header-download")?.href,
  }));

  const brokenImages = dimensions.images.filter(
    (image) => image.declaredSrc && (!image.complete || image.width === 0),
  );
  if (dimensions.scrollWidth > dimensions.innerWidth + 1) {
    throw new Error(`${name}: horizontal overflow ${dimensions.scrollWidth} > ${dimensions.innerWidth}`);
  }
  if (brokenImages.length) {
    throw new Error(`${name}: image load failure ${JSON.stringify(brokenImages)}`);
  }
  const productImages = dimensions.images.filter((image) => image.src.includes("workbench-"));
  if (productImages.some((image) => image.width < 2000)) throw new Error(`${name}: product screenshot is not high resolution`);
  if (dimensions.iconCount < 20) throw new Error(`${name}: Lucide icons did not render`);
  if (!dimensions.videoSource?.includes("Yishu-v1.4.0-demo.mp4")) throw new Error(`${name}: video source missing`);
  if (!dimensions.downloadHref?.includes("Yishu-v1.4.0-windows-x64.zip")) throw new Error(`${name}: download link missing`);

  await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage: true });
  await page.locator(".video-cover").click();
  await page.waitForFunction(
    () => {
      const demo = document.querySelector("video");
      return demo && !demo.paused && demo.readyState >= 2;
    },
    { timeout: 30_000 },
  );
  await page.waitForTimeout(1200);
  const videoState = await page.locator("video").evaluate((demo) => ({
    currentTime: demo.currentTime,
    duration: demo.duration,
    paused: demo.paused,
    readyState: demo.readyState,
  }));
  if (videoState.currentTime < 0.2 || videoState.duration < 140) {
    throw new Error(`${name}: demo video did not play correctly`);
  }
  await context.close();
  return {
    name,
    viewport,
    h1: dimensions.h1,
    iconCount: dimensions.iconCount,
    imageCount: dimensions.images.length,
    videoState,
    consoleErrors,
    requestFailures,
  };
}

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROME || undefined,
  });
  try {
    const results = [];
    results.push(await verifyViewport(browser, "desktop", { width: 1440, height: 1000 }));
    results.push(await verifyViewport(browser, "mobile", { width: 390, height: 844 }));
    console.log(JSON.stringify({ baseUrl, results }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});

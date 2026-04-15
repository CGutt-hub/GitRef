/* GitRef browser extension — popup logic.
   Talks to the local gitref serve endpoint (127.0.0.1:7342). */

const GITREF_PORT = 7342;
const SAVE_URL = `http://127.0.0.1:${GITREF_PORT}/save`;

const btn = document.getElementById("save");
const status = document.getElementById("status");
const info = document.getElementById("info");

function show(msg, cls) {
  status.textContent = msg;
  status.className = cls || "";
}

// Extract DOI / arXiv / ISBN from page via content script injection
async function extractFromPage(tab) {
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => {
      const url = location.href;
      const title = document.title;

      // DOI from meta tags
      let doi = "";
      const doiSels = [
        'meta[name="citation_doi"]',
        'meta[name="dc.identifier"]',
        'meta[name="DC.identifier"]',
        'meta[name="DC.Identifier"]',
        'meta[property="citation_doi"]',
        'meta[name="prism.doi"]',
      ];
      for (const sel of doiSels) {
        const el = document.querySelector(sel);
        if (el) {
          const v = el.getAttribute("content") || "";
          if (v.match(/^10\./)) { doi = v; break; }
        }
      }

      // DOI from URL patterns
      if (!doi) {
        const m = url.match(/doi\.org\/(10\.[^?#\s]+)/);
        if (m) doi = decodeURIComponent(m[1]);
      }

      // arXiv from URL
      let arxiv = "";
      const axm = url.match(/arxiv\.org\/(?:abs|pdf)\/([\d.]+(?:v\d+)?)/);
      if (axm) arxiv = axm[1];

      // arXiv from meta
      if (!arxiv) {
        const el = document.querySelector('meta[name="citation_arxiv_id"]');
        if (el) arxiv = el.getAttribute("content") || "";
      }

      // PDF URL from meta
      let pdfUrl = "";
      const pdfEl = document.querySelector('meta[name="citation_pdf_url"]');
      if (pdfEl) pdfUrl = pdfEl.getAttribute("content") || "";

      // Detect page type (like Zotero)
      let pageType = "webpage";
      if (doi || document.querySelector('meta[name="citation_title"]')) {
        pageType = "paper";
      } else if (arxiv) {
        pageType = "preprint";
      }

      return { url, title, doi, arxiv, pdfUrl, pageType };
    },
  });

  return results[0]?.result || { url: tab.url, title: tab.title };
}

async function savePaper() {
  btn.disabled = true;
  show("Connecting…");

  let tab;
  try {
    const [t] = await chrome.tabs.query({ active: true, currentWindow: true });
    tab = t;
  } catch {
    show("Cannot access current tab.", "err");
    btn.disabled = false;
    return;
  }

  let pageData;
  try {
    pageData = await extractFromPage(tab);
  } catch {
    // Fallback if content script injection fails (e.g. chrome:// pages)
    pageData = { url: tab.url, title: tab.title };
  }

  // Build the identifier URL for the server
  let sendUrl = pageData.url;
  if (pageData.doi) {
    sendUrl = `https://doi.org/${pageData.doi}`;
  } else if (pageData.arxiv) {
    sendUrl = `https://arxiv.org/abs/${pageData.arxiv}`;
  }

  show("Saving…");

  try {
    const resp = await fetch(SAVE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: sendUrl, title: pageData.title }),
    });

    if (!resp.ok) {
      show(`Server error (${resp.status})`, "err");
      btn.disabled = false;
      return;
    }

    const data = await resp.json();
    show(`Saved: ${data.key}`, "ok");
    info.textContent = data.title || "";
    if (data.file) {
      info.textContent += ` [${data.file}]`;
    }
  } catch (e) {
    if (e instanceof TypeError) {
      show("Cannot reach gitref serve", "err");
      info.textContent = "Start the server: gitref serve";
    } else {
      show("Failed: " + e.message, "err");
    }
    btn.disabled = false;
  }
}

// Auto-detect on popup open: show page info
(async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const data = await extractFromPage(tab);

    if (data.doi) {
      info.textContent = `DOI: ${data.doi}`;
    } else if (data.arxiv) {
      info.textContent = `arXiv: ${data.arxiv}`;
    } else if (data.pageType === "paper") {
      info.textContent = "Paper detected";
    } else {
      info.textContent = data.url?.substring(0, 60) || "";
    }
  } catch {
    // ignore - just no preview
  }
})();

btn.addEventListener("click", savePaper);

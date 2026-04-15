// GitRef Bookmarklet — saves the current page to your local GitRef server.
// To install: create a bookmark and paste the minified version as the URL.
//
// How it works:
//   1. Grabs the page URL and title
//   2. Looks for DOI meta tags or arXiv IDs in the URL
//   3. POSTs the info to the local GitRef server (http://127.0.0.1:7342/save)
//   4. Shows a brief notification with the result

(function () {
  var GITREF_PORT = 7342;
  var url = window.location.href;
  var title = document.title;

  // Try to find a DOI from common meta tags
  var doiMeta =
    document.querySelector('meta[name="citation_doi"]') ||
    document.querySelector('meta[name="dc.identifier"]') ||
    document.querySelector('meta[name="DC.identifier"]');
  if (doiMeta) {
    var doiVal = doiMeta.getAttribute("content");
    if (doiVal && doiVal.match(/^10\./)) {
      url = "https://doi.org/" + doiVal;
    }
  }

  var payload = JSON.stringify({ url: url, title: title });

  // Show a small notification
  function notify(msg, ok) {
    var el = document.createElement("div");
    el.textContent = msg;
    el.style.cssText =
      "position:fixed;top:10px;right:10px;z-index:999999;" +
      "padding:12px 20px;border-radius:8px;font:14px/1.4 sans-serif;" +
      "color:#fff;background:" +
      (ok ? "#2ea043" : "#d73a49") +
      ";box-shadow:0 2px 8px rgba(0,0,0,.3);transition:opacity .3s";
    document.body.appendChild(el);
    setTimeout(function () {
      el.style.opacity = "0";
      setTimeout(function () {
        el.remove();
      }, 400);
    }, 3000);
  }

  fetch("http://127.0.0.1:" + GITREF_PORT + "/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload,
  })
    .then(function (r) {
      return r.json();
    })
    .then(function (d) {
      notify("GitRef: saved — " + (d.title || "done"), true);
    })
    .catch(function (e) {
      notify("GitRef: failed — is 'gitref serve' running?", false);
    });
})();

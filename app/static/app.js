const runButton = document.getElementById("run-button");
const clearButton = document.getElementById("clear-button");
const refreshHistoryButton = document.getElementById("refresh-history");
const refreshDomainsButton = document.getElementById("refresh-domains");
const titleInput = document.getElementById("title");
const sourceUrlInput = document.getElementById("source-url");
const articleTextInput = document.getElementById("article-text");
const resultsRoot = document.getElementById("results");
const summaryPanel = document.getElementById("summary-panel");
const articleIdEl = document.getElementById("article-id");
const elapsedMsEl = document.getElementById("elapsed-ms");
const claimCountEl = document.getElementById("claim-count");
const articleDomainEl = document.getElementById("article-domain");
const overallVerdictEl = document.getElementById("overall-verdict");
const verdictCountsEl = document.getElementById("verdict-counts");
const reportSummaryEl = document.getElementById("report-summary");
const historyListEl = document.getElementById("history-list");
const exportLinkEl = document.getElementById("export-link");
const domainGridEl = document.getElementById("domain-grid");
const statArticlesEl = document.getElementById("stat-articles");
const statClaimsEl = document.getElementById("stat-claims");
const statSourcesEl = document.getElementById("stat-sources");

const samples = {
  energy: {
    title: "Renewable Energy Update",
    sourceUrl: "https://example.com/renewable-energy-update",
    articleText:
      "Solar power accounted for the majority of new electricity generation capacity added globally in recent years. Researchers also note that battery storage costs have declined over time, making grid-scale storage more practical. Some reports claim solar is now the cheapest source of electricity in history in many regions.",
  },
  health: {
    title: "Public Health Brief",
    sourceUrl: "https://example.com/public-health-brief",
    articleText:
      "According to public health researchers, childhood vaccination coverage remained high in many regions, but some communities saw lower uptake after the pandemic. Hospitalizations from respiratory illness also declined compared with earlier peaks.",
  },
  labor: {
    title: "Labor Market Snapshot",
    sourceUrl: "https://example.com/labor-market-snapshot",
    articleText:
      "Payroll growth slowed in the latest month, although unemployment remained low and wages continued rising across several sectors. Analysts also reported that labor force participation improved for prime-age workers.",
  },
  tech: {
    title: "AI Infrastructure Note",
    sourceUrl: "https://example.com/ai-infrastructure-note",
    articleText:
      "Demand for AI compute pushed data center spending higher, while semiconductor firms reported stronger revenue tied to accelerator demand. Some analysts also said energy use from AI workloads could rise alongside new model deployments.",
  },
  climate: {
    title: "Climate Indicators Brief",
    sourceUrl: "https://example.com/climate-indicators-brief",
    articleText:
      "Global average temperatures remained near record highs, and greenhouse gas emissions from several sectors stayed elevated. Scientists also warned that sea level rise would continue even if annual emissions growth slowed.",
  },
};

document.querySelectorAll("[data-sample]").forEach((button) => {
  button.addEventListener("click", () => {
    const sample = samples[button.dataset.sample];
    titleInput.value = sample.title;
    sourceUrlInput.value = sample.sourceUrl;
    articleTextInput.value = sample.articleText;
  });
});

runButton.addEventListener("click", async () => {
  runButton.disabled = true;
  runButton.textContent = "Running...";
  resultsRoot.innerHTML = "";

  try {
    const response = await fetch("/verify", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: titleInput.value,
        source_url: sourceUrlInput.value || null,
        article_text: articleTextInput.value,
        persist: true,
      }),
    });

    const rawText = await response.text();
    let payload = null;
    try {
      payload = JSON.parse(rawText);
    } catch {
      payload = null;
    }

    if (!response.ok) {
      throw new Error(payload?.detail || rawText || "Verification failed.");
    }

    renderVerification(payload);
    await Promise.all([loadStats(), loadHistory(), loadDomains()]);
  } catch (error) {
    resultsRoot.innerHTML = `<article class="result-card"><p>${escapeHtml(error.message)}</p></article>`;
  } finally {
    runButton.disabled = false;
    runButton.textContent = "Run verification";
  }
});

clearButton.addEventListener("click", () => {
  resultsRoot.innerHTML = "";
  summaryPanel.classList.add("hidden");
  exportLinkEl.classList.add("hidden");
});

refreshHistoryButton.addEventListener("click", () => {
  loadHistory();
});

refreshDomainsButton.addEventListener("click", () => {
  loadDomains();
});

async function loadStats() {
  try {
    const response = await fetch("/stats");
    const stats = await response.json();
    statArticlesEl.textContent = stats.articles;
    statClaimsEl.textContent = stats.claims;
    statSourcesEl.textContent = stats.sources;
  } catch {
    statArticlesEl.textContent = "-";
    statClaimsEl.textContent = "-";
    statSourcesEl.textContent = "-";
  }
}

async function loadHistory() {
  historyListEl.innerHTML = '<p class="muted">Loading runs...</p>';
  try {
    const response = await fetch("/articles?limit=8");
    const articles = await response.json();
    if (!articles.length) {
      historyListEl.innerHTML = '<p class="muted">No saved runs yet.</p>';
      return;
    }

    historyListEl.innerHTML = articles
      .map(
        (article) => `
          <button class="history-item" data-article-id="${article.id}">
            <strong>${escapeHtml(article.title)}</strong>
            <span>${escapeHtml(article.article_domain)} · ${escapeHtml(article.overall_verdict)}</span>
            <span>${article.claim_count} claims</span>
          </button>
        `,
      )
      .join("");

    historyListEl.querySelectorAll("[data-article-id]").forEach((button) => {
      button.addEventListener("click", async () => {
        const articleId = button.dataset.articleId;
        await loadArticleDetail(articleId);
      });
    });
  } catch {
    historyListEl.innerHTML = '<p class="muted">Could not load recent runs.</p>';
  }
}

async function loadDomains() {
  domainGridEl.innerHTML = '<p class="muted">Loading domains...</p>';
  try {
    const response = await fetch("/domains");
    const domains = await response.json();
    domainGridEl.innerHTML = domains
      .map(
        (item) => `
          <article class="domain-card">
            <strong>${escapeHtml(item.domain)}</strong>
            <span>${item.source_count} sources</span>
            <span>${item.article_count} saved articles</span>
          </article>
        `,
      )
      .join("");
  } catch {
    domainGridEl.innerHTML = '<p class="muted">Could not load domain breakdown.</p>';
  }
}

async function loadArticleDetail(articleId) {
  try {
    const response = await fetch(`/articles/${articleId}`);
    const article = await response.json();
    const payload = {
      article_id: article.id,
      title: article.title,
      source_url: article.source_url,
      article_domain: article.article_domain,
      overall_verdict: article.overall_verdict,
      report_summary: article.report_summary,
      elapsed_ms: article.elapsed_ms,
      claims: article.claims.map((claim) => ({
        text: claim.claim_text,
        sentence_index: claim.sentence_index,
        claim_type: claim.claim_type,
        checkability_score: claim.checkability_score,
        domain: claim.domain,
        key_terms: claim.key_terms,
        hedged: claim.hedged,
      })),
      verdict_counts: buildCountsFromHistory(article.claims),
      results: article.claims.map((claim) => ({
        claim: claim.claim_text,
        claim_type: claim.claim_type,
        domain: claim.domain,
        score: claim.credibility_score,
        confidence: claim.confidence_score,
        verdict: claim.verdict,
        explanation: claim.explanation,
        reviewer_note: claim.reviewer_note,
        debug_signals: {},
        evidence: claim.evidence.map((evidence) => ({
          slug: evidence.source_slug,
          title: evidence.title,
          url: evidence.url,
          organization: evidence.organization,
          domain: evidence.domain,
          source_type: evidence.source_type,
          snippet: evidence.snippet,
          authority_score: evidence.authority_score,
          match_score: evidence.match_score,
          relevance_score: evidence.relevance_score,
          coverage_score: evidence.coverage_score,
          authority_component: evidence.authority_component,
          tag_hits: evidence.tag_hits,
          keyword_hits: evidence.keyword_hits,
          phrase_hits: evidence.phrase_hits,
          matched_numbers: evidence.matched_numbers,
          signal_summary: evidence.signal_summary,
          debug_factors: {},
        })),
      })),
    };
    renderVerification(payload);
  } catch {
    resultsRoot.innerHTML = '<article class="result-card"><p>Could not load the saved run.</p></article>';
  }
}

function renderVerification(payload) {
  summaryPanel.classList.remove("hidden");
  articleIdEl.textContent = payload.article_id || "not saved";
  elapsedMsEl.textContent = `${payload.elapsed_ms} ms`;
  claimCountEl.textContent = payload.claims.length;
  articleDomainEl.textContent = payload.article_domain;
  overallVerdictEl.textContent = payload.overall_verdict;
  verdictCountsEl.textContent = `${payload.verdict_counts.likely_supported} / ${payload.verdict_counts.mixed_support} / ${payload.verdict_counts.weak_support} / ${payload.verdict_counts.insufficient_evidence}`;
  reportSummaryEl.textContent = payload.report_summary;

  if (payload.article_id) {
    exportLinkEl.href = `/articles/${payload.article_id}/export`;
    exportLinkEl.classList.remove("hidden");
  } else {
    exportLinkEl.classList.add("hidden");
  }

  resultsRoot.innerHTML = payload.results
    .map(
      (result, index) => `
        <article class="result-card">
          <div class="meta-row">
            <span class="chip">Claim ${index + 1}</span>
            <span class="chip">${escapeHtml(result.claim_type)}</span>
            <span class="chip">${escapeHtml(result.domain)}</span>
            <span class="chip verdict-chip">${escapeHtml(result.verdict)}</span>
            <span class="chip">score ${result.score}</span>
            <span class="chip">confidence ${result.confidence}</span>
          </div>
          <h3>${escapeHtml(result.claim)}</h3>
          <p class="muted">${escapeHtml(result.explanation)}</p>
          <p class="reviewer-note">${escapeHtml(result.reviewer_note)}</p>
          <div class="evidence-list">
            ${result.evidence
              .map(
                (evidence) => `
                  <section class="evidence-card">
                    <div class="meta-row">
                      <span class="chip">${escapeHtml(evidence.organization || evidence.title)}</span>
                      <span class="chip">${escapeHtml(evidence.domain)}</span>
                      <span class="chip">${escapeHtml(evidence.source_type)}</span>
                      <span class="chip">authority ${evidence.authority_score}</span>
                      <span class="chip">match ${evidence.match_score}</span>
                      <span class="chip">coverage ${evidence.coverage_score}</span>
                    </div>
                    <h4><a href="${escapeHtml(evidence.url)}" target="_blank" rel="noreferrer">${escapeHtml(evidence.title)}</a></h4>
                    <p class="muted">${escapeHtml(evidence.snippet)}</p>
                    <p class="muted">${escapeHtml(evidence.signal_summary)}</p>
                    <div class="chip-row">
                      ${renderChips("tag", evidence.tag_hits)}
                      ${renderChips("keyword", evidence.keyword_hits)}
                      ${renderChips("phrase", evidence.phrase_hits)}
                      ${renderChips("number", evidence.matched_numbers)}
                    </div>
                  </section>
                `,
              )
              .join("")}
          </div>
        </article>
      `,
    )
    .join("");
}

function renderChips(label, values) {
  return values.map((value) => `<span class="chip">${escapeHtml(label)}: ${escapeHtml(value)}</span>`).join("");
}

function buildCountsFromHistory(claims) {
  const counts = {
    likely_supported: 0,
    mixed_support: 0,
    weak_support: 0,
    insufficient_evidence: 0,
  };
  claims.forEach((claim) => {
    if (claim.verdict === "likely supported") counts.likely_supported += 1;
    if (claim.verdict === "mixed support") counts.mixed_support += 1;
    if (claim.verdict === "weak support") counts.weak_support += 1;
    if (claim.verdict === "insufficient evidence") counts.insufficient_evidence += 1;
  });
  return counts;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

loadStats();
loadHistory();
loadDomains();

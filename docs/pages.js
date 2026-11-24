// Static pages: terms, privacy, sources, about. Plain language. All brand, domain and contact values come from site.json (passed in as `site`).
// Every page is a DRAFT until the owner approves it (launch checklist item 11); the banner text is site.legal_status.
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const mail = (site, role) => { if (!site.email_enabled) return `<a href="https://github.com/${esc(site.repo)}/issues/new">a GitHub issue</a>`; const a = `${site.contacts[role]}@${site.domain}`; return `<a href="mailto:${esc(a)}">${esc(a)}</a>`; };
  const draft = site => `<p class="callout draft-banner"><strong>${esc(site.legal_status)}.</strong> This page is a plain-language draft and has not been approved yet. Do not rely on it as final terms.</p>`;
  const head = (site, title, lead) => `<div class="page-head"><h1>${esc(title)}</h1><p class="intro">${lead}</p></div>${draft(site)}`;
  const date = 'Last updated 2026-11-24.';

  const terms = site => `${head(site, 'Terms of use', `Short version: the data is open for what we hold rights in, it is only as good as its sources, and you check before you buy. ${date}`)}
<div class="prose">
<h2>The data is provided as is</h2>
<p>${esc(site.brand)} collects product specifications from the sources named next to each value. We try to be accurate, but values can be wrong, out of date or specific to a region or revision. The service and the data come with no warranty of any kind, express or implied, including accuracy, completeness, fitness for a purpose or availability.</p>
<h2>Not purchase advice</h2>
<p>Nothing here is a recommendation or independent testing. “Accepted into catalogue” means a recorded review decision about what a cited source says. Check the manufacturer’s page and the label on the product before you buy, especially for safety ratings, plugs and voltages.</p>
<h2>Limit of liability</h2>
<p>To the extent the law allows, we are not liable for any loss arising from using the site or the data, and our total liability for any claim is limited to zero dollars, since the service is free. Some places do not allow these limits, so they apply only as far as your local law permits.</p>
<h2>Licence and attribution</h2>
<p>The database is available under the Open Database License 1.0 for what we hold rights in: the compilation (its selection, structure and identity work) and values from sources we have permission evidence for. Other values are shown as facts with a link to their source, and we grant no licence over them. Check that source’s terms before you reuse them. Site text is CC BY 4.0 and the code is Apache-2.0. If you publish something made from the data, include: “Data: ${esc(site.brand)} (ODbL), sources linked per value”. Details: <a href="#/sources">Sources</a> and <a href="https://github.com/${esc(site.repo)}/blob/master/DATA-LICENSE.md">DATA-LICENSE.md</a>.</p>
<h2>Acceptable use</h2>
<ul><li>Do not attack, overload or probe the service, or try to get around its limits.</li>
<li>Honour rate limits and the rules in <code>robots.txt</code>. Use the static dataset files for bulk needs rather than scraping pages.</li>
<li>Do not use the data to mislead people or to claim an endorsement by a manufacturer.</li></ul>
<p>We may slow down or block clients that break these rules.</p>
<h2>Trademarks</h2>
<p>Product, brand and certification names belong to their owners and are used only to identify products. No affiliation or endorsement is implied.</p>
<h2>Paid tier</h2>
<p>A paid tier is coming later. Nothing on this site is for sale today.</p>
<h2>Changes and contact</h2>
<p>We may change these terms; the date above shows the latest version. Questions: ${mail(site, 'hello')}. Takedown requests: see <a href="#/sources">Sources</a>.</p>
</div>`;

  const privacy = site => `${head(site, 'Privacy', `Short version: no accounts, no cookies, no tracking of individuals. ${date}`)}
<div class="prose">
<h2>What we do not do</h2>
<ul><li>No accounts, no sign-up and no cookies set by this site.</li>
<li>No advertising and no sale or sharing of personal data.</li></ul>
<h2>What we measure</h2>
<ul><li><strong>Page views:</strong> cookieless analytics counts visits and pages without identifying you. It does not use cookies or follow you across sites.</li>
<li><strong>IP addresses:</strong> used briefly by the hosting layer to apply rate limits and block abuse, and not stored by us.</li>
<li><strong>Searches that find nothing:</strong> when a search returns no result, the search text may be sent, shortened, as an anonymous count so we can see what products to add. It is never stored with an IP address. Do not type personal information into the search box.</li></ul>
<h2>Your browser</h2>
<p>Your theme choice and the like are kept in your own browser storage and never sent to us.</p>
<h2>GitHub and email</h2>
<p>Corrections and product requests on GitHub are public and governed by GitHub’s own privacy terms; include product information only. If you email ${mail(site, 'corrections')}, ${mail(site, 'legal')} or ${mail(site, 'hello')}, we keep the message only as long as needed to answer it.</p>
<h2>Contact</h2>
<p>${mail(site, 'hello')}</p>
</div>`;

  const sources = (site, data) => {
    const granted = data?.granted || [], facts = data?.facts_only || [], cov = data?.coverage?.categories || null;
    const num = n => Number(n || 0).toLocaleString('en-US');
    const grantItems = rows => rows.length ? `<ul class="credit-list">${rows.map(item => `<li>${esc(item.credit || item.domain)} <small class="muted code">${esc(item.domain)}</small>${item.attribution ? `<br><small>Required attribution: “${esc(item.attribution)}”</small>` : ''}</li>`).join('')}</ul>` : '<p class="muted">None listed.</p>';
    const factItems = rows => rows.length ? `<ul class="credit-list">${rows.map(item => `<li>${esc(item.credit || item.domain)} <small class="muted code">${esc(item.domain)}</small></li>`).join('')}</ul>` : '<p class="muted">None listed.</p>';
    const covTable = cov ? `<div class="table-scroll" role="region" aria-label="Coverage" tabindex="0"><table class="spec-table"><thead><tr><th scope="col">Category</th><th scope="col">Values shown</th><th scope="col">Values under our licence</th></tr></thead><tbody>${Object.keys(cov).sort().map(id => `<tr><th scope="row">${esc(id)}</th><td>${num(cov[id].free?.values)}</td><td>${num(cov[id].granted?.values)}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">Coverage figures could not be loaded.</p>';
    return `${head(site, 'Sources and credit', `Every value links to the page or file that states it. This page credits the sources and explains reuse and takedowns. ${date}`)}
<div class="prose">
<p><strong>How to cite.</strong> Data: ${esc(site.brand)} (ODbL), sources linked per value.</p>
<p><strong>What our licence covers.</strong> The ODbL covers the compilation and the values from the sources listed under “Licensed with permission”. Everything else is shown as a fact with a link, and we grant no licence over it. Each value’s detail view marks which case applies.</p>
<h2>Licensed with permission</h2>
${data ? grantItems(granted) : '<p class="muted">The source list could not be loaded.</p>'}
<h2>Shown as facts with links, not licensed by us</h2>
<p>We republish specification values and links, not text, images or documents. Rights in each source’s content and marks stay with their owners. “ENERGY STAR” and other certification marks belong to their owners and appear only as factual attributes.</p>
${data ? factItems(facts) : ''}
<h2>Coverage</h2>
${covTable}
<h2>Takedowns</h2>
<p>If you own a source and want a field or a whole source removed, email ${mail(site, 'legal')} with the page or value concerned. We acknowledge within 3 business days and remove it from the site and API within 7 days of a valid request, and from the next release. Factual corrections go to ${mail(site, 'corrections')} or a <a href="https://github.com/${esc(site.repo)}/issues/new?title=Correction%3A%20">GitHub issue</a>.</p>
</div>`;
  };

  const about = site => `<div class="page-head"><h1>About ${esc(site.brand)}</h1><p class="intro">A cross-brand reference of product specifications where every value shows where it came from.</p></div>${draft(site)}
<div class="prose">
<h2>What it is</h2>
<p>${esc(site.brand)} records exact products (by manufacturer model or part number, not a shop listing title) and the specifications their makers and certifiers publish, with a link per value. “Unknown” means no value is recorded, never “No”.</p>
<h2>What it is not</h2>
<p>It is not independent testing and not shopping advice. See the <a href="#/terms">Terms</a>.</p>
<h2>Free and open</h2>
<p>The database is open under the ODbL for what we hold rights in (see <a href="#/sources">Sources</a>), with downloads under <a href="api/v1/categories.json">Static dataset</a> and a machine-readable summary in <a href="llms.txt">llms.txt</a>. An API and MCP access are in preview. A paid tier is coming later.</p>
<h2>Get in touch</h2>
<p>Corrections: ${mail(site, 'corrections')}. General: ${mail(site, 'hello')}. Takedowns: ${mail(site, 'legal')}. Code and issues: <a href="https://github.com/${esc(site.repo)}">GitHub</a>.</p>
</div>`;

  window.SpecsheetPages = {terms, privacy, sources, about};
})();

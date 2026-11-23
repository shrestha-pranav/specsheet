(() => {
  'use strict';

  const main = document.getElementById('main');
  document.querySelector('.skip-link')?.addEventListener('click', event => {
    event.preventDefault();
    main.focus();
    main.scrollIntoView();
  });
  const themeSelect = document.getElementById('theme');
  const categoryCache = new Map();
  const indexCache = new Map();
  const detailCache = new Map();
  let redirectsPromise;
  let categoriesPromise;
  let routeSequence = 0;

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const encoded = (value) => encodeURIComponent(value);
  const safeUrl = (value) => { try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.href : null; } catch { return null; } };
  const categoryUrl = (id, query = '') => `#/category/${encoded(id)}${query}`;
  const returnParam = (query) => query ? `&return=${encoded(query)}` : '';
  const productUrl = (category, id, query = '', ids = []) => { const parts = [query ? `return=${encoded(query)}` : '', ids.length ? `ids=${encoded(ids.join(','))}` : ''].filter(Boolean); return `#/product/${encoded(category)}/${encoded(id)}${parts.length ? `?${parts.join('&')}` : ''}`; };
  const compareUrl = (category, ids, differences = false, query = '', options = {}) => `#/compare/${encoded(category)}?ids=${encoded(ids.join(','))}${differences ? '&diff=1' : ''}${options.detail ? '&detail=1' : ''}${options.model ? `&model=${encoded(options.model)}` : ''}${returnParam(query)}`;
  const BUILD = document.querySelector('meta[name="specsheet-build"]')?.content || '';
  const getJson = async (url) => { const response = await fetch(BUILD ? `${url}${url.includes('?') ? '&' : '?'}v=${BUILD}` : url); if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); };
  const issueBase = 'https://github.com/shrestha-pranav/specsheet/issues/new';
  const normalizeQuery = query => query.trim().replace(/\s+/g, ' ').toLocaleLowerCase();
  const validGtin = digits => { let sum = 0; [...digits].reverse().forEach((digit, index) => { sum += Number(digit) * (index % 2 ? 3 : 1); }); return sum % 10 === 0; };
  const identifierGuess = query => {
    const value = query.trim().toUpperCase().replace(/[\s.-]/g, '');
    if (/^[0-9]{2}[A-Z0-9]{2}[0-9A-Z]{4}[A-Z]{2}$/.test(value)) return {scheme:'mtm',value};
    if ([8,12,13,14].includes(value.length) && /^\d+$/.test(value) && validGtin(value)) return {scheme:'gtin',value:value.padStart(14,'0')};
    return null;
  };
  // Retail-title search: pull model-number-like tokens out of a pasted title, rank exact identifiers first, then same-model-code
  // neighbours, then all-words and partial word matches. A miss here says what was searched; it never proves absence.
  const STOP_WORDS = new Set(['the','a','an','and','with','for','of','in','laptop','laptops','notebook','computer','pc','monitor','ssd','router','new','inch','oled','lcd','led']);
  const compactId = value => String(value ?? '').toUpperCase().replace(/[\s.\-_/]/g, '');
  const UNIT_TOKEN = /^\d+(GB|TB|HZ|W|MM|IN|INCH|MBPS|GBPS|MB|MAH|WH|GHZ|MHZ|K)$/;
  const MTM_LIKE = /^\d{2}[A-Z0-9]{2}[0-9A-Z]{3,4}[A-Z]{2}$/;
  const extractIdentifiers = query => {
    const found = new Map();
    for (const word of String(query || '').toUpperCase().split(/[\s,;()\[\]"]+/).filter(Boolean)) {
      const value = compactId(word);
      if (!/^[A-Z0-9]+$/.test(value) || UNIT_TOKEN.test(value)) continue;
      if (value.length >= 5 && value.length <= 24 && /[A-Z]/.test(value) && /\d/.test(value)) found.set(value, {value, scheme: MTM_LIKE.test(value) ? 'mtm' : 'model'});
      else if ([8,12,13,14].includes(value.length) && /^\d+$/.test(value) && validGtin(value)) found.set(value.padStart(14, '0'), {value:value.padStart(14, '0'), scheme:'gtin'});
    }
    return [...found.values()];
  };
  const rowSearchCache = new WeakMap();
  const rowSearchEntry = row => {
    let entry = rowSearchCache.get(row);
    if (!entry) {
      const ids = (row.identifiers || []).map(id => compactId(id.value)).flatMap(value => /^\d{8,14}$/.test(value) ? [value, value.padStart(14, '0')] : [value]);
      const text = [row.brand, row.name, row.variant_label, row.family, ...(row.search || []), ...(row.identifiers || []).map(id => id.value)].join(' ').toLocaleLowerCase().replace(/[^a-z0-9]+/g, ' ');
      entry = {ids, text:` ${text} `};
      rowSearchCache.set(row, entry);
    }
    return entry;
  };
  const termHit = (text, term) => {
    if (term.length < 3) return text.includes(` ${term} `);
    if (text.includes(term)) return true;
    const loose = /^(\d{1,2})[a-z]$/.exec(term);
    return loose ? text.includes(` ${loose[1]} `) ? 'loose' : false : false;
  };
  const searchRows = (rows, query) => {
    const raw = String(query || '').trim();
    const info = {query:raw, identifiers:[], terms:[], matches:new Map()};
    if (!raw) return info;
    const identifiers = extractIdentifiers(raw);
    info.identifiers = identifiers.map(item => item.value);
    info.terms = [...new Set(normalizeQuery(raw).replace(/\b\d+-in-\d+\b/g, ' ').split(/[^a-z0-9]+/).filter(term => term.length > 1 && !STOP_WORDS.has(term)))];
    const need = Math.ceil(info.terms.length / 2);
    for (const row of rows) {
      const entry = rowSearchEntry(row);
      const exact = identifiers.filter(item => entry.ids.includes(item.value));
      if (exact.length) { info.matches.set(row.id, {rank:0, matched:exact.map(item => item.value), why:`Exact identifier ${exact.map(item => item.value).join(', ')}`}); continue; }
      const sameCode = identifiers.filter(item => item.scheme === 'mtm' && entry.ids.some(id => MTM_LIKE.test(id) && id.slice(0, 4) === item.value.slice(0, 4)));
      const hits = info.terms.map(term => [term, termHit(entry.text, term)]);
      const matched = hits.filter(([, hit]) => hit).map(([term]) => term), missed = hits.filter(([, hit]) => !hit).map(([term]) => term);
      const loose = hits.filter(([, hit]) => hit === 'loose').map(([term]) => term);
      if (sameCode.length) { info.matches.set(row.id, {rank:1, matched, why:`Same model code ${sameCode[0].value.slice(0, 4)}, but ${sameCode.map(item => item.value).join(', ')} is not recorded. Check the part number on the product label.`}); continue; }
      if (!info.terms.length || !matched.length) continue;
      const looseNote = loose.length ? ` (${loose.join(', ')} matched loosely, verify)` : '';
      if (!missed.length) info.matches.set(row.id, {rank:2, matched, why:`Every search word matches${looseNote}.`});
      else if (matched.length >= need) info.matches.set(row.id, {rank:3, matched, why:`Matched ${matched.join(', ')}; not matched ${missed.join(', ')}${looseNote}. Confirm the identifier before relying on this.`});
    }
    const best = Math.min(...[...info.matches.values()].map(match => match.rank), 9);
    for (const [id, match] of info.matches) if (best === 0 ? match.rank > 0 : (best <= 2 && match.rank === 3)) info.matches.delete(id);
    return info;
  };
  const missingIssueUrl = (categoryId, query) => {
    const payload = {category:categoryId, query, query_norm:normalizeQuery(query), identifier_guess:identifierGuess(query), build:BUILD};
    const params = new URLSearchParams({template:'missing-product.yml',payload:JSON.stringify(payload)});
    return `${issueBase}?${params}`;
  };
  const correctionIssueUrl = (entityId, key, shownValue) => {
    const payload = {entity_id:entityId,key,shown_value:shownValue,claimed_value:'',evidence_url:'',build:BUILD};
    return `${issueBase}?${new URLSearchParams({template:'field-correction.yml',payload:JSON.stringify(payload)})}`;
  };
  const categories = () => categoriesPromise ||= getJson('api/v1/categories.json').then(items => {
    const visible = items.filter(item => item.id !== 'power-strips-demo');
    visible.forEach(item => categoryCache.set(item.id, item));
    return visible;
  }).catch(error => { categoriesPromise = null; throw error; });
  const toRow = (row) => ({...row,
    family: row.family_id, model: row.ids?.[0]?.split(':').slice(1).join(':') || '',
    identifiers: (row.ids || []).map(id => ({scheme:id.split(':')[0], value:id.split(':').slice(1).join(':')})),
    specs: Object.fromEntries([...Object.entries(row.v || {}).map(([key,value]) => [key,{status:'known',value,...(row.x?.[key] || {})}]),
      ...Object.entries(row.s || {}).map(([key,status]) => [key,{status,value:null}])])});
  const loadShards = (paths) => Promise.all(paths.map(path => getJson(`api/v1/${path}`))).then(shards => shards.flat());
  // Trusted rows only, unless the reader opted in to the unreviewed preview index. Preview is strictly additive: every trusted row keeps
  // its accepted facts, preview claims attach as separate candidates, and preview-only identities are appended.
  const indexFor = (category, preview = false) => {
    const wantPreview = preview && !!category.preview?.index;
    const key = wantPreview ? `${category.id}:preview` : category.id;
    if (!indexCache.has(key)) indexCache.set(key, (async () => {
      if (!category.index) return getJson(`api/v1/${category.products}`);
      // Revision rows (opt-in per category) are children of their model, never separate products in counts or listings.
      const trusted = (await loadShards(category.index)).map(toRow).filter(row => row.kind !== 'revision');
      if (!wantPreview) return trusted;
      const merged = trusted.map(row => ({...row, unreviewed:false, candidates:{}, unreviewedKeys:new Set()}));
      const known = new Map(merged.map(row => [row.id, row]));
      for (const row of (await loadShards(category.preview.index)).map(toRow).filter(row => row.kind !== 'revision')) {
        const base = known.get(row.id);
        if (!base) { row.unreviewed = true; row.candidates = {}; row.unreviewedKeys = new Set(Object.keys(row.specs).filter(k => row.specs[k].status === 'known')); merged.push(row); continue; }
        for (const [key, spec] of Object.entries(row.specs)) {
          if (spec.status !== 'known') continue;
          const accepted = base.specs[key];
          if (!accepted || accepted.status !== 'known' || JSON.stringify([accepted.value, accepted.qualifier]) !== JSON.stringify([spec.value, spec.qualifier])) { base.candidates[key] = spec; base.unreviewedKeys.add(key); }
        }
      }
      return merged;
    })().catch(error => { indexCache.delete(key); throw error; }));
    return indexCache.get(key);
  };
  const normalizeRecord = record => record.record_format === 'specsheet.record/1' ? {
      ...record, brand:record.brand?.name || '', model:record.identifiers?.find(id => id.role === 'key')?.value || '',
      family:record.relations?.find(link => link.type === 'member_of_family' && link.status === 'approved')?.target || '',
      variant:record.variant_label, identity_caveat:'Identity follows the published manufacturer identifier and approved relationships.',
      marketing_terms:[], documents:record.documents || [], media:record.media || [], sources:record.sources || [],
      notes:Array.isArray(record.notes) ? record.notes.join(' · ') : record.notes || ''} : record;
  const previewDetail = (category, productId) => {
    const key = `preview/${category.id}/${productId}`;
    if (!detailCache.has(key)) detailCache.set(key, category.preview?.products
      ? getJson(`api/v1/${category.preview.products}${encoded(productId)}.json`).then(normalizeRecord).catch(error => { detailCache.delete(key); if (error.message === 'HTTP 404') return null; throw error; })
      : Promise.resolve(null));
    return detailCache.get(key);
  };
  const detailFor = (categoryId, productId, preview = false) => {
    const key = `${categoryId}/${productId}`;
    if (!detailCache.has(key)) detailCache.set(key, getJson(`api/v1/${encoded(categoryId)}/products/${encoded(productId)}.json`).catch(async error => {
      if (error.message !== 'HTTP 404') throw error;
      redirectsPromise ||= getJson('api/v1/redirects.json');
      const targets = (await redirectsPromise)[productId]?.replaced_by || [];
      if (targets.length > 1) { const split = new Error('This product was split into several records.'); split.targets = targets; throw split; }
      if (targets.length === 1 && targets[0] !== productId) return getJson(`api/v1/${encoded(categoryId)}/products/${encoded(targets[0])}.json`);
      throw error;
    }).then(normalizeRecord).catch(error => { detailCache.delete(key); throw error; }));
    if (!preview) return detailCache.get(key);
    // Opt-in: trusted record plus the unreviewed delta (or a preview-only record when no trusted one exists).
    const category = categoryCache.get(categoryId) || {};
    return previewDetail(category, productId).then(delta => {
      if (delta && delta.trusted === false) return {...delta, previewOnly:true, previewSpecs:delta.specs};
      return detailCache.get(key).then(trusted => ({...trusted, previewSpecs:delta?.specs || null, previewSources:delta?.sources || []}));
    });
  };
  const parseRoute = () => {
    const raw = location.hash.slice(1) || '/';
    const [path, query = ''] = raw.split('?');
    let pieces;
    try { pieces = path.split('/').filter(Boolean).map(decodeURIComponent); } catch { pieces = ['invalid']; }
    return {kind: pieces[0] || 'home', parts: pieces.slice(1), params: new URLSearchParams(query)};
  };
  const crumb = (items) => `<nav class="crumbs" aria-label="Breadcrumb"><a href="#/">Catalogue</a>${items.map(item => ` <span aria-hidden="true">/</span> ${item.url ? `<a href="${item.url}">${escapeHtml(item.name)}</a>` : `<span aria-current="page">${escapeHtml(item.name)}</span>`}`).join('')}</nav>`;
  const demoBadge = (item) => item.demo ? '<span class="badge demo">Demo data</span>' : '';
  const statusLabel = {known:'Known',unknown:'Unknown',conflicted:'Conflicted',not_yet_extracted:'Not yet extracted',not_applicable:'Not applicable',not_published:'Not published'};
  const specObject = (product, key) => {
    if (!Object.hasOwn(product.specs || {}, key)) return {value:null,status:'not_yet_extracted',sources:[],confidence:null,source_scope:'none'};
    const raw = product.specs[key];
    if (raw && typeof raw === 'object' && Object.hasOwn(raw, 'status')) return raw;
    return {value:raw,status:raw === null ? 'unknown' : 'known',sources:[],confidence:null,source_scope:'none'};
  };
  const unreviewedBadge = '<span class="badge preview" title="Not yet accepted by a recorded review decision">Unreviewed candidate</span>';
  const acceptedBadge = '<span class="badge direct" title="Accepted by a recorded review decision about its source claims; not independent testing">Accepted into catalogue</span>';
  const previewMark = (html) => `<span class="val-preview" title="Unreviewed candidate value">${html}</span>`;
  const reviewKind = category => category.demo ? 'demo' : category.status === 'accepted' ? 'accepted' : 'legacy';
  const reviewNote = category => ({demo:'Fictional demo data.', accepted:'Records are accepted into the catalogue from cited sources. Acceptance is a review decision about those source claims, not independent testing.', legacy:'Legacy pilot records: not reviewed. Treat values as unconfirmed until sources are checked.'}[reviewKind(category)]);
  const sourceKind = tier => ({manufacturer:'Manufacturer claim', retailer:'Retailer listing', review:'Independent review', regulatory:'Regulatory filing', community:'Community report'}[tier] || (tier ? `${tier[0].toUpperCase()}${tier.slice(1)} source` : 'Source'));
  const isKnown = (spec) => spec?.status === 'known';
  const qualifierLabel = {from:'from', approx:'approx.', up_to:'up to'};
  const displayStructured = (value, field) => {
    const presentation = field?.display;
    const labelMap = {side:'Side',protocol:'Protocol',usb_gbps:'USB speed',pd_in_w:'PD input',pd_out_w:'PD output',dp_alt:'DisplayPort Alt Mode'};
    const human = key => labelMap[key] || key.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
    const atom = (part, unit = '') => part === null || part === undefined || part === ''
      ? '<span class="val-unknown">Unknown</span>'
      : typeof part === 'boolean' ? (part ? 'Yes' : 'No')
      : typeof part === 'object' && part.min != null && part.max != null ? escapeHtml(`${part.min}–${part.max}${unit ? ` ${unit}` : ''}`)
      : typeof part === 'object' ? escapeHtml(JSON.stringify(part))
      : escapeHtml(`${part}${typeof part === 'number' && unit ? ` ${unit}` : ''}`);
    if (presentation?.kind === 'object_table' && field?.key === 'out.ports' && Array.isArray(value)) {
      const connector = {usb_c:'USB-C', usb_a:'USB-A', cable_c:'USB-C cable', cable_lightning:'Lightning cable', wireless:'Wireless', ac:'AC', dc:'DC'};
      const dash = '<span class="val-unknown">—</span>';
      const rows = value.map(item => { const port = item && typeof item === 'object' ? item : {};
        const pdo = [port.fixed_pdos ? `<span class="pdo-line">${escapeHtml(port.fixed_pdos)}</span>` : '', port.pps ? `<span class="pdo-line">PPS ${escapeHtml(port.pps)}</span>` : ''].join('');
        return `<tr><td>${port.name ? escapeHtml(port.name) : dash}${port.direction && port.direction !== 'out' ? ` <small class="muted">(${port.direction === 'in' ? 'input' : 'in/out'})</small>` : ''}</td><td>${port.type ? escapeHtml(connector[port.type] || port.type) : dash}</td><td class="num">${typeof port.max_w === 'number' ? `${port.max_w} W` : dash}</td><td>${pdo || dash}</td></tr>`; }).join('');
      return `<table class="nested-spec-table port-table"><thead><tr><th scope="col">Port</th><th scope="col">Connector</th><th scope="col">Max W</th><th scope="col">PDO / PPS</th></tr></thead><tbody>${rows}</tbody></table>`;
    }
    if (presentation?.kind === 'object_table' && Array.isArray(value)) {
      const columns = presentation.columns || [];
      return `<table class="nested-spec-table"><thead><tr>${columns.map(column => `<th scope="col">${escapeHtml(column.label)}</th>`).join('')}</tr></thead><tbody>${value.map(item => `<tr>${columns.map(column => { const part = item && typeof item === 'object' ? item[column.key] : null; return `<td>${part === null || part === undefined || part === '' ? '<span class="val-unknown">Unknown</span>' : escapeHtml(typeof part === 'number' ? `${part}${column.unit ? ` ${column.unit}` : ''}` : String(part))}</td>`; }).join('')}</tr>`).join('')}</tbody></table>`;
    }
    if (presentation?.kind === 'delimited_list' && presentation.separator === 'semicolon_newline' && typeof value === 'string') {
      const parts = value.split(/[;\r\n]+/).map(part => part.trim()).filter(Boolean);
      return parts.length ? `<ul class="condition-list">${parts.map(part => `<li>${escapeHtml(part)}</li>`).join('')}</ul>` : escapeHtml(value);
    }
    if (Array.isArray(value) && value.length && value.every(item => item && typeof item === 'object' && !Array.isArray(item))) {
      const described = field?.items?.fields || [];
      const keys = [...new Set([...described.map(item => item.key), ...value.flatMap(item => Object.keys(item))])];
      const columns = keys.map(key => ({key, label: described.find(item => item.key === key)?.label || human(key), unit:described.find(item => item.key === key)?.unit}));
      return `<div class="nested-scroll" role="region" aria-label="${escapeHtml(field?.label || 'Structured values')}" tabindex="0"><table class="nested-spec-table"><thead><tr>${columns.map(c => `<th scope="col">${escapeHtml(c.label)}${c.unit ? ` (${escapeHtml(c.unit)})` : ''}</th>`).join('')}</tr></thead><tbody>${value.map(item => `<tr>${columns.map(c => `<td>${atom(item[c.key], c.unit)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    }
    if (Array.isArray(value)) return `<ul class="condition-list">${value.map(item => `<li>${atom(item)}</li>`).join('')}</ul>`;
    if (value && typeof value === 'object') return `<dl class="object-spec">${Object.entries(value).map(([key, part]) => `<dt>${escapeHtml(human(key))}</dt><dd>${atom(part, field?.unit)}</dd>`).join('')}</dl>`;
    return null;
  };
  const displayValue = (spec, field, compact = false) => {
    if (!isKnown(spec)) {
      if (spec.status === 'conflicted') return `<span class="val-conflict">Conflicted</span>${spec.value != null ? `<div class="conflict-value">${displayStructured(spec.value, field) ?? escapeHtml(formatRaw(spec.value, field, compact))}</div>` : ''}`;
      return `<span class="val-unknown">${escapeHtml(statusLabel[spec.status] || 'Unknown')}</span>`;
    }
    const value = spec.value;
    if (typeof value === 'boolean') return `<span class="${value ? 'val-true' : 'val-false'}">${value ? 'Yes' : 'No'}</span>`;
    if (Array.isArray(value) && value.length === 0) return '<span class="muted">Known empty list</span>';
    const structured = displayStructured(value, field);
    if (structured !== null) return structured;
    const qualifier = qualifierLabel[spec.qualifier];
    return escapeHtml(`${qualifier ? `${qualifier} ` : ''}${spec.display || formatRaw(value, field, compact)}`);
  };
  const formatRaw = (value, field, compact = false) => {
    if (Array.isArray(value)) {
      if (value.length && typeof value[0] === 'object') return value.map(v => Object.entries(v).map(([key, part]) => `${key.replaceAll('_', ' ')}: ${part}`).join(' · ')).join(compact ? '; ' : ' · ');
      return value.join(', ');
    }
    if (value && typeof value === 'object') return value.min != null && value.max != null ? `${value.min}–${value.max}${field?.unit ? ` ${field.unit}` : ''}` : JSON.stringify(value);
    if (typeof value === 'number') return field?.unit ? `${Math.abs(value) >= 1000 ? value.toLocaleString('en-US') : value} ${field.unit}` : String(value);
    return String(value);
  };
  const basisLabels = {power_basis:{label:'Power basis',values:{energy_star_on_mode:'ENERGY STAR on-mode test',energy_star_sleep:'ENERGY STAR sleep-mode test'}}, cts_version:{label:'DisplayHDR CTS'}, cache_state:{label:'Cache state',values:{in_slc_cache:'in SLC cache'}}, claim_basis:{label:'Claim basis',values:{mfr_in_house_lab:'manufacturer in-house lab',mfr_unstated:'unstated',mfr_reported_certified:'manufacturer-reported certification',third_party_certified:'third-party certified',independent_measured:'independent measurement'}}, power_mode:{label:'Mode',values:{quiet:'quiet',standard:'standard',max:'max',unstated:'unstated'}}};
  const modeLabels = {negotiated:'negotiated', sustained:'sustained', peak:'peak', advertised_by_device:'advertised by device'};
  const kindLabels = {official:'Manufacturer-stated', measured:'Measured', derived:'Derived', reported:'Reported'};
  const basisText = basis => Object.entries(basis || {}).map(([key, value]) => { const meta = basisLabels[key]; return `${meta?.label || key.replaceAll('_', ' ')}: ${key === 'cts_version' ? `v${value}` : (meta?.values?.[value] || String(value).replaceAll('_', ' '))}`; });
  const altSources = (item, sources) => (item.sources || []).map(id => (sources || []).find(source => source.id === id)).filter(Boolean).map(source => { const url = safeUrl(source.url); return url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label || new URL(url).host)}</a>` : escapeHtml(source.label || 'Source'); });
  const alternativeItem = (item, field, sources) => {
    const q = qualifierLabel[item.qualifier];
    const shown = displayStructured(item.value, field) ?? escapeHtml(`${q ? `${q} ` : ''}${item.display || formatRaw(item.value, field)}`);
    const tags = [...basisText(item.basis), ...(item.measurement_mode ? [`Mode: ${modeLabels[item.measurement_mode] || item.measurement_mode}`] : [])];
    const links = altSources(item, sources);
    return `<li class="alt-item"><strong class="alt-value">${shown}</strong> <span class="muted">${escapeHtml(kindLabels[item.kind] || 'Reported')}${tags.length ? ` · ${escapeHtml(tags.join(' · '))}` : ''}${links.length ? ` · ${links.join(', ')}` : ''}</span></li>`;
  };
  const valueWithContext = (spec, field, sources = []) => {
    const extra = [];
    const noHeadline = spec.status === 'unknown' && spec.alternatives?.length;
    if (spec.inherited_from) extra.push(`<small class="value-note">From model ${escapeHtml(typeof spec.inherited_from === 'string' ? spec.inherited_from : spec.inherited_from.id || spec.inherited_from.name || JSON.stringify(spec.inherited_from))}</small>`);
    if (spec.status === 'known' && spec.basis && Object.keys(spec.basis).length) extra.push(`<small class="value-note">${escapeHtml(basisText(spec.basis).join(' · '))}</small>`);
    if (spec.revision_applicability) extra.push(`<small class="value-note revision-applicability">${spec.revision_applicability === 'all' ? 'Applies to all hardware revisions' : 'Revision not specified by source'}</small>`);
    if (spec.conditional?.length) extra.push(`<div class="value-details"><strong>Conditions</strong><ul>${spec.conditional.map(item => `<li>${escapeHtml(formatRaw(item.conditions, field))}: ${displayStructured(item.value,field) ?? escapeHtml(formatRaw(item.value,field))}</li>`).join('')}</ul></div>`);
    if (noHeadline) extra.push(`<small class="value-note">${escapeHtml(spec.note || 'No single headline: the sources state this under different bases, so the values are not comparable.')}</small>`);
    if (spec.alternatives?.length) extra.push(`<div class="value-details"><strong>${noHeadline ? 'Reported values' : 'Reported alternatives'}</strong><ul class="alt-list">${spec.alternatives.map(item => alternativeItem(item, field, sources)).join('')}</ul></div>`);
    return (noHeadline ? '<span class="val-unknown">No single value</span>' : displayValue(spec, field)) + extra.join('');
  };
  // Opt-in preview overlay on a detail page: the unreviewed value always sits below, never replaces, the trusted one.
  const previewOverlay = (record, key, field) => {
    const delta = record.previewSpecs?.[key];
    if (!delta || record.previewOnly || (JSON.stringify([delta.value, delta.display, delta.qualifier]) === JSON.stringify([record.specs?.[key]?.value, record.specs?.[key]?.display, record.specs?.[key]?.qualifier]) && delta.status === record.specs?.[key]?.status)) return '';
    return `<div class="value-details preview-note candidate-value">${unreviewedBadge} ${displayValue(delta, field)}<div class="evidence-cell">${evidenceMarkup({sources:record.previewSources || [], record_format:true}, delta, {candidate:true})}</div></div>`;
  };
  const errorPanel = (title, message, action = '<a href="#/">Return to catalogue</a>') => `<section class="state-panel" role="alert"><h1>${escapeHtml(title)}</h1><p>${escapeHtml(message)}</p><div class="inline-actions">${action}</div></section>`;
  const setLoading = (label) => { main.innerHTML = `<div class="loading" role="status">${escapeHtml(label)}</div>`; };
  const setTitle = (title) => { document.title = `${title} — specsheet`; };
  const schemeQuery = matchMedia('(prefers-color-scheme: dark)');
  const applyTheme = (theme) => { document.documentElement.dataset.theme = theme === 'system' ? (schemeQuery.matches ? 'dark' : 'light') : theme; themeSelect.value = theme; };
  let savedTheme = 'system';
  try { savedTheme = localStorage.getItem('specsheet-theme') || 'system'; } catch { /* storage can be disabled */ }
  if (!['system','light','dark'].includes(savedTheme)) savedTheme = 'system';
  applyTheme(savedTheme);
  schemeQuery.addEventListener('change', () => { if (themeSelect.value === 'system') applyTheme('system'); });
  themeSelect.addEventListener('change', () => { applyTheme(themeSelect.value); try { localStorage.setItem('specsheet-theme', themeSelect.value); } catch { /* keep session choice */ } });

  async function renderRoute() {
    const sequence = ++routeSequence;
    const route = parseRoute();
    setLoading('Loading catalogue…');
    try {
      const all = await categories();
      if (sequence !== routeSequence) return;
      if (route.kind === 'home') { renderHome(all); main.focus(); return; }
      const category = categoryCache.get(route.parts[0]);
      if (!category) { main.innerHTML = errorPanel('Category not found', 'This category is not in the current static dataset.'); return; }
      if (category.schema && !category.schemaLoaded) {
        const schema = await getJson(`api/v1/${category.schema}`);
        if (sequence !== routeSequence) return;
        category.fields = schema.fields;
        category.groups = schema.groups;
        category.schemaLoaded = true;
      }
      if (route.kind === 'category' && route.parts.length === 1) { await renderCategory(category, route.params, sequence); if (sequence === routeSequence) main.focus(); return; }
      if (route.kind === 'product' && route.parts.length === 2) { await renderProduct(category, route.parts[1], route.params, sequence); if (sequence === routeSequence) main.focus(); return; }
      if (route.kind === 'compare' && route.parts.length === 1) { await renderCompare(category, route.params, sequence); if (sequence === routeSequence) main.focus(); return; }
      main.innerHTML = errorPanel('Page not found', 'This catalogue address is not available.');
    } catch (error) {
      if (sequence !== routeSequence) return;
      main.innerHTML = errorPanel('Catalogue could not load', `The static data could not be read (${error.message}). Check your connection and try again.`, '<button type="button" id="retry-load">Retry loading</button><a href="#/">Return to catalogue</a>');
      main.querySelector('#retry-load')?.addEventListener('click', renderRoute);
    }
  }

  function renderHome(all) {
    setTitle('Catalogue');
    main.innerHTML = `<section class="lead-panel"><h1>Product specifications, with context.</h1><p>Search across brands, inspect the exact variant, and see where each recorded fact came from. Start with a category.</p></section><section aria-labelledby="cat-heading"><h2 id="cat-heading">Browse categories</h2><div class="category-list">${all.map(category => `<a class="category-row" href="${categoryUrl(category.id)}"><span><strong>${escapeHtml(category.name)}</strong> ${demoBadge(category)}<p>${escapeHtml(category.description)}</p></span><span class="count-pill">${category.count} ${category.count === 1 ? 'product' : 'products'} →</span></a>`).join('')}</div></section><p class="muted" style="margin-top:25px;max-width:72ch">Records marked “Accepted into catalogue” have a recorded review decision about their source claims; that is not independent testing. Legacy pilot records and unreviewed candidates are labelled as such. “Unknown” means no value is recorded, not “No”.</p>`;
  }

  function initialState(category, params) {
    const defaults = category.fields.filter(field => field.column).map(field => field.key);
    const available = new Set(category.fields.map(field => field.key));
    const cols = params.has('cols') ? params.get('cols').split(',').filter(key => available.has(key)) : defaults;
    const ids = (params.get('ids') || '').split(',').filter(Boolean).slice(0, 4);
    const filters = {};
    for (const field of category.fields.filter(f => f.facet)) {
      for (const suffix of (['number','integer','range'].includes(field.type) && field.facet?.kind !== 'enum' ? ['min','max'] : ['value'])) {
        const key = `f_${field.key}_${suffix}`;
        if (params.has(key)) filters[key] = params.get(key);
      }
    }
    return {q: params.get('q') || '', brand: params.get('brand') || '', filters,
      sort: ['coverage','brand','name','model',...category.fields.map(f => f.key)].includes(params.get('sort')) ? params.get('sort') : 'coverage',
      dir: params.has('dir') ? (params.get('dir') === 'desc' ? 'desc' : 'asc') : (params.get('sort') && params.get('sort') !== 'coverage' ? 'asc' : 'desc'),
      preview: params.get('preview') === '1' && !!category.preview, view: params.get('view') === 'grouped' ? 'grouped' : 'flat', cols, ids, page:Math.max(1, Number.parseInt(params.get('page') || '1', 10) || 1)};
  }
  function categoryStateQuery(state) {
    const params = new URLSearchParams();
    if (state.q) params.set('q', state.q);
    if (state.brand) params.set('brand', state.brand);
    for (const [key, value] of Object.entries(state.filters)) if (value) params.set(key, value);
    if (state.preview) params.set('preview', '1');
    if (state.view === 'grouped') params.set('view', 'grouped');
    if (state.sort !== 'coverage') params.set('sort', state.sort);
    if (state.dir !== (state.sort === 'coverage' ? 'desc' : 'asc')) params.set('dir', state.dir);
    params.set('cols', state.cols.join(','));
    if (state.ids.length) params.set('ids', state.ids.join(','));
    if (state.page > 1) params.set('page', String(state.page));
    return params.toString();
  }
  function persistCategoryState(category, state) {
    history.replaceState(null, '', categoryUrl(category.id, `?${categoryStateQuery(state)}`));
  }
  const validatedReturnQuery = (category, params) => params.has('return') ? categoryStateQuery(initialState(category, new URLSearchParams(params.get('return')))) : '';
  const returnUrl = (category, query) => categoryUrl(category.id, query ? `?${query}` : '');
  const withPreview = (category, query, preview) => { if (!preview || !category.preview) return query; const state = initialState(category, new URLSearchParams(query)); state.preview = true; return categoryStateQuery(state); };
  const returnWithIds = (category, query, ids) => { const state = initialState(category, new URLSearchParams(query)); state.ids = ids; return categoryStateQuery(state); };
  // Facet aliases live in the shell, not the data: a LiDAR filter must also match dToF (a kind of LiDAR). Keyed by field key, then selected value.
  const FACET_ALIASES = {'nav.type': {lidar: ['lidar', 'dtof']}};
  const aliasLabel = (field, option) => { const extra = (FACET_ALIASES[field.key]?.[option] || []).filter(value => value !== option); return extra.length ? `${option} (incl. ${extra.join(', ')})` : option; };
  // Measurement-method conditions: figures with a different claim basis or operating mode are not like-for-like.
  const METHOD_DEFAULTS = {claim_basis: 'mfr_unstated', power_mode: 'unstated'};
  const methodKeys = field => (field?.conditions || []).filter(key => Object.hasOwn(METHOD_DEFAULTS, key));
  const methodValue = (spec, key) => spec?.basis?.[key] ?? METHOD_DEFAULTS[key];
  const methodsDiffer = (specs, field) => { const known = specs.filter(isKnown); return known.length > 1 && methodKeys(field).some(key => new Set(known.map(spec => methodValue(spec, key))).size > 1); };
  const methodsFlag = (specs, field) => { const parts = methodKeys(field).map(key => { const labels = [...new Set(specs.filter(isKnown).map(spec => methodValue(spec, key)))].map(value => basisLabels[key]?.values?.[value] || value); return labels.length > 1 ? `${basisLabels[key]?.label || key}: ${labels.join(' vs ')}` : ''; }).filter(Boolean); return `<small class="methods-flag" title="${escapeHtml(parts.join('; ') || 'Measurement methods differ')}">methods differ</small>`; };
  const facetKey = (field, suffix = 'value') => `f_${field.key}_${suffix}`;
  const groupLabel = (category, id) => category.groups?.find(group => group.id === id)?.label || id;
  const facetControl = (field, rows, state) => {
    const key = facetKey(field);
    const label = escapeHtml(field.label);
    const value = escapeHtml(state.filters[key] || '');
    if (['number','integer','range'].includes(field.type) && field.facet?.kind !== 'enum') {
      const min = facetKey(field, 'min'), max = facetKey(field, 'max');
      const minLabel = field.type === 'range' ? 'From at least' : 'At least';
      const maxLabel = field.type === 'range' ? 'To at most' : 'At most';
      return `<div class="filter-field"><label>${label}${field.unit ? ` (${escapeHtml(field.unit)})` : ''}</label><div class="range-inputs"><input type="number" data-filter="${min}" aria-label="${minLabel} ${label}" placeholder="Min" value="${escapeHtml(state.filters[min] || '')}"><input type="number" data-filter="${max}" aria-label="${maxLabel} ${label}" placeholder="Max" value="${escapeHtml(state.filters[max] || '')}"></div></div>`;
    }
    if (field.type === 'bool') return `<div class="filter-field"><label for="facet-${field.key}">${label}</label><select id="facet-${field.key}" data-filter="${key}"><option value="">Any</option><option value="yes" ${value === 'yes' ? 'selected' : ''}>Yes</option><option value="no" ${value === 'no' ? 'selected' : ''}>No</option><option value="unknown" ${value === 'unknown' ? 'selected' : ''}>Unknown</option></select></div>`;
    if (field.type === 'enum') {
      const options = field.enum || field.options || [...new Set(rows.map(row => specObject(row, field.key)).filter(isKnown).map(s => s.value).filter(v => typeof v === 'string'))].sort();
      return `<div class="filter-field"><label for="facet-${field.key}">${label}</label><select id="facet-${field.key}" data-filter="${key}"><option value="">Any</option>${options.map(option => `<option value="${escapeHtml(option)}" ${option === state.filters[key] ? 'selected' : ''}>${escapeHtml(aliasLabel(field, option))}</option>`).join('')}<option value="__unknown" ${value === '__unknown' ? 'selected' : ''}>Unknown</option></select></div>`;
    }
    return `<div class="filter-field"><label for="facet-${field.key}">${label}</label><input id="facet-${field.key}" type="search" data-filter="${key}" value="${value}" placeholder="Contains…"></div>`;
  };
  const previewControl = (category, state, rows = []) => {
    if (!category.preview) return '';
    const only = rows.filter(row => row.unreviewed).length, withCandidates = rows.filter(row => !row.unreviewed && row.unreviewedKeys?.size).length;
    const note = state.preview
      ? `Showing ${rows.length} products: ${rows.length - only} accepted, plus ${only} unreviewed candidate-only products (marked). ${withCandidates} accepted products also carry unreviewed candidate values beneath their accepted ones.`
      : (category.preview.only_preview ? `Adds ${category.preview.only_preview} candidate-only products from brands without a review decision yet<span id="preview-brands"></span>, and shows unreviewed candidate values beneath accepted ones.` : 'Adds no new products; it only shows unreviewed candidate values beneath those of products already listed.');
    return `<div class="preview-toggle"><label><input type="checkbox" id="preview-toggle" ${state.preview ? 'checked' : ''}>Include unreviewed candidates (preview)</label><p>${note} Candidates are labelled “Unreviewed candidate”, never replace accepted values, and never remove accepted products.</p></div>`;
  };
  const filterMarkup = (category, rows, state) => {
    const brands = [...new Set(rows.map(row => row.brand))].sort();
    const common = category.fields.filter(f => f.facet && (typeof f.facet !== 'object' || f.facet.default_visible));
    const more = category.fields.filter(f => f.facet && typeof f.facet === 'object' && !f.facet.default_visible);
    const grouped = fields => [...new Set(fields.map(f => f.group))].map(group => `<section class="filter-group"><h3>${escapeHtml(groupLabel(category, group))}</h3>${fields.filter(f => f.group === group).map(f => facetControl(f, rows, state)).join('')}</section>`).join('');
    const hasActiveMore = more.some(field => Object.keys(state.filters).some(key => key.startsWith(`f_${field.key}_`) && state.filters[key]));
    return `<div class="filters-body"><div class="filter-field"><label for="brand-filter">Brand</label><select id="brand-filter"><option value="">All brands</option>${brands.map(brand => `<option value="${escapeHtml(brand)}" ${state.brand === brand ? 'selected' : ''}>${escapeHtml(brand)}</option>`).join('')}</select></div>${grouped(common)}${more.length ? `<details class="more-filters" ${hasActiveMore ? 'open' : ''}><summary>More filters (${more.length})</summary>${grouped(more)}</details>` : ''}<button type="button" class="rail-reset" id="clear-filters">Reset filters</button></div>`;
  };
  const matchFacet = (row, field, filters) => {
    const spec = specObject(row, field.key);
    if (['number','integer','range'].includes(field.type) && field.facet?.kind !== 'enum') {
      const minRaw = filters[facetKey(field, 'min')], maxRaw = filters[facetKey(field, 'max')];
      if (!minRaw && !maxRaw) return true;
      if (!isKnown(spec)) return false;
      const low = field.type === 'range' ? Number(spec.value?.min) : Number(spec.value);
      const high = field.type === 'range' ? Number(spec.value?.max) : Number(spec.value);
      if (!Number.isFinite(low) || !Number.isFinite(high)) return false;
      return (!minRaw || low >= Number(minRaw)) && (!maxRaw || high <= Number(maxRaw));
    }
    const query = filters[facetKey(field)];
    if (!query) return true;
    if (query === '__unknown' || (field.type === 'bool' && query === 'unknown')) return !isKnown(spec);
    if (!isKnown(spec)) return false;
    if (field.type === 'bool') return spec.value === (query === 'yes');
    if (field.type === 'enum') return (FACET_ALIASES[field.key]?.[query] || [query]).includes(spec.value);
    return formatRaw(spec.value, field).toLocaleLowerCase().includes(query.toLocaleLowerCase());
  };
  const coverage = row => { const parts = Object.values(row.completeness || {}); const total = parts.reduce((n, p) => n + p[1], 0); return total ? parts.reduce((n, p) => n + p[0], 0) / total : 0; };
  const getSortValue = (row, key) => {
    if (key === 'coverage') return coverage(row);
    if (['brand','name','model'].includes(key)) return row[key];
    const spec = specObject(row, key);
    return isKnown(spec) ? spec.value : null;
  };
  const compareSort = (a, b, state) => {
    const left = getSortValue(a, state.sort), right = getSortValue(b, state.sort);
    if (state.sort === 'coverage') return (Number(!!a.unreviewed) - Number(!!b.unreviewed)) || ((state.dir === 'desc' ? right - left : left - right)) || a.brand.localeCompare(b.brand) || a.name.localeCompare(b.name, undefined, {numeric:true});
    if (left == null && right != null) return 1;
    if (left != null && right == null) return -1;
    if (left == null && right == null) return a.name.localeCompare(b.name);
    let delta;
    if (typeof left === 'number' && typeof right === 'number') delta = left - right;
    else if (typeof left === 'boolean' && typeof right === 'boolean') delta = Number(left) - Number(right);
    else delta = formatRaw(left).localeCompare(formatRaw(right), undefined, {numeric:true, sensitivity:'base'});
    return (state.dir === 'asc' ? delta : -delta) || a.name.localeCompare(b.name);
  };
  const selectedRows = (rows, state) => state.ids.map(id => rows.find(row => row.id === id)).filter(Boolean);

  const modelLabel = category => category.id === 'laptops' ? 'MTM / part number' : 'Model number';
  const requestNote = 'Public if submitted; GitHub account required. Include product information only.';
  const activeFilters = state => !!state.brand || Object.values(state.filters).some(Boolean);

  async function renderCategory(category, params, sequence) {
    setLoading(`Loading ${category.name}…`);
    const state = initialState(category, params);
    const rows = await indexFor(category, state.preview);
    if (sequence !== routeSequence) return;
    setTitle(category.name);
    const droppedIds = state.ids.filter(id => !rows.some(row => row.id === id));
    state.ids = state.ids.filter(id => !droppedIds.includes(id));
    const configTotals = new Map();
    for (const row of rows) if (row.kind === 'configuration' && row.parent_id) configTotals.set(row.parent_id, (configTotals.get(row.parent_id) || 0) + 1);
    const hasConfigs = configTotals.size > 0;
    const droppedNote = droppedIds.length ? `${droppedIds.length} selected ${droppedIds.length === 1 ? 'product was' : 'products were'} removed from your selection because ${category.preview && !state.preview ? 'unreviewed candidate rows are off' : 'not in this catalogue'}.` : '';
    main.innerHTML = `${crumb([{name:category.name}])}<div class="page-head"><h1>${escapeHtml(category.name)} ${demoBadge(category)}</h1><p class="intro">${escapeHtml(category.description)} ${escapeHtml(reviewNote(category))} Open a product to inspect its sources and uncertainty.</p></div><div class="catalogue-layout"><aside class="filter-rail"><details open><summary>Filters</summary>${previewControl(category, state, rows)}${filterMarkup(category, rows, state)}</details></aside><section class="catalogue-results" aria-label="Products"><div class="results-head"><label class="search-field" for="product-search">Search name, brand, identifier or a pasted retail title<input id="product-search" type="search" placeholder="Search products…" value="${escapeHtml(state.q)}" autocomplete="off"></label><div><h2>Compare the facts</h2><p>Choose 2–4 products to compare.</p></div></div><div class="results-tools"><span class="meta" id="result-count" role="status"></span><label class="sort-control">Sort <select id="sort-select" aria-label="Sort products"><option value="coverage">Most complete first</option><option value="brand">Brand</option><option value="name">Product name</option><option value="model">${escapeHtml(modelLabel(category))}</option><option value="__column" disabled>Column (use header)</option></select></label>${hasConfigs ? `<label class="sort-control">View <select id="view-select" aria-label="Result view"><option value="flat" ${state.view === 'flat' ? 'selected' : ''}>Flat list</option><option value="grouped" ${state.view === 'grouped' ? 'selected' : ''}>Grouped by model</option></select></label>` : ''}<details class="column-menu"><summary>Choose columns</summary><div class="column-options"><button type="button" id="reset-columns">Reset to default columns</button>${[...new Set(category.fields.map(field => field.group))].map(group => `<fieldset><legend>${escapeHtml(groupLabel(category,group))}</legend>${category.fields.filter(field => field.group === group).map(field => `<label><input type="checkbox" data-column="${escapeHtml(field.key)}" ${state.cols.includes(field.key) ? 'checked' : ''}>${escapeHtml(field.label)}</label>`).join('')}</fieldset>`).join('')}</div></details></div><p class="request-prompt">Can’t find it? <a id="request-product" href="${escapeHtml(missingIssueUrl(category.id, state.q))}" target="_blank" rel="noopener noreferrer">Prepare GitHub issue draft</a> for a product request. ${requestNote} A draft opens only if you choose this link.</p><div id="selection-status" class="visually-hidden" role="status" aria-live="polite" aria-atomic="true"></div><p id="selection-notice" class="inline-notice" role="status" ${droppedNote ? '' : 'hidden'}>${escapeHtml(droppedNote)}</p><div id="compare-shelf"></div><div id="results-table"></div><div id="pagination"></div></section></div>`;
    const mobileQuery = matchMedia('(max-width: 800px)');
    const filterDisclosure = main.querySelector('.filter-rail > details');
    filterDisclosure.open = !mobileQuery.matches;
    mobileQuery.addEventListener('change', event => { if (filterDisclosure.isConnected) filterDisclosure.open = !event.matches; }, {once:false});
    const search = main.querySelector('#product-search');
    const brandNote = main.querySelector('#preview-brands');
    if (brandNote && category.preview?.only_preview) indexFor(category, true).then(all => {
      const names = [...new Set(all.filter(row => row.unreviewed).map(row => row.brand).filter(Boolean))].sort();
      if (sequence === routeSequence && brandNote.isConnected && names.length) brandNote.textContent = ` (${names.length > 4 ? `${names.slice(0,4).join(', ')} and ${names.length - 4} more` : names.join(', ')})`;
    }).catch(() => { /* the toggle works without the brand hint */ });
    main.querySelector('#preview-toggle')?.addEventListener('change', event => {
      state.preview = event.target.checked; state.page = 1;
      persistCategoryState(category, state);
      renderCategory(category, new URLSearchParams(categoryStateQuery(state)), sequence).then(() => main.querySelector('#preview-toggle')?.focus());
    });
    const sortSelect = main.querySelector('#sort-select');
    sortSelect.addEventListener('change', () => { state.sort = sortSelect.value; state.dir = state.sort === 'coverage' ? 'desc' : 'asc'; update(); });
    main.querySelector('#view-select')?.addEventListener('change', event => { state.view = event.target.value; state.page = 1; update(); });
    search.addEventListener('input', () => { state.q = search.value; state.page = 1; update(); });
    main.querySelector('#brand-filter').addEventListener('change', event => { state.brand = event.target.value; state.page = 1; update(); });
    main.querySelectorAll('[data-filter]').forEach(control => control.addEventListener(control.tagName === 'SELECT' ? 'change' : 'input', () => { state.filters[control.dataset.filter] = control.value; state.page = 1; update(); }));
    const clearFilters = () => {
      state.brand = ''; state.filters = {};
      main.querySelector('#brand-filter').value = '';
      main.querySelectorAll('[data-filter]').forEach(control => { control.value = ''; });
      state.page = 1; update();
    };
    main.querySelector('#clear-filters').addEventListener('click', () => {
      state.q = ''; search.value = '';
      clearFilters(); search.focus();
    });
    main.querySelectorAll('[data-column]').forEach(control => control.addEventListener('change', () => {
      state.cols = [...main.querySelectorAll('[data-column]:checked')].map(input => input.dataset.column);
      update();
    }));
    main.querySelector('#reset-columns').addEventListener('click', () => { state.cols = category.fields.filter(field => field.column).map(field => field.key); main.querySelectorAll('[data-column]').forEach(control => { control.checked = state.cols.includes(control.dataset.column); }); update(); });
    main.querySelector('#pagination').addEventListener('click', event => {
      const button = event.target.closest('[data-page]');
      if (!button) return;
      const direction = button.dataset.dir;
      state.page = Number(button.dataset.page);
      update();
      // The pagination buttons are re-rendered; keep keyboard focus on the same-direction control (or the surviving one) and let #result-count announce the page.
      (main.querySelector(`#pagination [data-dir="${direction}"]:not(:disabled)`) || main.querySelector('#pagination button:not(:disabled)'))?.focus({preventScroll:true});
      main.querySelector('#result-count').scrollIntoView({block:'start'});
    });
    main.querySelector('#results-table').addEventListener('click', event => {
      const broaden = event.target.closest('[data-broaden]');
      if (broaden) { state.q = broaden.dataset.broaden; search.value = state.q; state.page = 1; update(); search.focus(); return; }
      if (event.target.closest('[data-empty-clear]')) { clearFilters(); search.focus(); return; }
      if (event.target.closest('[data-empty-preview]')) { main.querySelector('#preview-toggle')?.click(); return; }
      const button = event.target.closest('[data-sort]');
      if (!button) return;
      const key = button.dataset.sort;
      if (state.sort === key) state.dir = state.dir === 'asc' ? 'desc' : 'asc';
      else { state.sort = key; state.dir = 'asc'; }
      update();
    });
    main.querySelector('#results-table').addEventListener('change', event => {
      const input = event.target.closest('[data-select]');
      if (!input) return;
      if (input.checked && !state.ids.includes(input.dataset.select)) {
        if (state.ids.length >= 4) { input.checked = false; return; }
        state.ids.push(input.dataset.select);
      } else if (!input.checked) state.ids = state.ids.filter(id => id !== input.dataset.select);
      update();
    });
    main.querySelector('#compare-shelf').addEventListener('click', event => {
      const button = event.target.closest('[data-remove]');
      if (!button) return;
      state.ids = state.ids.filter(id => id !== button.dataset.remove);
      update();
    });
    // The listing index carries values only; claim basis / mode come from the detail record of the 2-4 products picked for comparison.
    const methodFields = category.fields.filter(field => methodKeys(field).length);
    function enrichCompared() {
      if (!methodFields.length || state.ids.length < 2) return;
      // Old index builds lack basis: fall back to the detail records. Skipped entirely when the index already carries it.
      if (rows.some(row => methodFields.some(field => row.specs[field.key]?.basis))) return;
      const pending = selectedRows(rows, state).filter(row => !row.methodsLoaded);
      if (!pending.length) return;
      pending.forEach(row => { row.methodsLoaded = true; });
      Promise.all(pending.map(row => detailFor(category.id, row.id).then(record => { for (const field of methodFields) { const detail = record.specs?.[field.key]; if (detail?.basis && row.specs[field.key]?.status === 'known') row.specs[field.key] = {...row.specs[field.key], basis: detail.basis}; } }).catch(() => {}))).then(() => { if (sequence === routeSequence) update(); });
    }
    function update() {
      const active = document.activeElement;
      const focus = active?.closest('#results-table') ? {kind: active.dataset.select ? 'select' : 'sort', value: active.dataset.select || active.dataset.sort} :
        active?.closest('#compare-shelf') ? {kind:'shelf', value:active.dataset.remove} : null;
      const found = searchRows(rows, state.q);
      const hasQuery = !!found.query;
      const base = hasQuery ? rows.filter(row => found.matches.has(row.id)) : rows;
      const filtered = base.filter(row => (!state.brand || row.brand === state.brand) && category.fields.filter(f => f.facet).every(field => matchFacet(row, field, state.filters)))
        .sort((a, b) => { if (hasQuery) { const ma = found.matches.get(a.id), mb = found.matches.get(b.id); const delta = (ma.rank - mb.rank) || (mb.matched.length - ma.matched.length); if (delta) return delta; } return compareSort(a, b, state); });
      sortSelect.value = [...sortSelect.options].some(o => o.value === state.sort && !o.disabled) ? state.sort : '__column';
      main.querySelector('#request-product').href = missingIssueUrl(category.id, state.q);
      const grouped = state.view === 'grouped' && hasConfigs;
      let units;
      if (grouped) {
        const groups = new Map();
        for (const row of filtered) { const key = row.kind === 'configuration' && row.parent_id ? row.parent_id : row.id; if (!groups.has(key)) groups.set(key, []); groups.get(key).push(row); }
        units = [...groups.entries()].map(([key, members]) => ({key, members}));
      } else units = filtered.map(row => ({key:null, members:[row]}));
      const pageSize = grouped ? 20 : 50;
      const pages = Math.max(1, Math.ceil(units.length / pageSize));
      state.page = Math.min(state.page, pages);
      const pageUnits = units.slice((state.page - 1) * pageSize, state.page * pageSize);
      const groupInfo = grouped ? new Map(pageUnits.filter(unit => unit.members[0].kind === 'configuration' && unit.members[0].parent_id).map(unit => [unit.members[0].id, {parent:unit.key, name:unit.members[0].name, matching:unit.members.length, total:configTotals.get(unit.key) || unit.members.length}])) : null;
      main.querySelector('#result-count').textContent = `${filtered.length} of ${rows.length} products${state.preview ? ' (accepted plus unreviewed candidates)' : ''}${grouped ? `, in ${units.length} ${units.length === 1 ? 'group' : 'groups'}` : ''}${pages > 1 ? `. Page ${state.page} of ${pages}` : ''}`;
      const query = categoryStateQuery(state);
      renderTable(category, pageUnits.flatMap(unit => unit.members), state, query, {found, total:rows.length, hiddenByFilters:base.length - filtered.length, baseCount:base.length, groupInfo, compared:selectedRows(rows, state)});
      main.querySelector('#pagination').innerHTML = pages > 1 ? `<nav class="pagination" aria-label="Result pages"><button type="button" data-dir="prev" data-page="${state.page - 1}" ${state.page === 1 ? 'disabled' : ''}>Previous</button><span>Page ${state.page} of ${pages}</span><button type="button" data-dir="next" data-page="${state.page + 1}" ${state.page === pages ? 'disabled' : ''}>Next</button></nav>` : '';
      renderShelf(category, rows, state, query);
      main.querySelector('#selection-status').textContent = `${state.ids.length} selected. ${state.ids.length >= 4 ? 'Maximum of 4; remove one to add another.' : state.ids.length >= 2 ? 'Compare products available.' : 'Choose 2 to 4 products to compare.'}`;
      persistCategoryState(category, state);
      enrichCompared();
      if (focus?.kind === 'select') [...main.querySelectorAll('[data-select]')].find(input => input.dataset.select === focus.value)?.focus();
      if (focus?.kind === 'sort') [...main.querySelectorAll('[data-sort]')].find(button => button.dataset.sort === focus.value)?.focus();
      if (focus?.kind === 'shelf') ([...main.querySelectorAll('#compare-shelf [data-remove]')].find(button => button.dataset.remove === focus.value) || main.querySelector('#compare-shelf [data-remove]') || search).focus();
    }
    update();
  }

  // Table cell: accepted value first; an unreviewed candidate sits beneath it with a text label (never dashed styling alone).
  function cellValue(category, row, field) {
    const spec = specObject(row, field.key);
    let html = displayValue(spec, field, true);
    if (field.key === 'cpu.model' && isKnown(spec)) {
      const cores = specObject(row, 'cpu.cores'), threads = specObject(row, 'cpu.threads');
      const note = [isKnown(cores) ? `${cores.value}C` : '', isKnown(threads) ? `${threads.value}T` : ''].filter(Boolean).join(' / ');
      if (note) html += `<small class="value-note">${escapeHtml(note)}</small>`;
    }
    const candidate = row.candidates?.[field.key];
    if (candidate) return `${html}<div class="candidate-value"><span class="badge preview">Unreviewed candidate</span> ${displayValue(candidate, field, true)}</div>`;
    return row.unreviewed && row.unreviewedKeys?.has(field.key) ? previewMark(html) : html;
  }
  function emptyState(category, state, ctx) {
    const q = state.q.trim();
    const searched = `Searched brand, name, variant and identifiers across ${ctx.total} ${state.preview ? 'accepted and unreviewed candidate' : 'catalogue'} products.`;
    const request = `<a class="button-link" href="${escapeHtml(missingIssueUrl(category.id, state.q))}" target="_blank" rel="noopener noreferrer">Prepare GitHub issue draft</a><small>${requestNote} An unmatched title is not a confirmed missing product.</small>`;
    if (q && ctx.baseCount > 0) return `<div class="empty-table"><strong>${ctx.baseCount} ${ctx.baseCount === 1 ? 'product matches' : 'products match'} this search but ${ctx.baseCount === 1 ? 'is' : 'are'} hidden by the active filters</strong><p>Clear the filters to see ${ctx.baseCount === 1 ? 'it' : 'them'}.</p><div class="empty-actions"><button type="button" data-empty-clear>Clear filters</button></div></div>`;
    if (q) {
      const terms = [...ctx.found.identifiers, ...ctx.found.terms.filter(term => !ctx.found.identifiers.some(id => id.toLocaleLowerCase() === term))].slice(0, 4);
      return `<div class="empty-table"><strong>No match for this search</strong><p>${searched} ${ctx.found.identifiers.length ? `Identifiers looked for: ${escapeHtml(ctx.found.identifiers.join(', '))}. ` : 'No model number was recognised in the text. '}A failed search does not show that the product is absent from the catalogue or the market.</p><div class="empty-actions">${terms.map(term => `<button type="button" data-broaden="${escapeHtml(term)}">Search only “${escapeHtml(term)}”</button>`).join('')}${activeFilters(state) ? '<button type="button" data-empty-clear>Clear filters</button>' : ''}${category.preview && !state.preview ? '<button type="button" data-empty-preview>Also search unreviewed candidates</button>' : ''}</div><div class="empty-request">${request}</div></div>`;
    }
    return `<div class="empty-table"><strong>No products match these filters</strong><p>Try fewer filters.</p><div class="empty-actions"><button type="button" data-empty-clear>Clear filters</button></div></div>`;
  }
  function renderTable(category, rows, state, query, ctx = {}) {
    const fields = state.cols.map(key => category.fields.find(field => field.key === key)).filter(Boolean);
    const columnHeader = (key, label, cls = '') => `<th scope="col" class="${cls}" aria-sort="${state.sort === key ? (state.dir === 'asc' ? 'ascending' : 'descending') : 'none'}"><button type="button" data-sort="${escapeHtml(key)}">${escapeHtml(label)} ${state.sort === key ? (state.dir === 'asc' ? '↑' : '↓') : ''}</button></th>`;
    const target = main.querySelector('#results-table');
    if (!rows.length) { target.innerHTML = emptyState(category, state, {found:{identifiers:[], terms:[]}, total:rows.length, baseCount:0, ...ctx}); return; }
    const compared = ctx.compared || [];
    // Index rows carry basis (row.x[k].basis), so every row on the page is judged, not only the selected ones.
    const methodPool = rows.length > 1 ? rows : compared;
    const methodDiff = new Set(methodPool.length > 1 ? fields.filter(f => methodKeys(f).length && methodsDiffer(methodPool.map(r => specObject(r, f.key)), f)).map(f => f.key) : []);
    const cellHtml = (row, f) => cellValue(category, row, f) + (methodDiff.has(f.key) && isKnown(specObject(row, f.key)) && methodKeys(f).some(key => methodValue(specObject(row, f.key), key) !== METHOD_DEFAULTS[key]) ? ' ' + methodsFlag(methodPool.map(r => specObject(r, f.key)), f) : '');
    const body = rows.map(row => {
      const info = ctx.groupInfo?.get(row.id);
      const groupHeader = info ? `<tr class="model-group"><th colspan="${fields.length + 4}" scope="rowgroup">Configurations of <a href="${productUrl(category.id, info.parent, query)}">${escapeHtml(info.name)}</a> <span class="muted">(${info.matching} matching of ${info.total} configurations)</span></th></tr>` : '';
      const why = ctx.found?.matches.get(row.id)?.why;
      const parentLine = row.kind === 'configuration' && row.parent_id ? `<small class="entity-kind">Configuration of <a href="${productUrl(category.id, row.parent_id, query)}">${escapeHtml(row.name)} (model)</a></small>` : row.kind ? `<small class="entity-kind">${escapeHtml(row.kind[0].toUpperCase() + row.kind.slice(1))}</small>` : '';
      return `${groupHeader}<tr class="${state.ids.includes(row.id) ? 'selected' : ''}${row.unreviewed ? ' unreviewed' : ''}"><td class="select-cell"><input type="checkbox" data-select="${escapeHtml(row.id)}" aria-label="Select ${escapeHtml(row.name)} ${escapeHtml(row.model || '')} for comparison" ${state.ids.includes(row.id) ? 'checked' : ''} ${state.ids.length >= 4 && !state.ids.includes(row.id) ? 'disabled' : ''}></td><td class="col-brand">${escapeHtml(row.brand)}</td><td class="name-cell"><span class="brand-compact">${escapeHtml(row.brand)}</span><a href="${productUrl(category.id, row.id, query)}">${escapeHtml(row.name)}</a> ${demoBadge(row)}${row.unreviewed ? ` ${unreviewedBadge}` : ''}<span class="code id-compact">${escapeHtml(row.model || '—')}</span>${row.variant_label ? `<small class="variant-label">${escapeHtml(row.variant_label)}</small>` : ''}${parentLine}${why ? `<small class="match-why">${escapeHtml(why)}</small>` : ''}</td><td class="code col-model">${escapeHtml(row.model || '—')}</td>${fields.map(f => `<td class="${['number','integer'].includes(f.type) ? 'num' : ''}">${cellHtml(row, f)}</td>`).join('')}</tr>`;
    }).join('');
    target.innerHTML = `<div class="table-scroll" role="region" aria-label="Product comparison table" tabindex="0"><table><thead><tr><th scope="col" class="select-head">Select</th>${columnHeader('brand','Brand','col-brand')}${columnHeader('name','Product','name-head')}${columnHeader('model', modelLabel(category), 'col-model')}${fields.map(f => columnHeader(f.key, f.label)).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
  }
  function renderShelf(category, rows, state, query) {
    const target = main.querySelector('#compare-shelf');
    if (!state.ids.length) { target.innerHTML = ''; return; }
    const chosen = selectedRows(rows, state);
    target.innerHTML = `<div class="compare-shelf"><strong>${chosen.length} selected</strong><div class="selected-items">${chosen.map(row => `<button type="button" data-remove="${escapeHtml(row.id)}" aria-label="Remove ${escapeHtml(row.name)}">${escapeHtml(row.brand)} ${escapeHtml(row.model || row.name)} ×</button>`).join('')}</div>${chosen.length >= 2 ? `<a class="button-link primary" href="${compareUrl(category.id, state.ids, false, query)}">Compare products</a>` : '<small>Select at least one more product.</small>'}</div>`;
  }

  const evidenceMarkup = (record, spec, {candidate = false} = {}) => {
    const direct = (spec.sources || []).map(id => record.sources.find(source => source.id === id)).filter(Boolean);
    const context = direct.length ? [] : (record.record_format ? [] : record.sources);
    const inherited = !!spec.inherited_from || spec.source_scope === 'inherited';
    const kind = direct.length ? 'direct' : (spec.status === 'conflicted' ? 'warning' : '');
    const types = [...new Set(direct.map(source => sourceKind(source.tier)))].join(', ');
    const label = `${candidate ? 'Candidate: ' : ''}${direct.length ? `${types} (${inherited ? 'inherited from model' : 'field source'})` : (context.length ? 'Record context' : 'No source')}`;
    const sourceList = direct.length ? direct : context;
    const scopeText = direct.length ? (inherited ? 'These links support the model claim this value is inherited from; they were not attached to this configuration directly.' : 'These links were attached to this field in the record.') : context.length ? 'These links belong to the record; none was attached to this field.' : 'No source link is available for this field.';
    const review = candidate ? 'Unreviewed candidate: no review decision accepts this value. It does not share the accepted value\u2019s sources.' : record.demo ? 'Fictional demo value.' : record.record_format ? 'Accepted into the catalogue; acceptance is not independent testing.' : 'Legacy pilot value: not reviewed.';
    return `<details><summary><span class="badge ${candidate ? 'preview' : kind}">${escapeHtml(label)}</span></summary><p>${scopeText}</p>${sourceList.length ? `<ul>${sourceList.map(source => { const url = safeUrl(source.url); return `<li>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label || source.title || new URL(url).host)}</a>` : escapeHtml(source.label || source.title || 'Source')}${source.tier ? ` <span class="source-tier">${escapeHtml(source.tier)}</span>` : ''}</li>`; }).join('')}</ul>` : ''}<p>${review} Field confidence: ${escapeHtml(spec.confidence || 'not rated')}. ${escapeHtml(statusLabel[spec.status] || 'Unknown')}.</p></details>`;
  };
  // Hardware revisions of one model: only what each revision states beyond the model, never implied identical.
  const revisionsMarkup = (category, record, returnQuery = '') => {
    const revisions = Array.isArray(record.revisions) ? record.revisions : [];
    if (!revisions.length) return '';
    const byKey = new Map(category.fields.map(field => [field.key, field]));
    const badge = (entry, spec) => (spec.sources || []).map(id => (entry.sources || []).find(source => source.id === id)).filter(Boolean).map(source => {
      const url = safeUrl(source.url), tier = escapeHtml(source.tier || 'source');
      return url ? `<a class="source-tier" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(source.label || '')}">${tier}</a>` : `<span class="source-tier">${tier}</span>`;
    }).join(' ');
    const rows = revisions.map(entry => {
      const keys = (entry.differs || []).filter(key => Object.hasOwn(entry.specs || {}, key));
      const items = keys.map(key => {
        const field = byKey.get(key) || {key, label:key, type:'string'}, spec = specObject(entry, key), base = specObject(record, key);
        const baseText = base.status === 'known' ? ` <span class="muted">(model: ${displayValue(base, field, true)})</span>` : '';
        return `<li><span class="muted">${escapeHtml(field.label)}:</span> ${displayValue(spec, field, true)}${baseText} ${badge(entry, spec)}</li>`;
      });
      return `<tr><th scope="row"><a href="${productUrl(category.id, entry.id, returnQuery)}">${escapeHtml(entry.label || entry.name)}</a></th><td>${items.length ? `<ul class="revision-diffs">${items.join('')}</ul>` : '<span class="muted">Nothing known beyond the model; hardware may or may not differ.</span>'}</td></tr>`;
    }).join('');
    const extra = revisions.some(entry => (entry.differs || []).some(key => specObject(record, key).status !== 'known' && key !== 'sup.hardware_version'));
    return `<section class="detail-section revisions" id="revisions-section" tabindex="-1"><h2>Hardware revisions</h2><p class="muted">${revisions.length} hardware ${revisions.length === 1 ? 'revision' : 'revisions'} of this model. Each lists only what it states beyond the model.${extra ? ' Specs above are for the default revision where a source shows a single version\u2019s table; revision-specific hardware is listed below.' : ''}</p><div class="table-scroll" role="region" aria-label="Hardware revisions" tabindex="0"><table class="revision-table"><thead><tr><th scope="col">Revision</th><th scope="col">What differs</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
  };
  const TIER_RANK = {core:0, important:1, detail:2};
  const claimSig = spec => JSON.stringify([spec.status, spec.value ?? null, spec.qualifier || null, spec.conditional || null, spec.alternatives || null]);
  // Fields that differ across all schema tiers, buyer-relevant first (core/column, then important, then detail).
  const differingFields = (category, rows) => category.fields
    .filter(field => new Set(rows.map(row => claimSig(specObject(row, field.key)))).size > 1)
    .sort((a, b) => ((TIER_RANK[a.tier] ?? 0) - (TIER_RANK[b.tier] ?? 0)) || (Number(!!b.column) - Number(!!a.column)) || (a.priority - b.priority));
  const SUMMARY = [['cpu.model','CPU'],['mem.size','RAM'],['stor.size','Storage'],['disp.size','Display'],['disp.panel_type','Panel'],['sw.os','OS'],['input.pen','Pen']];
  const textValue = (spec, field) => spec.display ? `${qualifierLabel[spec.qualifier] ? `${qualifierLabel[spec.qualifier]} ` : ''}${spec.display}` : typeof spec.value === 'boolean' ? (spec.value ? 'Yes' : 'No') : `${qualifierLabel[spec.qualifier] ? `${qualifierLabel[spec.qualifier]} ` : ''}${formatRaw(spec.value, field, true)}`;
  // Compact identity summary beside each MTM: known recorded values only, never inferred from the model name.
  const configSummary = (category, row) => {
    let keys = SUMMARY.filter(([key]) => category.fields.some(field => field.key === key));
    if (keys.length < 3) keys = category.fields.filter(field => field.column).slice(0, 5).map(field => [field.key, field.label]);
    return keys.map(([key, label]) => { const field = category.fields.find(item => item.key === key), spec = specObject(row, key); if (!isKnown(spec) || typeof spec.value === 'object') return ''; const text = textValue(spec, field); return `<span title="${escapeHtml(label)}: ${escapeHtml(text)}">${escapeHtml(label)} ${escapeHtml(text.length > 34 ? `${text.slice(0, 32)}…` : text)}</span>`; }).filter(Boolean).join(' · ');
  };
  const configTable = (category, children, fields, selected, query, withSelect, previewState) => `<table><thead><tr>${withSelect ? '<th scope="col">Select</th>' : ''}<th scope="col">${escapeHtml(modelLabel(category))}</th>${fields.map(field => `<th scope="col">${escapeHtml(field.label)}</th>`).join('')}</tr></thead><tbody>${children.map(row => `<tr class="${selected.has(row.id) ? 'selected' : ''}">${withSelect ? `<td class="select-cell"><input type="checkbox" data-config="${escapeHtml(row.id)}" aria-label="Select configuration ${escapeHtml(row.model || row.id)} for comparison" ${selected.has(row.id) ? 'checked' : ''}></td>` : ''}<th scope="row" class="config-id"><a href="${productUrl(category.id, row.id, query)}">${escapeHtml(row.model || row.id)}</a>${row.unreviewed ? ` ${unreviewedBadge}` : ''}<small class="variant-label">${escapeHtml(row.variant_label || '')}</small>${withSelect ? `<small class="config-summary">${configSummary(category, row)}</small>` : ''}</th>${fields.map(field => `<td>${cellValue(category, row, field)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  const revisionSensitive = category => /revision-level|revision/i.test(category.description || '');
  const revisionLine = (category, record) => {
    if (record.kind !== 'model' && !(record.record_format && record.kind === undefined)) return '';
    const count = record.revisions?.length || 0;
    if (count) return `<p class="revision-line"><strong>Hardware revisions: ${count} recorded.</strong> Specifications below describe the default revision unless a revision table says otherwise. <a href="#revisions-section" data-jump="revisions-section">Jump to revisions</a></p>`;
    return revisionSensitive(category) ? '<p class="revision-line"><strong>Hardware revisions: none recorded.</strong> No revision-specific evidence recorded; hardware may or may not differ between revisions.</p>' : '';
  };
  // Bundles (packages): a flat list of what is sold under one SKU. Content entities link to their detail page only when the index has them.
  const contentsMarkup = (category, contents, names, returnQuery) => `<ul class="bundle-contents">${(contents || []).map(item => { const label = item.entity ? (names.get(item.entity) || item.entity) : item.description; const text = names.has(item.entity) ? `<a href="${productUrl(category.id, item.entity, returnQuery)}">${escapeHtml(label)}</a>` : escapeHtml(label); return `<li>${item.qty && item.qty !== 1 ? `${item.qty} × ` : ''}${text}</li>`; }).join('')}</ul>`;
  const entityNames = async (category, wantPreview = false) => { try { return new Map((await indexFor(category, wantPreview)).map(row => [row.id, row.name])); } catch { return new Map(); } };
  const bundlesMarkup = (category, bundles, names, returnQuery) => `<section class="detail-section bundles" id="bundles-section"><h2>Sold as bundles</h2><p class="muted">${bundles.length} ${bundles.length === 1 ? 'bundle includes' : 'bundles include'} this model under ${bundles.length === 1 ? 'its' : 'their'} own SKU. Bundles inherit no specifications.</p><ul class="bundle-list">${bundles.map(bundle => `<li><a href="${productUrl(category.id, bundle.id, returnQuery)}">${escapeHtml(bundle.name)}</a> <span class="code">${escapeHtml(bundle.sku || '')}</span> <span class="muted">· ${bundle.qty && bundle.qty !== 1 ? `${bundle.qty} of this model` : '1 of this model'}</span>${contentsMarkup(category, bundle.contents, names, returnQuery)}</li>`).join('')}</ul></section>`;
  async function renderProduct(category, productId, params, sequence) {
    setLoading('Loading product specifications…');
    const returnQuery = validatedReturnQuery(category, params);
    const backUrl = returnUrl(category, returnQuery);
    let record;
    const wantPreview = params.get('preview') === '1' || new URLSearchParams(params.get('return') || '').get('preview') === '1';
    try { record = await detailFor(category.id, productId, wantPreview && !!category.preview); }
    catch (error) { if (sequence === routeSequence) main.innerHTML = errorPanel('Product not found', `This product record could not be loaded (${error.message}).`, `<a href="${backUrl}">Back to ${escapeHtml(category.name)}</a>`); return; }
    if (sequence !== routeSequence) return;
    setTitle(record.name);
    if (record.kind === 'package') {
      const names = await entityNames(category);
      if (sequence !== routeSequence) return;
      main.innerHTML = `${crumb([{name:category.name,url:backUrl},{name:record.name}])}<div class="page-head"><h1>${escapeHtml(record.name)}</h1><p class="intro">${escapeHtml(record.brand)} · Bundle · SKU <span class="code">${escapeHtml(record.model || '')}</span></p></div><section class="detail-section package-detail"><h2>Contents</h2>${contentsMarkup(category, record.contents, names, returnQuery)}<p class="muted">This bundle inherits no specs; see member models.</p>${record.notes ? `<p class="muted">${escapeHtml(record.notes)}</p>` : ''}</section>`;
      return;
    }
    const groups = [...new Set(category.fields.map(field => field.group))];
    main.innerHTML = `${crumb([{name:category.name,url:backUrl},{name:record.name}])}<div class="page-head"><h1>${escapeHtml(record.name)} ${demoBadge(record)}${record.previewOnly ? ` ${unreviewedBadge}` : ''}</h1><p class="intro">${escapeHtml(record.brand)}${record.family ? ` · ${escapeHtml(record.family)}` : ''}${record.model ? ` · <span class="code">${escapeHtml(record.model)}</span>` : ''}</p><p class="review-line">${record.previewOnly ? unreviewedBadge : record.demo ? '' : record.record_format ? acceptedBadge : '<span class="badge">Legacy pilot record, not reviewed</span>'} <span class="muted">${record.previewOnly ? 'No review decision covers this product yet.' : record.record_format ? 'Reviewed for inclusion from the cited sources; this is not independent testing.' : ''}</span></p>${revisionLine(category, record)}</div>${record.kind === 'model' || record.kind === 'family' ? `<div class="callout">This is a ${record.kind} page, not a purchasable product. Exact specifications belong to a configuration, identified by ${escapeHtml(modelLabel(category))}.</div>` : ''}${record.previewOnly ? '<div class="callout">Unreviewed preview record: no review decision covers this product yet. Every value below is a candidate and may be wrong.</div>' : ''}${record.demo ? '<div class="callout">Fictional demo data. Values and identifiers on this page do not describe a real product.</div>' : ''}<div class="detail-grid"><div class="detail-main"><div class="callout">${escapeHtml(record.identity_caveat || 'Identity has not been independently verified.')}</div>${groups.map((group, groupIndex) => `<section class="detail-section" data-spec-group="${groupIndex}"><h2>${escapeHtml(group)}</h2><div class="table-scroll" role="region" aria-label="${escapeHtml(groupLabel(category, group))} specifications" tabindex="0"><table class="spec-table"><tbody>${category.fields.filter(field => field.group === group).sort((a,b) => a.priority-b.priority).map(field => { const spec = specObject(record, field.key); return `<tr><th scope="row">${escapeHtml(field.label)}</th><td class="value-cell">${displayValue(spec, field)}</td><td class="evidence-cell">${evidenceMarkup(record, spec)}</td></tr>`; }).join('')}</tbody></table></div></section>`).join('')}<section class="detail-section" id="documents-section"><h2>Documents</h2>${record.documents.length ? `<ul class="source-list">${record.documents.map(doc => { const url = safeUrl(doc.url); return `<li>${url ? `<a href="${escapeHtml(url)}">${escapeHtml(doc.label || url)}</a>` : escapeHtml(doc.label || 'Unlinked document')}</li>`; }).join('')}</ul>` : '<p class="muted">No manuals or specification sheets are linked yet.</p>'}</section><section class="detail-section"><h2>Media</h2>${record.media.length ? `<ul class="source-list">${record.media.map(item => { const url = safeUrl(item.url); return `<li>${url ? `<a href="${escapeHtml(url)}">${escapeHtml(item.label || url)}</a>` : escapeHtml(item.label || 'Unlinked media')}</li>`; }).join('')}</ul>` : '<p class="muted">No product images or media are linked yet.</p>'}</section></div><aside class="detail-side"><h2>Record context</h2><dl><dt>Brand</dt><dd>${escapeHtml(record.brand)}</dd><dt>Family hint</dt><dd>${escapeHtml(record.family || 'Not recorded')}</dd><dt>Model hint</dt><dd class="code">${escapeHtml(record.model || 'Not recorded')}</dd><dt>Variant hint</dt><dd>${escapeHtml(record.variant || 'Not resolved')}</dd><dt>Record confidence</dt><dd>${escapeHtml(record.confidence?.level || 'Not rated')} <span class="muted">(${escapeHtml(record.confidence?.scope || 'record')})</span></dd></dl><section class="detail-section"><h2>Identifiers</h2>${record.identifiers.length ? `<ul class="source-list">${record.identifiers.map(id => `<li><span class="code">${escapeHtml(id.value)}</span><br><span class="muted">${escapeHtml(id.scheme)} · ${escapeHtml(id.issuer || 'Issuer unspecified')}${id.market ? ` · ${escapeHtml(id.market)}` : ''} · ${escapeHtml(id.package_level || 'scope unverified')}</span></li>`).join('')}</ul>` : '<p>No identifiers recorded.</p>'}</section><section class="detail-section"><h2>Source links</h2>${record.sources.length ? `<ul class="source-list">${record.sources.map(source => { const url = safeUrl(source.url); return `<li>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label)}</a>` : escapeHtml(source.label)}</li>`; }).join('')}</ul>` : '<p class="muted">No source links; this is demo data.</p>'}</section>${record.marketing_terms.length ? `<section class="detail-section"><h2>Marketing terms</h2><p>${escapeHtml(record.marketing_terms.join(', '))}</p></section>` : ''}<section class="detail-section"><h2>Record notes</h2><p>${escapeHtml(record.notes || 'No notes recorded.')}</p></section></aside></div>`;
    if (record.record_format) {
      const relation = record.relations?.find(link => link.type === 'configuration_of' && link.status === 'approved');
      if (relation) main.querySelector('.detail-grid').insertAdjacentHTML('beforebegin', `<p class="model-link">This is a configuration. <a href="${productUrl(category.id, relation.target, returnQuery)}">View its model and other configurations</a>.</p>`);
      const revisionRelation = record.relations?.find(link => link.type === 'variant_of' && link.status === 'approved');
      if (record.kind === 'revision' && revisionRelation) main.querySelector('.detail-grid').insertAdjacentHTML('beforebegin', `<p class="model-link">This is a hardware revision. Specs not stated for it are inherited from its model. <a href="${productUrl(category.id, revisionRelation.target, returnQuery)}">View the model and all revisions</a>.</p>`);
      if (record.revisions?.length) main.querySelector('.detail-main').insertAdjacentHTML('afterbegin', revisionsMarkup(category, record, returnQuery));
      main.querySelector('[data-jump]')?.addEventListener('click', event => { event.preventDefault(); const target = main.querySelector('#revisions-section'); target?.scrollIntoView(); target?.focus(); });
      if (record.bundles?.length) entityNames(category).then(names => { if (sequence === routeSequence) main.querySelector('.detail-main')?.insertAdjacentHTML('beforeend', bundlesMarkup(category, record.bundles, names, returnQuery)); });
      if (record.options?.length) main.querySelector('.detail-main').insertAdjacentHTML('afterbegin', `<section class="detail-section"><h2>Model options</h2><p class="muted">These are configure-to-order choices, not published configurations.</p><ul>${record.options.map(option => `<li>${escapeHtml(typeof option === 'string' ? option : JSON.stringify(option))}</li>`).join('')}</ul></section>`);
      for (const [index, group] of groups.entries()) {
        const section = main.querySelector(`[data-spec-group="${index}"]`);
        const tbody = section?.querySelector('tbody');
        if (!tbody?.rows) continue;
        const ordered = category.fields.filter(field => field.group === group).sort((a,b) => a.priority-b.priority);
        const hidden = ordered.map((field, i) => field.tier === 'core' ? null : tbody.rows[i]).filter(Boolean);
        if (!hidden.length) continue;
        const details = document.createElement('details');
        details.className = 'tier-details';
        details.innerHTML = `<summary>More ${escapeHtml(groupLabel(category, group))} specifications (${hidden.length})</summary><div class="table-scroll" role="region" aria-label="More ${escapeHtml(groupLabel(category, group))} specifications" tabindex="0"><table class="spec-table"><tbody></tbody></table></div>`;
        hidden.forEach(row => details.querySelector('tbody').append(row));
        section.append(details);
        section.querySelector('h2').textContent = groupLabel(category, group);
      }
      main.querySelectorAll('.spec-table tbody tr').forEach(row => {
        const label = row.querySelector('th')?.textContent;
        const field = category.fields.find(item => item.label === label);
        if (!field) return;
        const spec = specObject(record, field.key);
        const cell = row.querySelector('.value-cell');
        cell.innerHTML = record.previewOnly ? previewMark(valueWithContext(spec, field, record.sources)) : valueWithContext(spec, field, record.sources) + previewOverlay(record, field.key, field);
        row.querySelector('.evidence-cell')?.insertAdjacentHTML('beforeend', `<a class="correction-link" href="${escapeHtml(correctionIssueUrl(record.id, field.key, spec.status === 'known' ? formatRaw(spec.value, field) : statusLabel[spec.status] || 'Unknown'))}" target="_blank" rel="noopener noreferrer">Report a correction</a>`);
      });
      if (record.kind === 'model' && category.index) {
        indexFor(category, wantPreview && !!category.preview).then(rows => {
          if (sequence !== routeSequence) return;
          const children = rows.filter(row => row.kind === 'configuration' && row.parent_id === record.id);
          if (!children.length) return;
          const differing = differingFields(category, children);
          const shown = differing.slice(0, 5), more = differing.slice(5);
          const selected = new Set((params.get('ids') || '').split(',').filter(id => children.some(row => row.id === id)).slice(0, 4));
          const compareReturn = withPreview(category, returnQuery, wantPreview);
          const section = `<section class="detail-section model-configs"><h2>Configurations of this model</h2><p class="muted">${children.length} published configurations, each identified by ${escapeHtml(modelLabel(category))}. This model page is not a purchasable product. ${differing.length ? `${differing.length} recorded specifications differ across configurations${more.length ? `; ${shown.length} are shown and ${more.length} more are under the disclosure below` : ''}.` : 'No difference is recorded among indexed facts; unrecorded fields may still differ.'} Unknown values stay explicit.</p><div id="config-compare" class="config-actions" role="status"></div><div class="table-scroll" role="region" aria-label="Model configurations" tabindex="0">${configTable(category, children, shown, selected, returnQuery, true)}</div>${more.length ? `<details class="tier-details"><summary>${more.length} more differing ${more.length === 1 ? 'specification' : 'specifications'}</summary><div class="table-scroll" role="region" aria-label="More differing specifications" tabindex="0">${configTable(category, children, more, selected, returnQuery, false)}</div></details>` : ''}</section>`;
          main.querySelector('.detail-main')?.insertAdjacentHTML('afterbegin', section);
          const sectionEl = main.querySelector('.model-configs');
          const status = sectionEl.querySelector('#config-compare');
          const paint = () => {
            const ids = [...sectionEl.querySelectorAll('[data-config]:checked')].map(input => input.dataset.config);
            sectionEl.querySelectorAll('[data-config]').forEach(input => { input.disabled = ids.length >= 4 && !input.checked; });
            sectionEl.querySelectorAll('tbody tr').forEach(tr => tr.classList.toggle('selected', !!tr.querySelector('[data-config]:checked')));
            status.innerHTML = `<strong>${ids.length} selected</strong> ${ids.length >= 2 ? `<a class="button-link primary" href="${compareUrl(category.id, ids, false, compareReturn, {model:record.id})}">Compare selected configurations</a>` : '<small>Select 2 to 4 configurations to compare.</small>'}${ids.length >= 4 ? ' <small>Maximum of 4.</small>' : ''}`;
            history.replaceState(null, '', productUrl(category.id, record.id, returnQuery, ids));
          };
          sectionEl.addEventListener('change', event => { if (event.target.closest('[data-config]')) paint(); });
          paint();
        }).catch(() => { /* Product specifications remain usable if the listing cannot load. */ });
      }
    }
  }

  const evidenceSig = (record, spec) => JSON.stringify([[...(spec.sources || [])].map(id => record.sources?.find(source => source.id === id)?.url || id).sort(), spec.confidence || null, spec.kind || null]);
  async function renderCompare(category, params, sequence) {
    const ids = [...new Set((params.get('ids') || '').split(',').filter(Boolean))];
    const returnQuery = validatedReturnQuery(category, params);
    const modelId = params.get('model') || '';
    const backUrl = returnUrl(category, returnQuery);
    if (ids.length < 2 || ids.length > 4) { main.innerHTML = errorPanel('Choose 2–4 products', 'Select products from one category before opening comparison.', `<a href="${backUrl}">Browse ${escapeHtml(category.name)}</a>`); return; }
    setLoading('Loading comparison…');
    let records;
    const wantPreview = params.get('preview') === '1' || new URLSearchParams(params.get('return') || '').get('preview') === '1';
    try { records = await Promise.all(ids.map(id => detailFor(category.id, id, wantPreview && !!category.preview))); }
    catch (error) { if (sequence === routeSequence) main.innerHTML = errorPanel('Comparison unavailable', `One or more products could not be loaded (${error.message}).`, `<a href="${backUrl}">Back to ${escapeHtml(category.name)}</a>`); return; }
    if (sequence !== routeSequence) return;
    if (records.some(record => record.category !== category.id)) { main.innerHTML = errorPanel('Mixed categories', 'All compared products must belong to the same category.', `<a href="${backUrl}">Back to ${escapeHtml(category.name)}</a>`); return; }
    setTitle(`Compare ${category.name}`);
    let differencesOnly = params.get('diff') === '1';
    let showDetails = params.get('detail') === '1';
    const groupedFields = [...new Set(category.fields.map(field => field.group))];
    const modelUrl = modelId ? productUrl(category.id, modelId, withPreview(category, returnQuery, wantPreview), ids) : '';
    const persist = () => history.replaceState(null, '', compareUrl(category.id, ids, differencesOnly, returnQuery, {detail:showDetails, model:modelId}));
    main.innerHTML = `${crumb([{name:category.name,url:backUrl},{name:'Compare'}])}<div class="page-head"><h1>Compare ${category.name.toLowerCase()} ${demoBadge(category)}</h1><p class="intro">Read differences side by side. Unknown and conflicted values remain separate from “No”. ${escapeHtml(reviewNote(category))} Rows are marked when claims differ; a row can also differ only in evidence or in unreviewed candidates.</p></div><div class="compare-toolbar"><label><input type="checkbox" id="differences-only" ${differencesOnly ? 'checked' : ''}>Show differences only</label><label><input type="checkbox" id="show-details" ${showDetails ? 'checked' : ''}>Show important and detailed specifications</label>${modelUrl ? `<a href="${modelUrl}">Back to model configurations</a>` : ''}<a href="${returnUrl(category, returnWithIds(category, returnQuery, ids))}">Back to products</a></div><div id="comparison-table"></div>`;
    const target = main.querySelector('#comparison-table');
    const renderRows = () => {
      let rowCount = 0, evidenceOnly = 0, hiddenDetail = 0;
      const body = groupedFields.map(group => {
        const items = category.fields.filter(field => field.group === group).sort((a,b) => a.priority-b.priority).map(field => {
          const inScope = showDetails || !field.tier || field.tier === 'core';
          const cells = records.map(record => specObject(record, field.key));
          const claims = cells.map(claimSig);
          const claimDiff = claims.some(signature => signature !== claims[0]);
          if (!inScope) { if (claimDiff) hiddenDetail++; return ''; }
          const evidence = cells.map((spec, index) => evidenceSig(records[index], spec));
          const evidenceDiff = !claimDiff && evidence.some(signature => signature !== evidence[0]);
          const effective = records.map((record, index) => { const candidate = record.previewSpecs?.[field.key]; return candidate && !record.previewOnly && candidate.status === 'known' ? claimSig(candidate) : claims[index]; });
          const candidateDiff = !claimDiff && effective.some(signature => signature !== effective[0]);
          if (differencesOnly && !claimDiff && !candidateDiff) { if (evidenceDiff) evidenceOnly++; return ''; }
          rowCount++;
          const flag = claimDiff ? ' <span class="diff-flag">Claims differ</span>' : candidateDiff ? ' <span class="diff-flag candidate">Unreviewed candidates differ</span>' : evidenceDiff ? ' <span class="diff-flag evidence">Same value, different evidence</span>' : '';
          const methods = methodsDiffer(cells, field) ? methodsFlag(cells, field) : '';
          return `<tr class="${claimDiff ? 'different' : candidateDiff ? 'candidate-different' : evidenceDiff ? 'evidence-different' : ''}"><th scope="row">${escapeHtml(field.label)}${flag}</th>${cells.map((spec, index) => `<td>${records[index].previewOnly ? previewMark(valueWithContext(spec, field, records[index].sources)) : valueWithContext(spec, field, records[index].sources) + previewOverlay(records[index], field.key, field)}${methods && isKnown(spec) ? ` ${methods}` : ''}<div class="evidence-cell">${evidenceMarkup(records[index], spec)}</div></td>`).join('')}</tr>`;
        }).filter(Boolean).join('');
        return items ? `<tr class="group-row"><th colspan="${records.length + 1}" scope="colgroup">${escapeHtml(groupLabel(category,group))}</th></tr>${items}` : '';
      }).join('');
      const hiddenNote = hiddenDetail ? ` ${hiddenDetail} more differing ${hiddenDetail === 1 ? 'specification is' : 'specifications are'} in important or detailed tiers and not shown. <button type="button" data-show-details>Show them</button>` : '';
      const evidenceNote = evidenceOnly ? ` ${evidenceOnly} ${evidenceOnly === 1 ? 'row differs' : 'rows differ'} only in evidence; they are not hardware differences and appear in the full view.` : '';
      target.innerHTML = `<div class="table-scroll" role="region" aria-label="Side-by-side product comparison" tabindex="0"><table class="compare-table"><thead><tr><th scope="col">Specification</th>${records.map(record => `<th scope="col"><a href="${productUrl(category.id, record.id, returnWithIds(category, returnQuery, ids))}">${escapeHtml(record.name)}</a> ${demoBadge(record)}${record.previewOnly ? ` ${unreviewedBadge}` : ''}<div class="muted code">${escapeHtml(record.model || '')}</div><button type="button" class="remove" data-remove="${escapeHtml(record.id)}">Remove</button></th>`).join('')}</tr></thead><tbody>${body || `<tr><td colspan="${records.length + 1}" class="empty-table">No differences among displayed fields.${hiddenNote}${evidenceNote}</td></tr>`}</tbody></table></div><p class="muted compare-summary">${rowCount} ${differencesOnly ? 'different' : 'total'} specification rows shown. Tinted rows contain a recorded claim difference.${body ? hiddenNote + evidenceNote : ''}</p>`;
    };
    main.querySelector('#differences-only').addEventListener('change', event => { differencesOnly = event.target.checked; persist(); renderRows(); });
    main.querySelector('#show-details').addEventListener('change', event => { showDetails = event.target.checked; persist(); renderRows(); });
    target.addEventListener('click', event => {
      if (event.target.closest('[data-show-details]')) { showDetails = true; main.querySelector('#show-details').checked = true; persist(); renderRows(); return; }
      const button = event.target.closest('[data-remove]');
      if (!button) return;
      const remaining = ids.filter(id => id !== button.dataset.remove);
      const nextQuery = returnWithIds(category, returnQuery, remaining);
      location.hash = remaining.length >= 2 ? compareUrl(category.id, remaining, differencesOnly, nextQuery, {detail:showDetails, model:modelId}).slice(1) : returnUrl(category, nextQuery).slice(1);
    });
    persist();
    renderRows();
  }

  window.addEventListener('hashchange', renderRoute);
  window.addEventListener('popstate', renderRoute);
  renderRoute();
})();

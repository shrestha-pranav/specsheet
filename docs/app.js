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
  const productUrl = (category, id, query = '') => `#/product/${encoded(category)}/${encoded(id)}${query ? `?return=${encoded(query)}` : ''}`;
  const compareUrl = (category, ids, differences = false, query = '') => `#/compare/${encoded(category)}?ids=${encoded(ids.join(','))}${differences ? '&diff=1' : ''}${returnParam(query)}`;
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
  // Trusted rows only, unless the reader opted in to the unreviewed preview index (superset: every trusted row plus preview-only rows).
  const indexFor = (category, preview = false) => {
    const wantPreview = preview && !!category.preview?.index;
    const key = wantPreview ? `${category.id}:preview` : category.id;
    if (!indexCache.has(key)) indexCache.set(key, (async () => {
      if (!category.index) return getJson(`api/v1/${category.products}`);
      // Revision rows (opt-in per category) are children of their model, never separate products in counts or listings.
      const trusted = (await loadShards(category.index)).map(toRow).filter(row => row.kind !== 'revision');
      if (!wantPreview) return trusted;
      const known = new Map(trusted.map(row => [row.id, row]));
      return (await loadShards(category.preview.index)).map(toRow).filter(row => row.kind !== 'revision').map(row => {
        const base = known.get(row.id);
        row.unreviewed = !base;
        row.unreviewedKeys = new Set(Object.keys(row.specs).filter(k => row.specs[k].status === 'known' && (!base || JSON.stringify(base.specs[k]?.value) !== JSON.stringify(row.specs[k].value))));
        return row;
      });
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
      return detailCache.get(key).then(trusted => ({...trusted, previewSpecs:delta?.specs || null}));
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
  const unreviewedBadge = '<span class="badge preview" title="Not yet accepted by a recorded review decision">Unreviewed</span>';
  const previewMark = (html) => `<span class="val-preview" title="Unreviewed preview value">${html}</span>`;
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
    if (typeof value === 'number') return `${value}${field?.unit ? ` ${field.unit}` : ''}`;
    return String(value);
  };
  const valueWithContext = (spec, field) => {
    const extra = [];
    if (spec.inherited_from) extra.push(`<small class="value-note">From model ${escapeHtml(typeof spec.inherited_from === 'string' ? spec.inherited_from : spec.inherited_from.id || spec.inherited_from.name || JSON.stringify(spec.inherited_from))}</small>`);
    if (spec.conditional?.length) extra.push(`<div class="value-details"><strong>Conditions</strong><ul>${spec.conditional.map(item => `<li>${escapeHtml(formatRaw(item.conditions, field))}: ${displayStructured(item.value,field) ?? escapeHtml(formatRaw(item.value,field))}</li>`).join('')}</ul></div>`);
    if (spec.alternatives?.length) extra.push(`<div class="value-details"><strong>Reported alternatives</strong><ul>${spec.alternatives.map(item => `<li>${escapeHtml(item.kind || 'Reported')}: ${displayStructured(item.value,field) ?? escapeHtml(formatRaw(item.value,field))}</li>`).join('')}</ul></div>`);
    return displayValue(spec, field) + extra.join('');
  };
  // Opt-in preview overlay on a detail page: the unreviewed value always sits below, never replaces, the trusted one.
  const previewOverlay = (record, key, field) => {
    const delta = record.previewSpecs?.[key];
    if (!delta || record.previewOnly || (JSON.stringify([delta.value, delta.display, delta.qualifier]) === JSON.stringify([record.specs?.[key]?.value, record.specs?.[key]?.display, record.specs?.[key]?.qualifier]) && delta.status === record.specs?.[key]?.status)) return '';
    return `<div class="value-details preview-note">${unreviewedBadge} ${displayValue(delta, field)}</div>`;
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
    main.innerHTML = `<section class="lead-panel"><h1>Product specifications, with context.</h1><p>Search across brands, inspect the exact variant, and see where each recorded fact came from. Start with a category.</p></section><section aria-labelledby="cat-heading"><h2 id="cat-heading">Browse categories</h2><div class="category-list">${all.map(category => `<a class="category-row" href="${categoryUrl(category.id)}"><span><strong>${escapeHtml(category.name)}</strong> ${demoBadge(category)}<p>${escapeHtml(category.description)}</p></span><span class="count-pill">${category.count} ${category.count === 1 ? 'product' : 'products'} →</span></a>`).join('')}</div></section><p class="muted" style="margin-top:25px;max-width:72ch">These published records are still under review. Open a product to inspect its sources and uncertainty.</p>`;
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
      preview: params.get('preview') === '1' && !!category.preview, cols, ids, page:Math.max(1, Number.parseInt(params.get('page') || '1', 10) || 1)};
  }
  function categoryStateQuery(state) {
    const params = new URLSearchParams();
    if (state.q) params.set('q', state.q);
    if (state.brand) params.set('brand', state.brand);
    for (const [key, value] of Object.entries(state.filters)) if (value) params.set(key, value);
    if (state.preview) params.set('preview', '1');
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
  const returnWithIds = (category, query, ids) => { const state = initialState(category, new URLSearchParams(query)); state.ids = ids; return categoryStateQuery(state); };
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
      return `<div class="filter-field"><label for="facet-${field.key}">${label}</label><select id="facet-${field.key}" data-filter="${key}"><option value="">Any</option>${options.map(option => `<option value="${escapeHtml(option)}" ${option === state.filters[key] ? 'selected' : ''}>${escapeHtml(option)}</option>`).join('')}<option value="__unknown" ${value === '__unknown' ? 'selected' : ''}>Unknown</option></select></div>`;
    }
    return `<div class="filter-field"><label for="facet-${field.key}">${label}</label><input id="facet-${field.key}" type="search" data-filter="${key}" value="${value}" placeholder="Contains…"></div>`;
  };
  const previewControl = (category, state) => category.preview ? `<div class="preview-toggle"><label><input type="checkbox" id="preview-toggle" ${state.preview ? 'checked' : ''}>Include unreviewed (preview)</label><p>${state.preview ? `Showing ${category.preview.count} products; ${category.preview.only_preview} exist only as unreviewed preview rows and are marked.` : `${category.preview.only_preview ? `Adds ${category.preview.only_preview} products from brands without a review decision yet<span id="preview-brands"></span>.` : 'Adds no new products; it only shows unreviewed values for products already listed.'}`} Unreviewed values never replace reviewed ones.</p></div>` : '';
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
    if (field.type === 'enum') return spec.value === query;
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

  async function renderCategory(category, params, sequence) {
    setLoading(`Loading ${category.name}…`);
    const state = initialState(category, params);
    const rows = await indexFor(category, state.preview);
    if (sequence !== routeSequence) return;
    setTitle(category.name);
    state.ids = state.ids.filter(id => rows.some(row => row.id === id));
    main.innerHTML = `${crumb([{name:category.name}])}<div class="page-head"><h1>${escapeHtml(category.name)} ${demoBadge(category)}</h1><p class="intro">${escapeHtml(category.description)} ${category.demo ? 'These fictional records test the interface and are not product recommendations.' : 'Published records are under review; open a product to inspect evidence and uncertainty.'}</p></div><div class="catalogue-layout"><aside class="filter-rail"><details open><summary>Filters</summary>${previewControl(category, state)}${filterMarkup(category, rows, state)}</details></aside><section class="catalogue-results" aria-label="Products"><div class="results-head"><label class="search-field" for="product-search">Search name, brand or identifier<input id="product-search" type="search" placeholder="Search products…" value="${escapeHtml(state.q)}" autocomplete="off"></label><div><h2>Compare the facts</h2><p>Choose 2–4 products to compare.</p></div></div><div class="results-tools"><span class="meta" id="result-count" role="status"></span><label class="sort-control">Sort <select id="sort-select" aria-label="Sort products"><option value="coverage">Most complete first</option><option value="brand">Brand</option><option value="name">Product name</option><option value="model">Model</option><option value="__column" disabled>Column (use header)</option></select></label><details class="column-menu"><summary>Choose columns</summary><div class="column-options"><button type="button" id="reset-columns">Reset to default columns</button>${[...new Set(category.fields.map(field => field.group))].map(group => `<fieldset><legend>${escapeHtml(groupLabel(category,group))}</legend>${category.fields.filter(field => field.group === group).map(field => `<label><input type="checkbox" data-column="${escapeHtml(field.key)}" ${state.cols.includes(field.key) ? 'checked' : ''}>${escapeHtml(field.label)}</label>`).join('')}</fieldset>`).join('')}</div></details></div><p class="request-prompt">Product missing? <a id="request-product" href="${escapeHtml(missingIssueUrl(category.id, state.q))}" target="_blank" rel="noopener noreferrer">Request a product</a>. A GitHub issue opens only if you choose this link.</p><div id="selection-status" class="visually-hidden" role="status" aria-live="polite" aria-atomic="true"></div><div id="compare-shelf"></div><div id="results-table"></div><div id="pagination"></div></section></div>`;
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
      state.preview = event.target.checked; state.page = 1; state.ids = [];
      persistCategoryState(category, state);
      renderCategory(category, new URLSearchParams(categoryStateQuery(state)), sequence).then(() => main.querySelector('#preview-toggle')?.focus());
    });
    const sortSelect = main.querySelector('#sort-select');
    sortSelect.addEventListener('change', () => { state.sort = sortSelect.value; state.dir = state.sort === 'coverage' ? 'desc' : 'asc'; update(); });
    search.addEventListener('input', () => { state.q = search.value; state.page = 1; update(); });
    main.querySelector('#brand-filter').addEventListener('change', event => { state.brand = event.target.value; state.page = 1; update(); });
    main.querySelectorAll('[data-filter]').forEach(control => control.addEventListener(control.tagName === 'SELECT' ? 'change' : 'input', () => { state.filters[control.dataset.filter] = control.value; state.page = 1; update(); }));
    main.querySelector('#clear-filters').addEventListener('click', () => {
      state.q = ''; state.brand = ''; state.filters = {};
      search.value = ''; main.querySelector('#brand-filter').value = '';
      main.querySelectorAll('[data-filter]').forEach(control => { control.value = ''; });
      state.page = 1; update(); search.focus();
    });
    main.querySelectorAll('[data-column]').forEach(control => control.addEventListener('change', () => {
      state.cols = [...main.querySelectorAll('[data-column]:checked')].map(input => input.dataset.column);
      update();
    }));
    main.querySelector('#reset-columns').addEventListener('click', () => { state.cols = category.fields.filter(field => field.column).map(field => field.key); main.querySelectorAll('[data-column]').forEach(control => { control.checked = state.cols.includes(control.dataset.column); }); update(); });
    main.querySelector('#pagination').addEventListener('click', event => { const button = event.target.closest('[data-page]'); if (!button) return; state.page = Number(button.dataset.page); update(); main.querySelector('#result-count').scrollIntoView({block:'start'}); });
    main.querySelector('#results-table').addEventListener('click', event => {
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
    function update() {
      const active = document.activeElement;
      const focus = active?.closest('#results-table') ? {kind: active.dataset.select ? 'select' : 'sort', value: active.dataset.select || active.dataset.sort} :
        active?.closest('#compare-shelf') ? {kind:'shelf', value:active.dataset.remove} : null;
      const q = state.q.trim().toLocaleLowerCase();
      const filtered = rows.filter(row => (!q || [row.name, row.brand, row.family, row.model, row.variant_label, ...(row.search || []), ...(row.identifiers || []).map(id => id.value)].some(value => String(value || '').toLocaleLowerCase().includes(q))) && (!state.brand || row.brand === state.brand) && category.fields.filter(f => f.facet).every(field => matchFacet(row, field, state.filters))).sort((a, b) => compareSort(a, b, state));
      sortSelect.value = [...sortSelect.options].some(o => o.value === state.sort && !o.disabled) ? state.sort : '__column';
      main.querySelector('#result-count').textContent = `${filtered.length} of ${rows.length} products${state.preview ? ' (includes unreviewed preview)' : ''}`;
      main.querySelector('#request-product').href = missingIssueUrl(category.id, state.q);
      const pages = Math.max(1, Math.ceil(filtered.length / 50));
      state.page = Math.min(state.page, pages);
      const query = categoryStateQuery(state);
      renderTable(category, filtered.slice((state.page - 1) * 50, state.page * 50), state, query);
      main.querySelector('#pagination').innerHTML = pages > 1 ? `<nav class="pagination" aria-label="Result pages"><button type="button" data-page="${state.page - 1}" ${state.page === 1 ? 'disabled' : ''}>Previous</button><span>Page ${state.page} of ${pages}</span><button type="button" data-page="${state.page + 1}" ${state.page === pages ? 'disabled' : ''}>Next</button></nav>` : '';
      renderShelf(category, rows, state, query);
      main.querySelector('#selection-status').textContent = `${state.ids.length} selected. ${state.ids.length >= 4 ? 'Maximum of 4; remove one to add another.' : state.ids.length >= 2 ? 'Compare products available.' : 'Choose 2 to 4 products to compare.'}`;
      persistCategoryState(category, state);
      if (focus?.kind === 'select') [...main.querySelectorAll('[data-select]')].find(input => input.dataset.select === focus.value)?.focus();
      if (focus?.kind === 'sort') [...main.querySelectorAll('[data-sort]')].find(button => button.dataset.sort === focus.value)?.focus();
      if (focus?.kind === 'shelf') ([...main.querySelectorAll('#compare-shelf [data-remove]')].find(button => button.dataset.remove === focus.value) || main.querySelector('#compare-shelf [data-remove]') || search).focus();
    }
    update();
  }

  // Table cell: unit-display hints and qualifiers via displayValue; CPU model gets a muted cores/threads line; unreviewed values are muted.
  function cellValue(category, row, field) {
    let html = displayValue(specObject(row, field.key), field, true);
    if (field.key === 'cpu.model' && isKnown(specObject(row, field.key))) {
      const cores = specObject(row, 'cpu.cores'), threads = specObject(row, 'cpu.threads');
      const note = [isKnown(cores) ? `${cores.value}C` : '', isKnown(threads) ? `${threads.value}T` : ''].filter(Boolean).join(' / ');
      if (note) html += `<small class="value-note">${escapeHtml(note)}</small>`;
    }
    return row.unreviewedKeys?.has(field.key) ? previewMark(html) : html;
  }
  function renderTable(category, rows, state, query) {
    const fields = state.cols.map(key => category.fields.find(field => field.key === key)).filter(Boolean);
    const columnHeader = (key, label) => `<th scope="col" aria-sort="${state.sort === key ? (state.dir === 'asc' ? 'ascending' : 'descending') : 'none'}"><button type="button" data-sort="${escapeHtml(key)}">${escapeHtml(label)} ${state.sort === key ? (state.dir === 'asc' ? '↑' : '↓') : ''}</button></th>`;
    const target = main.querySelector('#results-table');
    if (!rows.length) {
      const q = state.q.trim();
      target.innerHTML = `<div class="empty-table"><strong>No matching products</strong><p>${q ? 'Not in the catalogue yet. Request it, or try a broader search.' : 'Try a broader search or reset the filters.'}</p>${q ? `<a class="button-link" href="${escapeHtml(missingIssueUrl(category.id, q))}" target="_blank" rel="noopener noreferrer">Request “${escapeHtml(q)}” on GitHub</a>` : ''}</div>`;
      return;
    }
    const groupCounts = new Map();
    for (const row of rows) if (row.kind === 'configuration' && row.parent_id) groupCounts.set(row.parent_id, (groupCounts.get(row.parent_id) || 0) + 1);
    let lastGroup = '';
    const body = rows.map(row => {
      const group = row.kind === 'configuration' && groupCounts.get(row.parent_id) > 1 ? row.parent_id : '';
      const groupHeader = group && group !== lastGroup ? `<tr class="model-group"><th colspan="${fields.length + 4}" scope="rowgroup">Configurations linked to <a href="${productUrl(category.id, group, query)}">${escapeHtml(row.name)}</a> <span class="muted">(${groupCounts.get(group)} on this page)</span></th></tr>` : '';
      lastGroup = group;
      return `${groupHeader}<tr class="${state.ids.includes(row.id) ? 'selected' : ''}${row.unreviewed ? ' unreviewed' : ''}"><td class="select-cell"><input type="checkbox" data-select="${escapeHtml(row.id)}" aria-label="Select ${escapeHtml(row.name)} ${escapeHtml(row.model || '')} for comparison" ${state.ids.includes(row.id) ? 'checked' : ''} ${state.ids.length >= 4 && !state.ids.includes(row.id) ? 'disabled' : ''}></td><td>${escapeHtml(row.brand)}</td><td class="name-cell"><a href="${productUrl(category.id, row.id, query)}">${escapeHtml(row.name)}</a> ${demoBadge(row)}${row.unreviewed ? ` ${unreviewedBadge}` : ''}${row.variant_label ? `<small class="variant-label">${escapeHtml(row.variant_label)}</small>` : ''}${row.kind ? `<small class="entity-kind">${escapeHtml(row.kind[0].toUpperCase() + row.kind.slice(1))}</small>` : ''}</td><td class="code">${escapeHtml(row.model || '—')}</td>${fields.map(f => `<td class="${['number','integer'].includes(f.type) ? 'num' : ''}">${cellValue(category, row, f)}</td>`).join('')}</tr>`;
    }).join('');
    target.innerHTML = `<div class="table-scroll" role="region" aria-label="Product comparison table" tabindex="0"><table><thead><tr><th scope="col">Select</th>${columnHeader('brand','Brand')}${columnHeader('name','Product')}${columnHeader('model','Model')}${fields.map(f => columnHeader(f.key, f.label)).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
  }
  function renderShelf(category, rows, state, query) {
    const target = main.querySelector('#compare-shelf');
    if (!state.ids.length) { target.innerHTML = ''; return; }
    const chosen = selectedRows(rows, state);
    target.innerHTML = `<div class="compare-shelf"><strong>${chosen.length} selected</strong><div class="selected-items">${chosen.map(row => `<button type="button" data-remove="${escapeHtml(row.id)}" aria-label="Remove ${escapeHtml(row.name)}">${escapeHtml(row.brand)} ${escapeHtml(row.model || row.name)} ×</button>`).join('')}</div>${chosen.length >= 2 ? `<a class="button-link primary" href="${compareUrl(category.id, state.ids, false, query)}">Compare products</a>` : '<small>Select at least one more product.</small>'}</div>`;
  }

  const evidenceMarkup = (record, spec) => {
    const direct = (spec.sources || []).map(id => record.sources.find(source => source.id === id)).filter(Boolean);
    const context = direct.length ? [] : (record.record_format ? [] : record.sources);
    const kind = direct.length ? 'direct' : (spec.status === 'conflicted' ? 'warning' : '');
    const label = direct.length ? `${direct.length} field ${direct.length === 1 ? 'source' : 'sources'}` : (context.length ? 'Record context' : 'No source');
    const sourceList = direct.length ? direct : context;
    const scopeText = direct.length ? 'These links were attached to this field in the pilot record.' : context.length ? 'These links belong to the record; none was attached to this field.' : 'No source link is available for this field.';
    return `<details><summary><span class="badge ${kind}">${label}</span></summary><p>${scopeText}</p>${sourceList.length ? `<ul>${sourceList.map(source => { const url = safeUrl(source.url); return `<li>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label || source.title || new URL(url).host)}</a>` : escapeHtml(source.label || source.title || 'Source')}${source.tier ? ` <span class="source-tier">${escapeHtml(source.tier)}</span>` : ''}</li>`; }).join('')}</ul>` : ''}<p>Field confidence: ${escapeHtml(spec.confidence || 'not rated')}. ${escapeHtml(statusLabel[spec.status] || 'Unknown')}.</p></details>`;
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
    return `<section class="detail-section revisions"><h2>Hardware revisions</h2><p class="muted">${revisions.length} hardware ${revisions.length === 1 ? 'revision' : 'revisions'} of this model. Each lists only what it states beyond the model.${extra ? ' Specs above are for the default revision where a source shows a single version\u2019s table; revision-specific hardware is listed below.' : ''}</p><div class="table-scroll" role="region" aria-label="Hardware revisions" tabindex="0"><table class="revision-table"><thead><tr><th scope="col">Revision</th><th scope="col">What differs</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
  };
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
    const groups = [...new Set(category.fields.map(field => field.group))];
    main.innerHTML = `${crumb([{name:category.name,url:backUrl},{name:record.name}])}<div class="page-head"><h1>${escapeHtml(record.name)} ${demoBadge(record)}${record.previewOnly ? ` ${unreviewedBadge}` : ''}</h1><p class="intro">${escapeHtml(record.brand)}${record.family ? ` · ${escapeHtml(record.family)}` : ''}${record.model ? ` · <span class="code">${escapeHtml(record.model)}</span>` : ''}</p></div>${record.previewOnly ? '<div class="callout">Unreviewed preview record: no review decision covers this product yet. Every value below is a candidate and may be wrong.</div>' : ''}${record.demo ? '<div class="callout">Fictional demo data. Values and identifiers on this page do not describe a real product.</div>' : ''}<div class="detail-grid"><div class="detail-main"><div class="callout">${escapeHtml(record.identity_caveat || 'Identity has not been independently verified.')}</div>${groups.map(group => `<section class="detail-section"><h2>${escapeHtml(group)}</h2><div class="table-scroll"><table class="spec-table"><tbody>${category.fields.filter(field => field.group === group).sort((a,b) => a.priority-b.priority).map(field => { const spec = specObject(record, field.key); return `<tr><th scope="row">${escapeHtml(field.label)}</th><td class="value-cell">${displayValue(spec, field)}</td><td class="evidence-cell">${evidenceMarkup(record, spec)}</td></tr>`; }).join('')}</tbody></table></div></section>`).join('')}<section class="detail-section" id="documents-section"><h2>Documents</h2>${record.documents.length ? `<ul class="source-list">${record.documents.map(doc => { const url = safeUrl(doc.url); return `<li>${url ? `<a href="${escapeHtml(url)}">${escapeHtml(doc.label || url)}</a>` : escapeHtml(doc.label || 'Unlinked document')}</li>`; }).join('')}</ul>` : '<p class="muted">No manuals or specification sheets are linked yet.</p>'}</section><section class="detail-section"><h2>Media</h2>${record.media.length ? `<ul class="source-list">${record.media.map(item => { const url = safeUrl(item.url); return `<li>${url ? `<a href="${escapeHtml(url)}">${escapeHtml(item.label || url)}</a>` : escapeHtml(item.label || 'Unlinked media')}</li>`; }).join('')}</ul>` : '<p class="muted">No product images or media are linked yet.</p>'}</section></div><aside class="detail-side"><h2>Record context</h2><dl><dt>Brand</dt><dd>${escapeHtml(record.brand)}</dd><dt>Family hint</dt><dd>${escapeHtml(record.family || 'Not recorded')}</dd><dt>Model hint</dt><dd class="code">${escapeHtml(record.model || 'Not recorded')}</dd><dt>Variant hint</dt><dd>${escapeHtml(record.variant || 'Not resolved')}</dd><dt>Record confidence</dt><dd>${escapeHtml(record.confidence?.level || 'Not rated')} <span class="muted">(${escapeHtml(record.confidence?.scope || 'record')})</span></dd></dl><section class="detail-section"><h2>Identifiers</h2>${record.identifiers.length ? `<ul class="source-list">${record.identifiers.map(id => `<li><span class="code">${escapeHtml(id.value)}</span><br><span class="muted">${escapeHtml(id.scheme)} · ${escapeHtml(id.issuer || 'Issuer unspecified')}${id.market ? ` · ${escapeHtml(id.market)}` : ''} · ${escapeHtml(id.package_level || 'scope unverified')}</span></li>`).join('')}</ul>` : '<p>No identifiers recorded.</p>'}</section><section class="detail-section"><h2>Source links</h2>${record.sources.length ? `<ul class="source-list">${record.sources.map(source => { const url = safeUrl(source.url); return `<li>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label)}</a>` : escapeHtml(source.label)}</li>`; }).join('')}</ul>` : '<p class="muted">No source links; this is demo data.</p>'}</section>${record.marketing_terms.length ? `<section class="detail-section"><h2>Marketing terms</h2><p>${escapeHtml(record.marketing_terms.join(', '))}</p></section>` : ''}<section class="detail-section"><h2>Record notes</h2><p>${escapeHtml(record.notes || 'No notes recorded.')}</p></section></aside></div>`;
    if (record.record_format) {
      const relation = record.relations?.find(link => link.type === 'configuration_of' && link.status === 'approved');
      if (relation) main.querySelector('.detail-grid').insertAdjacentHTML('beforebegin', `<p class="model-link">This is a configuration. <a href="${productUrl(category.id, relation.target, returnQuery)}">View its model and other configurations</a>.</p>`);
      const revisionRelation = record.relations?.find(link => link.type === 'variant_of' && link.status === 'approved');
      if (record.kind === 'revision' && revisionRelation) main.querySelector('.detail-grid').insertAdjacentHTML('beforebegin', `<p class="model-link">This is a hardware revision. Specs not stated for it are inherited from its model. <a href="${productUrl(category.id, revisionRelation.target, returnQuery)}">View the model and all revisions</a>.</p>`);
      if (record.revisions?.length) main.querySelector('#documents-section')?.insertAdjacentHTML('beforebegin', revisionsMarkup(category, record, returnQuery));
      if (record.options?.length) main.querySelector('.detail-main').insertAdjacentHTML('afterbegin', `<section class="detail-section"><h2>Model options</h2><p class="muted">These are configure-to-order choices, not published configurations.</p><ul>${record.options.map(option => `<li>${escapeHtml(typeof option === 'string' ? option : JSON.stringify(option))}</li>`).join('')}</ul></section>`);
      for (const [index, group] of groups.entries()) {
        const section = main.querySelectorAll('.detail-main > .detail-section')[index + (record.options?.length ? 1 : 0)];
        const tbody = section?.querySelector('tbody');
        if (!tbody) continue;
        const ordered = category.fields.filter(field => field.group === group).sort((a,b) => a.priority-b.priority);
        const hidden = ordered.map((field, i) => field.tier === 'core' ? null : tbody.rows[i]).filter(Boolean);
        if (!hidden.length) continue;
        const details = document.createElement('details');
        details.className = 'tier-details';
        details.innerHTML = `<summary>More ${escapeHtml(groupLabel(category, group))} specifications (${hidden.length})</summary><div class="table-scroll"><table class="spec-table"><tbody></tbody></table></div>`;
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
        cell.innerHTML = record.previewOnly ? previewMark(valueWithContext(spec, field)) : valueWithContext(spec, field) + previewOverlay(record, field.key, field);
        row.querySelector('.evidence-cell')?.insertAdjacentHTML('beforeend', `<a class="correction-link" href="${escapeHtml(correctionIssueUrl(record.id, field.key, spec.status === 'known' ? formatRaw(spec.value, field) : statusLabel[spec.status] || 'Unknown'))}" target="_blank" rel="noopener noreferrer">Report a correction</a>`);
      });
      if (record.kind === 'model' && category.index) {
        indexFor(category).then(rows => {
          if (sequence !== routeSequence) return;
          const children = rows.filter(row => row.kind === 'configuration' && row.parent_id === record.id);
          if (!children.length) return;
          const varying = category.fields.filter(field => field.column || field.tier === 'core').filter(field => new Set(children.map(row => JSON.stringify([specObject(row,field.key).status,specObject(row,field.key).value]))).size > 1).slice(0,8);
          const section = `<section class="detail-section model-configs"><h2>Configurations of this model</h2><p class="muted">${children.length} published configurations. Columns show recorded differences; unknown values stay explicit.</p><div class="table-scroll" role="region" aria-label="Model configurations" tabindex="0"><table><thead><tr><th scope="col">Configuration</th>${varying.map(field => `<th scope="col">${escapeHtml(field.label)}</th>`).join('')}</tr></thead><tbody>${children.map(row => `<tr><th scope="row"><a href="${productUrl(category.id,row.id,returnQuery)}">${escapeHtml(row.model || row.id)}</a><small class="variant-label">${escapeHtml(row.variant_label || '')}</small></th>${varying.map(field => `<td>${displayValue(specObject(row,field.key),field,true)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`;
          main.querySelector('.detail-main')?.insertAdjacentHTML('afterbegin', section);
        }).catch(() => { /* Product specifications remain usable if the listing cannot load. */ });
      }
    }
  }

  async function renderCompare(category, params, sequence) {
    const ids = [...new Set((params.get('ids') || '').split(',').filter(Boolean))];
    const returnQuery = validatedReturnQuery(category, params);
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
    let showDetails = false;
    const groupedFields = [...new Set(category.fields.map(field => field.group))];
    main.innerHTML = `${crumb([{name:category.name,url:backUrl},{name:'Compare'}])}<div class="page-head"><h1>Compare ${category.name.toLowerCase()} ${demoBadge(category)}</h1><p class="intro">Read differences side by side. Unknown and conflicted values remain separate from “No”. ${category.demo ? 'All products here are fictional demo data.' : 'Published values have not been independently reviewed.'}</p></div><div class="compare-toolbar"><label><input type="checkbox" id="differences-only" ${differencesOnly ? 'checked' : ''}>Show differences only</label><label><input type="checkbox" id="show-details">Show important and detailed specifications</label><a href="${backUrl}">Back to products</a></div><div id="comparison-table"></div>`;
    const target = main.querySelector('#comparison-table');
    const renderRows = () => {
      let rowCount = 0;
      const body = groupedFields.map(group => {
        const items = category.fields.filter(field => field.group === group && (showDetails || !field.tier || field.tier === 'core')).sort((a,b) => a.priority-b.priority).map(field => {
          const cells = records.map(record => specObject(record, field.key));
          const signatures = cells.map(spec => JSON.stringify([spec.status,spec.value]));
          const different = signatures.some(signature => signature !== signatures[0]);
          if (differencesOnly && !different) return '';
          rowCount++;
          return `<tr class="${different ? 'different' : ''}"><th scope="row">${escapeHtml(field.label)}${different ? ' <span class="visually-hidden">Differs</span>' : ''}</th>${cells.map((spec, index) => `<td>${records[index].previewOnly ? previewMark(valueWithContext(spec, field)) : valueWithContext(spec, field) + previewOverlay(records[index], field.key, field)}<div class="evidence-cell">${evidenceMarkup(records[index], spec)}</div></td>`).join('')}</tr>`;
        }).filter(Boolean).join('');
        return items ? `<tr class="group-row"><th colspan="${records.length + 1}" scope="colgroup">${escapeHtml(groupLabel(category,group))}</th></tr>${items}` : '';
      }).join('');
      target.innerHTML = `<div class="table-scroll" role="region" aria-label="Side-by-side product comparison" tabindex="0"><table class="compare-table"><thead><tr><th scope="col">Specification</th>${records.map(record => `<th scope="col"><a href="${productUrl(category.id, record.id, returnWithIds(category, returnQuery, ids))}">${escapeHtml(record.name)}</a> ${demoBadge(record)}${record.previewOnly ? ` ${unreviewedBadge}` : ''}<div class="muted code">${escapeHtml(record.model || '')}</div><button type="button" class="remove" data-remove="${escapeHtml(record.id)}">Remove</button></th>`).join('')}</tr></thead><tbody>${body || `<tr><td colspan="${records.length + 1}" class="empty-table">No differences in the recorded schema.</td></tr>`}</tbody></table></div><p class="muted">${rowCount} ${differencesOnly ? 'different' : 'total'} specification rows. Tinted rows contain a recorded difference.</p>`;
    };
    main.querySelector('#differences-only').addEventListener('change', event => {
      differencesOnly = event.target.checked;
      history.replaceState(null, '', compareUrl(category.id, ids, differencesOnly, returnQuery));
      renderRows();
    });
    main.querySelector('#show-details').addEventListener('change', event => { showDetails = event.target.checked; renderRows(); });
    target.addEventListener('click', event => {
      const button = event.target.closest('[data-remove]');
      if (!button) return;
      const remaining = ids.filter(id => id !== button.dataset.remove);
      const nextQuery = returnWithIds(category, returnQuery, remaining);
      location.hash = remaining.length >= 2 ? compareUrl(category.id, remaining, differencesOnly, nextQuery).slice(1) : returnUrl(category, nextQuery).slice(1);
    });
    renderRows();
  }
  window.addEventListener('hashchange', renderRoute);
  window.addEventListener('popstate', renderRoute);
  renderRoute();
})();

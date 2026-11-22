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
  let categoriesPromise;
  let routeSequence = 0;

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const encoded = (value) => encodeURIComponent(value);
  const safeUrl = (value) => { try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.href : null; } catch { return null; } };
  const categoryUrl = (id, query = '') => `#/category/${encoded(id)}${query}`;
  const productUrl = (category, id) => `#/product/${encoded(category)}/${encoded(id)}`;
  const compareUrl = (category, ids, differences = false) => `#/compare/${encoded(category)}?ids=${encoded(ids.join(','))}${differences ? '&diff=1' : ''}`;
  const BUILD = document.querySelector('meta[name="specsheet-build"]')?.content || '';
  const getJson = async (url) => { const response = await fetch(BUILD ? `${url}${url.includes('?') ? '&' : '?'}v=${BUILD}` : url); if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); };
  const categories = () => categoriesPromise ||= getJson('api/v1/categories.json').then(items => {
    items.forEach(item => categoryCache.set(item.id, item));
    return items;
  }).catch(error => { categoriesPromise = null; throw error; });
  const indexFor = (category) => {
    if (!indexCache.has(category.id)) indexCache.set(category.id, getJson(`api/v1/${category.products}`).catch(error => { indexCache.delete(category.id); throw error; }));
    return indexCache.get(category.id);
  };
  const detailFor = (categoryId, productId) => {
    const key = `${categoryId}/${productId}`;
    if (!detailCache.has(key)) detailCache.set(key, getJson(`api/v1/${encoded(categoryId)}/products/${encoded(productId)}.json`).catch(error => { detailCache.delete(key); throw error; }));
    return detailCache.get(key);
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
  const statusLabel = {known:'Known',unknown:'Unknown',conflicted:'Conflicted',not_yet_extracted:'Not yet extracted',not_applicable:'Not applicable'};
  const specObject = (product, key) => {
    if (!Object.hasOwn(product.specs || {}, key)) return {value:null,status:'not_yet_extracted',sources:[],confidence:null,source_scope:'none'};
    const raw = product.specs[key];
    if (raw && typeof raw === 'object' && Object.hasOwn(raw, 'status')) return raw;
    return {value:raw,status:raw === null ? 'unknown' : 'known',sources:[],confidence:null,source_scope:'none'};
  };
  const isKnown = (spec) => spec?.status === 'known';
  const displayValue = (spec, field, compact = false) => {
    if (!isKnown(spec)) {
      if (spec.status === 'conflicted') return `<span class="val-conflict">Conflicted${spec.value != null ? `: ${escapeHtml(formatRaw(spec.value, field, compact))}` : ''}</span>`;
      return `<span class="val-unknown">${escapeHtml(statusLabel[spec.status] || 'Unknown')}</span>`;
    }
    const value = spec.value;
    if (typeof value === 'boolean') return `<span class="${value ? 'val-true' : 'val-false'}">${value ? 'Yes' : 'No'}</span>`;
    if (Array.isArray(value) && value.length === 0) return '<span class="muted">None documented</span>';
    return escapeHtml(formatRaw(value, field, compact));
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
      if (route.kind === 'category' && route.parts.length === 1) { await renderCategory(category, route.params, sequence); if (sequence === routeSequence) main.focus(); return; }
      if (route.kind === 'product' && route.parts.length === 2) { await renderProduct(category, route.parts[1], sequence); if (sequence === routeSequence) main.focus(); return; }
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
    main.innerHTML = `<section class="lead-panel"><h1>Product specifications, with context.</h1><p>Search across brands, inspect the exact variant, and see where each recorded fact came from. Start with a category.</p></section><section aria-labelledby="cat-heading"><h2 id="cat-heading">Browse categories</h2><div class="category-list">${all.map(category => `<a class="category-row" href="${categoryUrl(category.id)}"><span><strong>${escapeHtml(category.name)}</strong> ${demoBadge(category)}<p>${escapeHtml(category.description)}</p></span><span class="count-pill">${category.count} ${category.count === 1 ? 'product' : 'products'} →</span></a>`).join('')}</div></section><p class="muted" style="margin-top:25px;max-width:72ch">The charger catalogue is an unreviewed pilot. The power-strip category contains fictional examples used to verify the interface, not buying guidance.</p>`;
  }

  function initialState(category, params) {
    const defaults = category.fields.filter(field => field.column).map(field => field.key);
    const available = new Set(category.fields.map(field => field.key));
    const cols = params.has('cols') ? params.get('cols').split(',').filter(key => available.has(key)) : defaults;
    const ids = (params.get('ids') || '').split(',').filter(Boolean).slice(0, 4);
    const filters = {};
    for (const field of category.fields.filter(f => f.facet)) {
      for (const suffix of (['number','range'].includes(field.type) ? ['min','max'] : ['value'])) {
        const key = `f_${field.key}_${suffix}`;
        if (params.has(key)) filters[key] = params.get(key);
      }
    }
    return {q: params.get('q') || '', brand: params.get('brand') || '', filters,
      sort: ['brand','name','model',...category.fields.map(f => f.key)].includes(params.get('sort')) ? params.get('sort') : 'brand',
      dir: params.get('dir') === 'desc' ? 'desc' : 'asc', cols, ids};
  }
  function persistCategoryState(category, state) {
    const params = new URLSearchParams();
    if (state.q) params.set('q', state.q);
    if (state.brand) params.set('brand', state.brand);
    for (const [key, value] of Object.entries(state.filters)) if (value) params.set(key, value);
    if (state.sort !== 'brand') params.set('sort', state.sort);
    if (state.dir !== 'asc') params.set('dir', state.dir);
    params.set('cols', state.cols.join(','));
    if (state.ids.length) params.set('ids', state.ids.join(','));
    history.replaceState(null, '', categoryUrl(category.id, `?${params}`));
  }
  const facetKey = (field, suffix = 'value') => `f_${field.key}_${suffix}`;
  const facetControl = (field, rows, state) => {
    const key = facetKey(field);
    const label = escapeHtml(field.label);
    const value = escapeHtml(state.filters[key] || '');
    if (field.type === 'number' || field.type === 'range') {
      const min = facetKey(field, 'min'), max = facetKey(field, 'max');
      const minLabel = field.type === 'range' ? 'From at least' : 'At least';
      const maxLabel = field.type === 'range' ? 'To at most' : 'At most';
      return `<div class="filter-field"><label>${label}${field.unit ? ` (${escapeHtml(field.unit)})` : ''}</label><div class="range-inputs"><input type="number" data-filter="${min}" aria-label="${minLabel} ${label}" placeholder="Min" value="${escapeHtml(state.filters[min] || '')}"><input type="number" data-filter="${max}" aria-label="${maxLabel} ${label}" placeholder="Max" value="${escapeHtml(state.filters[max] || '')}"></div></div>`;
    }
    if (field.type === 'bool') return `<div class="filter-field"><label for="facet-${field.key}">${label}</label><select id="facet-${field.key}" data-filter="${key}"><option value="">Any</option><option value="yes" ${value === 'yes' ? 'selected' : ''}>Yes</option><option value="no" ${value === 'no' ? 'selected' : ''}>No</option><option value="unknown" ${value === 'unknown' ? 'selected' : ''}>Unknown</option></select></div>`;
    if (field.type === 'enum') {
      const options = field.options || [...new Set(rows.map(row => specObject(row, field.key)).filter(isKnown).map(s => s.value).filter(v => typeof v === 'string'))].sort();
      return `<div class="filter-field"><label for="facet-${field.key}">${label}</label><select id="facet-${field.key}" data-filter="${key}"><option value="">Any</option>${options.map(option => `<option value="${escapeHtml(option)}" ${option === state.filters[key] ? 'selected' : ''}>${escapeHtml(option)}</option>`).join('')}<option value="__unknown" ${value === '__unknown' ? 'selected' : ''}>Unknown</option></select></div>`;
    }
    return `<div class="filter-field"><label for="facet-${field.key}">${label}</label><input id="facet-${field.key}" type="search" data-filter="${key}" value="${value}" placeholder="Contains…"></div>`;
  };
  const filterMarkup = (category, rows, state) => {
    const brands = [...new Set(rows.map(row => row.brand))].sort();
    const groups = [...new Set(category.fields.filter(f => f.facet).map(f => f.group))];
    return `<div class="filters-body"><div class="filter-field"><label for="brand-filter">Brand</label><select id="brand-filter"><option value="">All brands</option>${brands.map(brand => `<option value="${escapeHtml(brand)}" ${state.brand === brand ? 'selected' : ''}>${escapeHtml(brand)}</option>`).join('')}</select></div>${groups.map(group => `<section class="filter-group"><h3>${escapeHtml(group)}</h3>${category.fields.filter(f => f.facet && f.group === group).map(f => facetControl(f, rows, state)).join('')}</section>`).join('')}<button type="button" class="rail-reset" id="clear-filters">Reset filters</button></div>`;
  };
  const matchFacet = (row, field, filters) => {
    const spec = specObject(row, field.key);
    if (field.type === 'number' || field.type === 'range') {
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
    if (query === '__unknown' || (field.type === 'bool' && query === 'unknown')) return spec.status === 'unknown' || spec.status === 'not_yet_extracted';
    if (!isKnown(spec)) return false;
    if (field.type === 'bool') return spec.value === (query === 'yes');
    if (field.type === 'enum') return spec.value === query;
    return formatRaw(spec.value, field).toLocaleLowerCase().includes(query.toLocaleLowerCase());
  };
  const getSortValue = (row, key) => {
    if (['brand','name','model'].includes(key)) return row[key];
    const spec = specObject(row, key);
    return isKnown(spec) ? spec.value : null;
  };
  const compareSort = (a, b, state) => {
    const left = getSortValue(a, state.sort), right = getSortValue(b, state.sort);
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
    const rows = await indexFor(category);
    if (sequence !== routeSequence) return;
    setTitle(category.name);
    const state = initialState(category, params);
    state.ids = state.ids.filter(id => rows.some(row => row.id === id));
    main.innerHTML = `${crumb([{name:category.name}])}<div class="page-head"><h1>${escapeHtml(category.name)} ${demoBadge(category)}</h1><p class="intro">${escapeHtml(category.description)} ${category.demo ? 'These fictional records test the interface and are not product recommendations.' : 'Pilot records are unreviewed; open a product to inspect evidence and uncertainty.'}</p></div><div class="catalogue-layout"><aside class="filter-rail"><details open><summary>Filters</summary>${filterMarkup(category, rows, state)}</details></aside><section class="catalogue-results" aria-label="Products"><div class="results-head"><label class="search-field" for="product-search">Search name, brand or identifier<input id="product-search" type="search" placeholder="Search products…" value="${escapeHtml(state.q)}" autocomplete="off"></label><div><h2>Compare the facts</h2><p>Choose 2–4 products to compare.</p></div></div><div class="results-tools"><span class="meta" id="result-count" role="status"></span><details class="column-menu"><summary>Choose columns</summary><div class="column-options">${category.fields.map(field => `<label><input type="checkbox" data-column="${escapeHtml(field.key)}" ${state.cols.includes(field.key) ? 'checked' : ''}>${escapeHtml(field.label)}</label>`).join('')}</div></details></div><div id="results-table"></div><div id="compare-shelf"></div></section></div>`;
    const mobileQuery = matchMedia('(max-width: 800px)');
    const filterDisclosure = main.querySelector('.filter-rail > details');
    filterDisclosure.open = !mobileQuery.matches;
    mobileQuery.addEventListener('change', event => { if (filterDisclosure.isConnected) filterDisclosure.open = !event.matches; }, {once:false});
    const search = main.querySelector('#product-search');
    search.addEventListener('input', () => { state.q = search.value; update(); });
    main.querySelector('#brand-filter').addEventListener('change', event => { state.brand = event.target.value; update(); });
    main.querySelectorAll('[data-filter]').forEach(control => control.addEventListener(control.tagName === 'SELECT' ? 'change' : 'input', () => { state.filters[control.dataset.filter] = control.value; update(); }));
    main.querySelector('#clear-filters').addEventListener('click', () => {
      state.q = ''; state.brand = ''; state.filters = {};
      search.value = ''; main.querySelector('#brand-filter').value = '';
      main.querySelectorAll('[data-filter]').forEach(control => { control.value = ''; });
      update(); search.focus();
    });
    main.querySelectorAll('[data-column]').forEach(control => control.addEventListener('change', () => {
      state.cols = [...main.querySelectorAll('[data-column]:checked')].map(input => input.dataset.column);
      update();
    }));
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
        active?.closest('#compare-shelf') ? {kind:'shelf'} : null;
      const q = state.q.trim().toLocaleLowerCase();
      const filtered = rows.filter(row => (!q || [row.name, row.brand, row.family, row.model, ...row.identifiers.map(id => id.value)].some(value => String(value || '').toLocaleLowerCase().includes(q))) && (!state.brand || row.brand === state.brand) && category.fields.filter(f => f.facet).every(field => matchFacet(row, field, state.filters))).sort((a, b) => compareSort(a, b, state));
      main.querySelector('#result-count').textContent = `${filtered.length} of ${rows.length} products`;
      renderTable(category, filtered, state);
      renderShelf(category, rows, state);
      persistCategoryState(category, state);
      if (focus?.kind === 'select') [...main.querySelectorAll('[data-select]')].find(input => input.dataset.select === focus.value)?.focus();
      if (focus?.kind === 'sort') [...main.querySelectorAll('[data-sort]')].find(button => button.dataset.sort === focus.value)?.focus();
      if (focus?.kind === 'shelf') (main.querySelector('#compare-shelf [data-remove]') || search).focus();
    }
    update();
  }

  function renderTable(category, rows, state) {
    const fields = state.cols.map(key => category.fields.find(field => field.key === key)).filter(Boolean);
    const columnHeader = (key, label) => `<th scope="col" aria-sort="${state.sort === key ? (state.dir === 'asc' ? 'ascending' : 'descending') : 'none'}"><button type="button" data-sort="${escapeHtml(key)}">${escapeHtml(label)} ${state.sort === key ? (state.dir === 'asc' ? '↑' : '↓') : ''}</button></th>`;
    const target = main.querySelector('#results-table');
    if (!rows.length) {
      target.innerHTML = '<div class="empty-table"><strong>No matching products</strong>Try a broader search or reset the filters.</div>';
      return;
    }
    target.innerHTML = `<div class="table-scroll" role="region" aria-label="Product comparison table" tabindex="0"><table><thead><tr><th scope="col">Select</th>${columnHeader('brand','Brand')}${columnHeader('name','Product')}${columnHeader('model','Model')}${fields.map(f => columnHeader(f.key, f.label)).join('')}</tr></thead><tbody>${rows.map(row => `<tr class="${state.ids.includes(row.id) ? 'selected' : ''}"><td class="select-cell"><input type="checkbox" data-select="${escapeHtml(row.id)}" aria-label="Select ${escapeHtml(row.name)} for comparison" ${state.ids.includes(row.id) ? 'checked' : ''} ${state.ids.length >= 4 && !state.ids.includes(row.id) ? 'disabled' : ''}></td><td>${escapeHtml(row.brand)}</td><td class="name-cell"><a href="${productUrl(category.id, row.id)}">${escapeHtml(row.name)}</a> ${demoBadge(row)}</td><td class="code">${escapeHtml(row.model || '—')}</td>${fields.map(f => `<td class="${f.type === 'number' ? 'num' : ''}">${displayValue(specObject(row, f.key), f, true)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  function renderShelf(category, rows, state) {
    const target = main.querySelector('#compare-shelf');
    if (!state.ids.length) { target.innerHTML = ''; return; }
    const chosen = selectedRows(rows, state);
    target.innerHTML = `<div class="compare-shelf"><strong>${chosen.length} selected</strong><div class="selected-items">${chosen.map(row => `<button type="button" data-remove="${escapeHtml(row.id)}" aria-label="Remove ${escapeHtml(row.name)}">${escapeHtml(row.brand)} ${escapeHtml(row.model || row.name)} ×</button>`).join('')}</div>${chosen.length >= 2 ? `<a class="button-link primary" href="${compareUrl(category.id, state.ids)}">Compare products</a>` : '<small>Select at least one more product.</small>'}</div>`;
  }

  const evidenceMarkup = (record, spec) => {
    const direct = (spec.sources || []).map(id => record.sources.find(source => source.id === id)).filter(Boolean);
    const context = direct.length ? [] : record.sources;
    const kind = direct.length ? 'direct' : (spec.status === 'conflicted' ? 'warning' : '');
    const label = direct.length ? `${direct.length} field ${direct.length === 1 ? 'source' : 'sources'}` : (context.length ? 'Record context' : 'No source');
    const sourceList = direct.length ? direct : context;
    const scopeText = direct.length ? 'These links were attached to this field in the pilot record.' : context.length ? 'These links belong to the record; none was attached to this field.' : 'No source link is available for this field.';
    return `<details><summary><span class="badge ${kind}">${label}</span></summary><p>${scopeText}</p>${sourceList.length ? `<ul>${sourceList.map(source => { const url = safeUrl(source.url); return `<li>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label)}</a>` : escapeHtml(source.label)}</li>`; }).join('')}</ul>` : ''}<p>Field confidence: ${escapeHtml(spec.confidence || 'not rated')}. ${escapeHtml(statusLabel[spec.status] || 'Unknown')}.</p></details>`;
  };
  async function renderProduct(category, productId, sequence) {
    setLoading('Loading product specifications…');
    let record;
    try { record = await detailFor(category.id, productId); }
    catch (error) { if (sequence === routeSequence) main.innerHTML = errorPanel('Product not found', `This product record could not be loaded (${error.message}).`, `<a href="${categoryUrl(category.id)}">Back to ${escapeHtml(category.name)}</a>`); return; }
    if (sequence !== routeSequence) return;
    setTitle(record.name);
    const groups = [...new Set(category.fields.map(field => field.group))];
    main.innerHTML = `${crumb([{name:category.name,url:categoryUrl(category.id)},{name:record.name}])}<div class="page-head"><h1>${escapeHtml(record.name)} ${demoBadge(record)}</h1><p class="intro">${escapeHtml(record.brand)}${record.family ? ` · ${escapeHtml(record.family)}` : ''}${record.model ? ` · <span class="code">${escapeHtml(record.model)}</span>` : ''}</p></div>${record.demo ? '<div class="callout">Fictional demo data. Values and identifiers on this page do not describe a real product.</div>' : ''}<div class="detail-grid"><div class="detail-main"><div class="callout">${escapeHtml(record.identity_caveat || 'Identity has not been independently verified.')}</div>${groups.map(group => `<section class="detail-section"><h2>${escapeHtml(group)}</h2><div class="table-scroll"><table class="spec-table"><tbody>${category.fields.filter(field => field.group === group).sort((a,b) => a.priority-b.priority).map(field => { const spec = specObject(record, field.key); return `<tr><th scope="row">${escapeHtml(field.label)}</th><td class="value-cell">${displayValue(spec, field)}</td><td class="evidence-cell">${evidenceMarkup(record, spec)}</td></tr>`; }).join('')}</tbody></table></div></section>`).join('')}<section class="detail-section"><h2>Documents</h2>${record.documents.length ? `<ul class="source-list">${record.documents.map(doc => { const url = safeUrl(doc.url); return `<li>${url ? `<a href="${escapeHtml(url)}">${escapeHtml(doc.label || url)}</a>` : escapeHtml(doc.label || 'Unlinked document')}</li>`; }).join('')}</ul>` : '<p class="muted">No manuals or specification sheets are linked yet.</p>'}</section><section class="detail-section"><h2>Media</h2>${record.media.length ? `<ul class="source-list">${record.media.map(item => { const url = safeUrl(item.url); return `<li>${url ? `<a href="${escapeHtml(url)}">${escapeHtml(item.label || url)}</a>` : escapeHtml(item.label || 'Unlinked media')}</li>`; }).join('')}</ul>` : '<p class="muted">No product images or media are linked yet.</p>'}</section></div><aside class="detail-side"><h2>Record context</h2><dl><dt>Brand</dt><dd>${escapeHtml(record.brand)}</dd><dt>Family hint</dt><dd>${escapeHtml(record.family || 'Not recorded')}</dd><dt>Model hint</dt><dd class="code">${escapeHtml(record.model || 'Not recorded')}</dd><dt>Variant hint</dt><dd>${escapeHtml(record.variant || 'Not resolved')}</dd><dt>Record confidence</dt><dd>${escapeHtml(record.confidence?.level || 'Not rated')} <span class="muted">(${escapeHtml(record.confidence?.scope || 'record')})</span></dd></dl><section class="detail-section"><h2>Identifiers</h2>${record.identifiers.length ? `<ul class="source-list">${record.identifiers.map(id => `<li><span class="code">${escapeHtml(id.value)}</span><br><span class="muted">${escapeHtml(id.scheme)} · ${escapeHtml(id.issuer || 'Issuer unspecified')}${id.market ? ` · ${escapeHtml(id.market)}` : ''} · ${escapeHtml(id.package_level || 'scope unverified')}</span></li>`).join('')}</ul>` : '<p>No identifiers recorded.</p>'}</section><section class="detail-section"><h2>Source links</h2>${record.sources.length ? `<ul class="source-list">${record.sources.map(source => { const url = safeUrl(source.url); return `<li>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.label)}</a>` : escapeHtml(source.label)}</li>`; }).join('')}</ul>` : '<p class="muted">No source links; this is demo data.</p>'}</section>${record.marketing_terms.length ? `<section class="detail-section"><h2>Marketing terms</h2><p>${escapeHtml(record.marketing_terms.join(', '))}</p></section>` : ''}<section class="detail-section"><h2>Record notes</h2><p>${escapeHtml(record.notes || 'No notes recorded.')}</p></section></aside></div>`;
  }

  async function renderCompare(category, params, sequence) {
    const ids = [...new Set((params.get('ids') || '').split(',').filter(Boolean))];
    if (ids.length < 2 || ids.length > 4) { main.innerHTML = errorPanel('Choose 2–4 products', 'Select products from one category before opening comparison.', `<a href="${categoryUrl(category.id)}">Browse ${escapeHtml(category.name)}</a>`); return; }
    setLoading('Loading comparison…');
    let records;
    try { records = await Promise.all(ids.map(id => detailFor(category.id, id))); }
    catch (error) { if (sequence === routeSequence) main.innerHTML = errorPanel('Comparison unavailable', `One or more products could not be loaded (${error.message}).`, `<a href="${categoryUrl(category.id)}">Back to ${escapeHtml(category.name)}</a>`); return; }
    if (sequence !== routeSequence) return;
    if (records.some(record => record.category !== category.id)) { main.innerHTML = errorPanel('Mixed categories', 'All compared products must belong to the same category.', `<a href="${categoryUrl(category.id)}">Back to ${escapeHtml(category.name)}</a>`); return; }
    setTitle(`Compare ${category.name}`);
    let differencesOnly = params.get('diff') === '1';
    const groupedFields = [...new Set(category.fields.map(field => field.group))];
    main.innerHTML = `${crumb([{name:category.name,url:categoryUrl(category.id)},{name:'Compare'}])}<div class="page-head"><h1>Compare ${category.name.toLowerCase()} ${demoBadge(category)}</h1><p class="intro">Read differences side by side. Unknown and conflicted values remain separate from “No”. ${category.demo ? 'All products here are fictional demo data.' : 'Pilot values have not been independently reviewed.'}</p></div><div class="compare-toolbar"><label><input type="checkbox" id="differences-only" ${differencesOnly ? 'checked' : ''}>Show differences only</label><a href="${categoryUrl(category.id)}">Back to products</a></div><div id="comparison-table"></div>`;
    const target = main.querySelector('#comparison-table');
    const renderRows = () => {
      let rowCount = 0;
      const body = groupedFields.map(group => {
        const items = category.fields.filter(field => field.group === group).sort((a,b) => a.priority-b.priority).map(field => {
          const cells = records.map(record => specObject(record, field.key));
          const signatures = cells.map(spec => JSON.stringify([spec.status,spec.value]));
          const different = signatures.some(signature => signature !== signatures[0]);
          if (differencesOnly && !different) return '';
          rowCount++;
          return `<tr class="${different ? 'different' : ''}"><th scope="row">${escapeHtml(field.label)}${different ? ' <span class="visually-hidden">Differs</span>' : ''}</th>${cells.map((spec, index) => `<td>${displayValue(spec, field)}<div class="evidence-cell">${evidenceMarkup(records[index], spec)}</div></td>`).join('')}</tr>`;
        }).filter(Boolean).join('');
        return items ? `<tr class="group-row"><th colspan="${records.length + 1}" scope="colgroup">${escapeHtml(group)}</th></tr>${items}` : '';
      }).join('');
      target.innerHTML = `<div class="table-scroll" role="region" aria-label="Side-by-side product comparison" tabindex="0"><table class="compare-table"><thead><tr><th scope="col">Specification</th>${records.map(record => `<th scope="col"><a href="${productUrl(category.id, record.id)}">${escapeHtml(record.name)}</a> ${demoBadge(record)}<div class="muted code">${escapeHtml(record.model || '')}</div><button type="button" class="remove" data-remove="${escapeHtml(record.id)}">Remove</button></th>`).join('')}</tr></thead><tbody>${body || `<tr><td colspan="${records.length + 1}" class="empty-table">No differences in the recorded schema.</td></tr>`}</tbody></table></div><p class="muted">${rowCount} ${differencesOnly ? 'different' : 'total'} specification rows. Tinted rows contain a recorded difference.</p>`;
    };
    main.querySelector('#differences-only').addEventListener('change', event => {
      differencesOnly = event.target.checked;
      history.replaceState(null, '', compareUrl(category.id, ids, differencesOnly));
      renderRows();
    });
    target.addEventListener('click', event => {
      const button = event.target.closest('[data-remove]');
      if (!button) return;
      const remaining = ids.filter(id => id !== button.dataset.remove);
      location.hash = remaining.length >= 2 ? compareUrl(category.id, remaining, differencesOnly).slice(1) : categoryUrl(category.id, `?ids=${encoded(remaining.join(','))}`).slice(1);
    });
    renderRows();
  }
  window.addEventListener('hashchange', renderRoute);
  window.addEventListener('popstate', renderRoute);
  renderRoute();
})();

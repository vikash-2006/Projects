// SQL + LLM Connect — frontend logic
// Talks to the Flask backend at /api/query and /api/schema

const form = document.getElementById('queryForm');
const input = document.getElementById('conditionInput');
const submitBtn = document.getElementById('submitBtn');
const submitBtnLabel = document.getElementById('submitBtnLabel');
const submitBtnSpinner = document.querySelector('.btn__spinner');

const emptyState = document.getElementById('emptyState');

const sqlPanel = document.getElementById('sqlPanel');
const sqlOutput = document.getElementById('sqlOutput');
const copySqlBtn = document.getElementById('copySqlBtn');
const rerunSqlBtn = document.getElementById('rerunSqlBtn');

const resultsSection = document.getElementById('resultsSection');
const resultsCount = document.getElementById('resultsCount');
const resultsThead = document.getElementById('resultsThead');
const resultsTbody = document.getElementById('resultsTbody');
const resultsEmpty = document.getElementById('resultsEmpty');

const errorSection = document.getElementById('errorSection');
const errorMessage = document.getElementById('errorMessage');

const dbStatusDot = document.getElementById('dbStatusDot');
const dbStatusText = document.getElementById('dbStatusText');

const toast = document.getElementById('toast');

const suggestionsDropdown = document.getElementById('suggestionsDropdown');

let schemaTables = [];
let allSuggestions = [];
let currentMatches = [];
let activeSuggestionIndex = -1;

let currentColumns = [];
let currentRows = [];
let sortState = { column: null, direction: 1 };

// Every UI section that can be shown/hidden as a result of a query run.
// hideAll() is the single source of truth for "nothing is showing" — every
// code path that ends a request (success, error, network failure) routes
// through it before showing its own section, so panels never stack.
function hideAll() {
  sqlPanel.hidden = true;
  resultsSection.hidden = true;
  errorSection.hidden = true;
  emptyState.hidden = true;
}

function showEmptyState() {
  hideAll();
  emptyState.hidden = false;
}

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  submitBtnLabel.textContent = isLoading ? 'Running…' : 'Run query';
  submitBtnSpinner.hidden = !isLoading;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('is-visible');
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.remove('is-visible'), 1800);
}

function renderResults(data) {
  currentColumns = data.columns || [];
  currentRows = data.rows || [];
  sortState = { column: null, direction: 1 };
  paintTable();

  resultsCount.textContent = `${data.row_count} row${data.row_count === 1 ? '' : 's'}`;
  resultsSection.hidden = false;
}

function paintTable() {
  resultsThead.innerHTML = '';
  resultsTbody.innerHTML = '';

  const tableWrap = resultsSection.querySelector('.results__table-wrap');

  if (currentColumns.length === 0 || currentRows.length === 0) {
    resultsEmpty.hidden = false;
    tableWrap.hidden = true;
    return;
  }

  resultsEmpty.hidden = true;
  tableWrap.hidden = false;

  const headRow = document.createElement('tr');
  currentColumns.forEach(col => {
    const th = document.createElement('th');
    th.textContent = col;
    if (sortState.column === col) th.classList.add('is-sorted');

    const arrow = document.createElement('span');
    arrow.className = 'sort-arrow';
    arrow.textContent = sortState.column === col ? (sortState.direction === 1 ? '↑' : '↓') : '↕';
    th.appendChild(arrow);

    th.addEventListener('click', () => sortByColumn(col));
    headRow.appendChild(th);
  });
  resultsThead.appendChild(headRow);

  let rows = currentRows;
  if (sortState.column) {
    rows = [...currentRows].sort((a, b) => {
      const av = a[sortState.column];
      const bv = b[sortState.column];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === 'number' && typeof bv === 'number') {
        return (av - bv) * sortState.direction;
      }
      return String(av).localeCompare(String(bv)) * sortState.direction;
    });
  }

  rows.forEach(row => {
    const tr = document.createElement('tr');
    currentColumns.forEach(col => {
      const td = document.createElement('td');
      const val = row[col];
      if (val === null || val === undefined) {
        td.textContent = 'null';
        td.classList.add('is-null');
      } else {
        td.textContent = String(val);
      }
      tr.appendChild(td);
    });
    resultsTbody.appendChild(tr);
  });
}

function sortByColumn(col) {
  if (sortState.column === col) {
    sortState.direction *= -1;
  } else {
    sortState.column = col;
    sortState.direction = 1;
  }
  paintTable();
}

function renderSql(sql) {
  sqlOutput.value = sql;
  autoGrow(sqlOutput);
  sqlPanel.hidden = false;
}

function buildSuggestions(tables) {
  const suggestions = ['show me all tables', 'describe the database schema'];

  tables.forEach(t => {
    const table = t.table;
    suggestions.push(`show me all rows from ${table}`);
    suggestions.push(`count of rows in ${table}`);
    suggestions.push(`first 10 rows from ${table}`);

    (t.columns || []).forEach(col => {
      suggestions.push(`${table} where ${col} = `);
      suggestions.push(`${table} sorted by ${col} descending`);
      suggestions.push(`average ${col} in ${table}`);
    });
  });

  return suggestions;
}

function getMatches(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return allSuggestions
    .filter(s => s.toLowerCase().includes(q))
    .sort((a, b) => a.toLowerCase().indexOf(q) - b.toLowerCase().indexOf(q))
    .slice(0, 7);
}

function highlightMatch(text, query) {
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return text.slice(0, idx) + '<mark>' + text.slice(idx, idx + query.length) + '</mark>' + text.slice(idx + query.length);
}

function renderSuggestions(matches, query) {
  currentMatches = matches;
  activeSuggestionIndex = -1;
  suggestionsDropdown.innerHTML = '';

  if (matches.length === 0) {
    suggestionsDropdown.hidden = true;
    return;
  }

  matches.forEach(text => {
    const item = document.createElement('div');
    item.className = 'suggestion-item';
    item.innerHTML = `<span class="suggestion-item__icon">→</span><span>${highlightMatch(text, query)}</span>`;
    item.addEventListener('mousedown', (e) => {
      e.preventDefault();
      selectSuggestion(text);
    });
    suggestionsDropdown.appendChild(item);
  });

  suggestionsDropdown.hidden = false;
}

function selectSuggestion(text) {
  input.value = text;
  suggestionsDropdown.hidden = true;
  input.focus();
}

function updateActiveSuggestion() {
  const items = suggestionsDropdown.querySelectorAll('.suggestion-item');
  items.forEach((el, i) => el.classList.toggle('is-active', i === activeSuggestionIndex));
  if (activeSuggestionIndex >= 0 && items[activeSuggestionIndex]) {
    items[activeSuggestionIndex].scrollIntoView({ block: 'nearest' });
  }
}

function autoGrow(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = `${textarea.scrollHeight}px`;
}

function renderError(message) {
  errorMessage.textContent = message;
  errorSection.hidden = false;
}

async function submitQuery(condition, sqlOverride) {
  hideAll();
  setLoading(true);

  try {
    const body = sqlOverride
      ? { condition, sql: sqlOverride }
      : { condition };

    const res = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();

    if (!res.ok || !data.ok) {
      if (data.sql) renderSql(data.sql);
      renderError(data.error || 'Unexpected error. Please try rephrasing your question.');
      return;
    }

    renderSql(data.sql);
    renderResults(data);
  } catch (err) {
    renderError('Could not reach the server. Make sure the Flask app is running.');
  } finally {
    setLoading(false);
  }
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  const condition = input.value.trim();
  if (!condition) return;
  submitQuery(condition);
});

input.addEventListener('input', () => {
  const matches = getMatches(input.value);
  renderSuggestions(matches, input.value.trim());
});

input.addEventListener('blur', () => {
  setTimeout(() => { suggestionsDropdown.hidden = true; }, 100);
});

input.addEventListener('keydown', (e) => {
  const dropdownOpen = !suggestionsDropdown.hidden && currentMatches.length > 0;

  if (dropdownOpen && e.key === 'ArrowDown') {
    e.preventDefault();
    activeSuggestionIndex = Math.min(activeSuggestionIndex + 1, currentMatches.length - 1);
    updateActiveSuggestion();
    return;
  }
  if (dropdownOpen && e.key === 'ArrowUp') {
    e.preventDefault();
    activeSuggestionIndex = Math.max(activeSuggestionIndex - 1, 0);
    updateActiveSuggestion();
    return;
  }
  if (dropdownOpen && e.key === 'Escape') {
    suggestionsDropdown.hidden = true;
    return;
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (dropdownOpen && activeSuggestionIndex >= 0) {
      selectSuggestion(currentMatches[activeSuggestionIndex]);
      return;
    }
    suggestionsDropdown.hidden = true;
    form.requestSubmit();
  }
});

document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    input.value = chip.dataset.example;
    input.focus();
  });
});

sqlOutput.addEventListener('input', () => autoGrow(sqlOutput));

copySqlBtn.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(sqlOutput.value);
    showToast('SQL copied to clipboard');
  } catch (err) {
    // Clipboard API unavailable — the SQL is still visible and selectable manually.
  }
});

rerunSqlBtn.addEventListener('click', () => {
  const condition = input.value.trim() || '(edited query)';
  const sql = sqlOutput.value.trim();
  if (!sql) return;
  submitQuery(condition, sql);
});

// Check DB connectivity on load
async function checkDbStatus() {
  try {
    const res = await fetch('/api/schema');
    const data = await res.json();
    if (data.ok) {
      dbStatusDot.classList.add('is-online');
      dbStatusText.textContent = 'Database connected';
      schemaTables = data.tables || [];
      allSuggestions = buildSuggestions(schemaTables);
    } else {
      dbStatusDot.classList.add('is-offline');
      dbStatusText.textContent = 'Database unreachable';
    }
  } catch (err) {
    dbStatusDot.classList.add('is-offline');
    dbStatusText.textContent = 'Database unreachable';
  }
}

checkDbStatus();
showEmptyState();
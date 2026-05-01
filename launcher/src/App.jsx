import React, { useState, useEffect, useMemo, useCallback } from 'react';
import './App.css';
import ObjectCard from './components/ObjectCard';
import EnvCard from './components/EnvCard';
import Toast from './components/Toast';
import InstallModal from './components/InstallModal';

const BASE_URL = process.env.REACT_APP_OMNIBIOAI_BASE_URL || 'http://127.0.0.1:8000';
const TOKEN = process.env.REACT_APP_OMNIBIOAI_TOKEN || 'dev';
const JUPYTER_BASE = process.env.REACT_APP_JUPYTER_BASE || 'http://127.0.0.1:8890';
const JUPYTER_TOKEN = process.env.REACT_APP_JUPYTER_TOKEN || 'devtoken';
const USE_MOCK = process.env.REACT_APP_USE_MOCK === 'true';
const PAGE_SIZE = 20;

// ── Mock data ─────────────────────────────────────────────────────────
const MOCK_OBJECT = {
  object_id: 'test-1234-abcd-5678',
  name: 'TCGA-BRCA RNAseq cohort 2024',
  object_type: 'RNASeqObject',
  metadata: { samples: 1247, genome: 'hg38', platform: 'Illumina NovaSeq', created_by: 'manish' },
};

const MOCK_REGISTRY = {
  'test-1234-abcd-5678': { ...MOCK_OBJECT, parent_id: null },
  '56d3fc3a-709b-4ed0-bf17-8cb73c6746b0': {
    object_id: '56d3fc3a-709b-4ed0-bf17-8cb73c6746b0',
    object_type: 'LiteratureStudy', name: 'Alzheimer CaseStudy',
    metadata: { study: 'Alzheimer_CaseStudy', status: 'created' }, parent_id: null,
  },
  '673590e8-fd26-4f8b-99cf-ddbf79d4bcd9': {
    object_id: '673590e8-fd26-4f8b-99cf-ddbf79d4bcd9',
    object_type: 'LiteratureJob', name: 'Alzheimer Ingest Job',
    metadata: { kind: 'ingest', status: 'done' },
    parent_id: '56d3fc3a-709b-4ed0-bf17-8cb73c6746b0',
  },
  'dadb78b0-348f-4056-b9f6-c870abb00455': {
    object_id: 'dadb78b0-348f-4056-b9f6-c870abb00455',
    object_type: 'LiteratureJob', name: 'Alzheimer Embedding Job',
    metadata: { kind: 'embed', status: 'done' },
    parent_id: '56d3fc3a-709b-4ed0-bf17-8cb73c6746b0',
  },
  '0cd22aa4-7d03-4851-8136-0da11318188b': {
    object_id: '0cd22aa4-7d03-4851-8136-0da11318188b',
    object_type: 'LiteratureSummary', name: 'Amyloid Therapy Summary',
    metadata: { status: 'done', query: 'Which therapies target amyloid pathways?' },
    parent_id: '56d3fc3a-709b-4ed0-bf17-8cb73c6746b0',
  },
  'f07c1ee1-0095-4c30-81aa-185c89c7bc43': {
    object_id: 'f07c1ee1-0095-4c30-81aa-185c89c7bc43',
    object_type: 'LiteratureJob', name: 'Alzheimer RAG Job',
    metadata: { kind: 'rag', status: 'done' },
    parent_id: '56d3fc3a-709b-4ed0-bf17-8cb73c6746b0',
  },
};

// ── Styling helpers ───────────────────────────────────────────────────
const TYPE_COLORS = {
  LiteratureStudy:   { bg: '#e8f4fd', text: '#1a6fa8', border: '#b3d7f0' },
  LiteratureJob:     { bg: '#fff3e0', text: '#a05a00', border: '#ffcc80' },
  LiteratureSummary: { bg: '#e8f5e9', text: '#2e7d32', border: '#a5d6a7' },
  RNASeqObject:      { bg: '#f3e5f5', text: '#7b1fa2', border: '#ce93d8' },
  default:           { bg: '#f1f3f4', text: '#3c4043', border: '#dadce0' },
};

function typeBadge(objectType) {
  const c = TYPE_COLORS[objectType] || TYPE_COLORS.default;
  return {
    display: 'inline-block', padding: '2px 8px', borderRadius: 4,
    fontSize: 11, fontWeight: 600, letterSpacing: '0.3px',
    background: c.bg, color: c.text, border: `1px solid ${c.border}`,
    whiteSpace: 'nowrap',
  };
}

const STATUS_COLOR = { done: '#2e7d32', created: '#a05a00', running: '#1a73e8', failed: '#c62828' };

function shouldUseMock(id) { return USE_MOCK || id === 'test'; }

const LAUNCH_LABELS = {
  notebook: 'Open in JupyterLab',
  python:   'Copy env vars to clipboard',
  r:        'Download R script + open RStudio',
};

// ── Group builder ─────────────────────────────────────────────────────
function buildGroups(objects, groupMode) {
  if (groupMode === 'flat') {
    return [{ groupKey: 'all', label: null, objects }];
  }

  if (groupMode === 'type') {
    const byType = {};
    objects.forEach((o) => {
      const t = o.object_type || 'Unknown';
      if (!byType[t]) byType[t] = [];
      byType[t].push(o);
    });
    return Object.entries(byType)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([t, objs]) => ({ groupKey: t, label: t, objects: objs }));
  }

  if (groupMode === 'study') {
    const byId = Object.fromEntries(objects.map((o) => [o.object_id, o]));
    const childrenMap = {};
    const roots = [];

    objects.forEach((o) => {
      const pid = o.parent_id;
      if (pid && byId[pid]) {
        if (!childrenMap[pid]) childrenMap[pid] = [];
        childrenMap[pid].push(o);
      } else {
        roots.push(o);
      }
    });

    const groups = [];
    const typeOrphans = {};

    roots.forEach((root) => {
      const kids = childrenMap[root.object_id] || [];
      if (kids.length > 0) {
        groups.push({
          groupKey: root.object_id,
          label: root.name || root.object_type,
          parentObj: root,
          objects: [root, ...kids],
        });
      } else {
        const t = root.object_type || 'Unknown';
        if (!typeOrphans[t]) typeOrphans[t] = [];
        typeOrphans[t].push(root);
      }
    });

    Object.entries(typeOrphans)
      .sort(([a], [b]) => a.localeCompare(b))
      .forEach(([t, objs]) => {
        groups.push({ groupKey: `type-${t}`, label: t, objects: objs });
      });

    return groups;
  }

  return [{ groupKey: 'all', label: null, objects }];
}

// ── ObjectRow ─────────────────────────────────────────────────────────
function ObjectRow({ obj, onSelect, isChild }) {
  const [hovered, setHovered] = useState(false);
  const status = obj.metadata?.status;

  const metaPreview = obj.metadata
    ? Object.entries(obj.metadata)
        .filter(([k]) => !['status', 'log_tail', 'celery_id', 'citations', 'answer', 'progress'].includes(k))
        .slice(0, 3)
        .map(([k, v]) => `${k}: ${v}`)
        .join('  ·  ')
    : '';

  return (
    <div
      onClick={() => onSelect(obj)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: isChild ? '10px 16px 10px 32px' : '12px 16px',
        borderRadius: 10, cursor: 'pointer',
        border: hovered ? '1px solid #1a73e8' : '1px solid #e8eaed',
        background: hovered ? '#f0f6ff' : isChild ? '#fafbfc' : '#fff',
        transition: 'border-color 0.15s, background 0.15s',
        boxShadow: hovered ? '0 1px 6px rgba(26,115,232,0.12)' : 'none',
        marginLeft: isChild ? 16 : 0,
        position: 'relative',
      }}
    >
      {isChild && (
        <div style={{
          position: 'absolute', left: 12, top: '50%',
          transform: 'translateY(-50%)',
          width: 10, height: 1, background: '#dadce0',
        }} />
      )}

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 3 }}>
          <span style={{ fontWeight: 600, fontSize: 14, color: '#202124' }}>
            {obj.name || obj.object_type}
          </span>
          <span style={typeBadge(obj.object_type)}>{obj.object_type}</span>
          {status && (
            <span style={{ fontSize: 11, fontWeight: 500, color: STATUS_COLOR[status] || '#5f6368' }}>
              ● {status}
            </span>
          )}
        </div>
        <div style={{ fontSize: 11, color: '#9aa0a6', fontFamily: 'monospace', marginBottom: metaPreview ? 2 : 0 }}>
          {obj.object_id}
        </div>
        {metaPreview && (
          <div style={{ fontSize: 12, color: '#5f6368' }}>{metaPreview}</div>
        )}
      </div>

      <div style={{
        marginLeft: 12, fontSize: 13, whiteSpace: 'nowrap', transition: 'color 0.15s',
        color: hovered ? '#1a73e8' : '#9aa0a6', fontWeight: hovered ? 600 : 400,
      }}>
        Open →
      </div>
    </div>
  );
}

// ── GroupSection ──────────────────────────────────────────────────────
function GroupSection({ group, onSelect, groupMode, page, onLoadMore }) {
  const { label, objects, parentObj } = group;
  const [collapsed, setCollapsed] = useState(false);
  const isStudyGroup = groupMode === 'study' && !!parentObj;

  const visibleObjects = objects.slice(0, page * PAGE_SIZE);
  const remaining = objects.length - visibleObjects.length;

  return (
    <div style={{ marginBottom: label ? 20 : 0 }}>
      {label && (
        <div
          onClick={() => setCollapsed((c) => !c)}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '6px 4px', marginBottom: 8, cursor: 'pointer', userSelect: 'none',
          }}
        >
          <span style={{
            fontSize: 10, color: '#9aa0a6', display: 'inline-block',
            transition: 'transform 0.15s',
            transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
          }}>▾</span>

          {isStudyGroup ? (
            <>
              <span style={typeBadge(parentObj.object_type)}>{parentObj.object_type}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#3c4043' }}>{label}</span>
            </>
          ) : (
            <span style={{ fontSize: 13, fontWeight: 600, color: '#3c4043' }}>{label}</span>
          )}

          <span style={{
            fontSize: 11, color: '#9aa0a6', background: '#f1f3f4',
            borderRadius: 10, padding: '1px 7px',
          }}>
            {objects.length}
          </span>
        </div>
      )}

      {!collapsed && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {visibleObjects.map((obj) => (
            <ObjectRow
              key={obj.object_id}
              obj={obj}
              onSelect={onSelect}
              isChild={isStudyGroup && obj.object_id !== parentObj?.object_id}
            />
          ))}

          {remaining > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); onLoadMore(); }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#1a73e8'; e.currentTarget.style.color = '#1a73e8'; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#dadce0'; e.currentTarget.style.color = '#5f6368'; }}
              style={{
                marginTop: 2, padding: '9px 0', background: 'none',
                border: '1px dashed #dadce0', borderRadius: 8,
                fontSize: 13, color: '#5f6368', cursor: 'pointer', width: '100%',
                transition: 'border-color 0.15s, color 0.15s',
              }}
            >
              Load {Math.min(PAGE_SIZE, remaining)} more
              <span style={{ color: '#bdc1c6', marginLeft: 6, fontSize: 12 }}>
                ({remaining} remaining)
              </span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── ObjectSelector ────────────────────────────────────────────────────
function ObjectSelector({ onSelect }) {
  const [allObjects, setAllObjects]   = useState([]);
  const [loading, setLoading]         = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [search, setSearch]           = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [typeFilter, setTypeFilter]   = useState('all');
  const [groupMode, setGroupMode]     = useState('study');
  const [groupPages, setGroupPages]   = useState({});
  const [serverPage, setServerPage]   = useState(1);
  const [serverTotal, setServerTotal] = useState(null);
  const [hasMore, setHasMore]         = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 400);
    return () => clearTimeout(t);
  }, [searchInput]);

  const fetchPage = useCallback((page, currentSearch, currentType, replace = false) => {
    if (USE_MOCK) {
      setAllObjects(Object.values(MOCK_REGISTRY));
      setLoading(false);
      return;
    }

    page === 1 ? setLoading(true) : setLoadingMore(true);

    const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
    if (currentSearch) params.set('search', currentSearch);
    if (currentType && currentType !== 'all') params.set('type', currentType);

    fetch(`${BASE_URL}/api/dev/objects/?${params}`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((data) => {
        const incoming = Array.isArray(data.objects) ? data.objects
          : Array.isArray(data) ? data
          : data?.results ?? [];
        setAllObjects((prev) => replace ? incoming : [...prev, ...incoming]);
        setServerTotal(data.count ?? null);
        setHasMore(data.has_next ?? false);
        setServerPage(page);
      })
      .catch(() => { if (replace) setAllObjects(Object.values(MOCK_REGISTRY)); })
      .finally(() => { setLoading(false); setLoadingMore(false); });
  }, []);

  useEffect(() => {
    setGroupPages({});
    fetchPage(1, search, typeFilter, true);
  }, [search, typeFilter, fetchPage]);

  const handleLoadMoreFromServer = useCallback(() => {
    if (!loadingMore && hasMore) fetchPage(serverPage + 1, search, typeFilter, false);
  }, [loadingMore, hasMore, serverPage, search, typeFilter, fetchPage]);

  const groups = useMemo(() => buildGroups(allObjects, groupMode), [allObjects, groupMode]);

  const types = useMemo(
    () => ['all', ...Array.from(new Set(allObjects.map((o) => o.object_type))).sort()],
    [allObjects]
  );

  const getPage = useCallback((key) => groupPages[key] || 1, [groupPages]);
  const loadMoreGroup = useCallback((key) => {
    setGroupPages((prev) => ({ ...prev, [key]: (prev[key] || 1) + 1 }));
  }, []);

  useEffect(() => { setGroupPages({}); }, [search, typeFilter, groupMode]);

  const totalShown = groups.reduce(
    (sum, g) => sum + Math.min(g.objects.length, getPage(g.groupKey) * PAGE_SIZE), 0
  );

  return (
    <div style={{ maxWidth: 700, margin: '0 auto', padding: '0 16px 60px' }}>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '20px 0', borderBottom: '1px solid #e8eaed', marginBottom: 20,
      }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 20, color: '#1a73e8', letterSpacing: '-0.3px' }}>
            OmniBioAI SDK
          </div>
          <div style={{ fontSize: 12, color: '#80868b', marginTop: 2 }}>Analysis Launcher</div>
        </div>
        <div style={{ fontSize: 12, color: '#80868b', textAlign: 'right' }}>
          {serverTotal !== null
            ? <div>{serverTotal} objects in registry</div>
            : <div>{allObjects.length} loaded</div>}
          {totalShown < allObjects.length && (
            <div style={{ marginTop: 2, color: '#bdc1c6' }}>showing {totalShown} of {allObjects.length}</div>
          )}
        </div>
      </header>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Search by name, type, or ID…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          style={{
            flex: 1, minWidth: 180, height: 36, padding: '0 12px', borderRadius: 8,
            border: '1px solid #dadce0', fontSize: 13, color: '#3c4043',
            outline: 'none', background: '#fff',
          }}
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          style={{
            height: 36, padding: '0 10px', borderRadius: 8,
            border: '1px solid #dadce0', fontSize: 13, color: '#3c4043',
            background: '#fff', cursor: 'pointer', minWidth: 140,
          }}
        >
          {types.map((t) => (
            <option key={t} value={t}>{t === 'all' ? 'All types' : t}</option>
          ))}
        </select>

        <div style={{ display: 'flex', border: '1px solid #dadce0', borderRadius: 8, overflow: 'hidden', height: 36 }}>
          {[
            { key: 'study', label: 'By study' },
            { key: 'type',  label: 'By type'  },
            { key: 'flat',  label: 'Flat'      },
          ].map(({ key, label }, i, arr) => (
            <button
              key={key}
              onClick={() => setGroupMode(key)}
              style={{
                padding: '0 12px', border: 'none',
                borderRight: i < arr.length - 1 ? '1px solid #dadce0' : 'none',
                cursor: 'pointer', fontSize: 12,
                fontWeight: groupMode === key ? 600 : 400,
                background: groupMode === key ? '#e8f0fe' : '#fff',
                color: groupMode === key ? '#1a73e8' : '#5f6368',
                transition: 'background 0.15s, color 0.15s',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '48px 0', color: '#9aa0a6', fontSize: 14 }}>
          Loading objects…
        </div>
      )}

      {!loading && allObjects.length === 0 && (
        <div style={{
          textAlign: 'center', padding: '48px 0', color: '#9aa0a6', fontSize: 14,
          background: '#f8f9fa', borderRadius: 12, border: '1px dashed #dadce0',
        }}>
          No objects match your search.
        </div>
      )}

      {!loading && groups.map((group) => (
        <GroupSection
          key={group.groupKey}
          group={group}
          onSelect={onSelect}
          groupMode={groupMode}
          page={getPage(group.groupKey)}
          onLoadMore={() => loadMoreGroup(group.groupKey)}
        />
      ))}

      {!loading && hasMore && (
        <button
          onClick={handleLoadMoreFromServer}
          disabled={loadingMore}
          onMouseEnter={(e) => { if (!loadingMore) { e.currentTarget.style.borderColor = '#1a73e8'; e.currentTarget.style.color = '#1a73e8'; }}}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#dadce0'; e.currentTarget.style.color = '#5f6368'; }}
          style={{
            marginTop: 16, padding: '11px 0', background: 'none',
            border: '1px dashed #dadce0', borderRadius: 8,
            fontSize: 13, color: '#5f6368', cursor: loadingMore ? 'default' : 'pointer',
            width: '100%', transition: 'border-color 0.15s, color 0.15s',
            opacity: loadingMore ? 0.6 : 1,
          }}
        >
          {loadingMore ? 'Loading…' : `Load next ${PAGE_SIZE} objects`}
          {!loadingMore && serverTotal !== null && (
            <span style={{ color: '#bdc1c6', marginLeft: 6, fontSize: 12 }}>
              ({serverTotal - allObjects.length} remaining on server)
            </span>
          )}
        </button>
      )}
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────
function App() {
  const params = new URLSearchParams(window.location.search);
  const urlObjectId = params.get('object_id');

  const [selectedObject, setSelectedObject] = useState(null);
  const [obj, setObj] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState(null);
  const [selected, setSelected] = useState('notebook');
  const [toast, setToast] = useState(null);
  const [modal, setModal] = useState(null);

  const objectId = urlObjectId || selectedObject?.object_id || null;

  useEffect(() => {
    if (!objectId) return;
    if (selectedObject?.object_id === objectId) { setObj(selectedObject); return; }
    if (shouldUseMock(objectId)) { setObj(MOCK_OBJECT); return; }

    setLoading(true);
    setFetchError(null);
    fetch(`${BASE_URL}/api/dev/objects/${objectId}/`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((data) => {
        const empty = !data || data.count === 0 || (Array.isArray(data) && !data.length);
        setObj(empty ? MOCK_OBJECT : data);
        setLoading(false);
      })
      .catch((err) => { setFetchError(err.message); setLoading(false); });
  }, [objectId, selectedObject]);

  const showToast = (msg) => { setToast(null); setTimeout(() => setToast(msg), 10); };

  const notebookUrl = `${JUPYTER_BASE}/lab?token=${JUPYTER_TOKEN}&omnibioai_object_id=${objectId}`;

  const pythonSnippet =
    `export OMNIBIOAI_OBJECT_ID="${objectId}"\n` +
    `export OMNIBIOAI_BASE_URL="${BASE_URL}"\n` +
    `export OMNIBIOAI_TOKEN="${TOKEN}"\n\n` +
    `# Paste in terminal, then:\n` +
    `from omnibioai_sdk import OmniClient\nimport os\n` +
    `c = OmniClient()\n` +
    `obj = c.object_get(os.environ["OMNIBIOAI_OBJECT_ID"])\n` +
    `print(obj["object_type"], obj["metadata"])`;

  const buildRScript = () => {
    const name = obj?.name || obj?.object_type || 'Unknown';
    const objectType = obj?.object_type || 'Unknown';
    return (
      `# OmniBioAI — auto-generated starter script\n# Object: ${name}\n# Type:   ${objectType}\n# ID:     ${objectId}\n\n` +
      `Sys.setenv(\n  OMNIBIOAI_OBJECT_ID = "${objectId}",\n  OMNIBIOAI_BASE_URL  = "${BASE_URL}",\n  OMNIBIOAI_TOKEN     = "${TOKEN}"\n)\n\n` +
      `library(httr2)\n\nobj <- request(Sys.getenv("OMNIBIOAI_BASE_URL")) |>\n` +
      `  req_url_path(paste0("/api/dev/objects/", Sys.getenv("OMNIBIOAI_OBJECT_ID"), "/")) |>\n` +
      `  req_headers(Authorization = paste("Bearer", Sys.getenv("OMNIBIOAI_TOKEN"))) |>\n` +
      `  req_perform() |>\n  resp_body_json()\n\ncat("Loaded:", obj$object_type, "\\n")\nprint(obj$metadata)\n`
    );
  };

  const downloadRScript = () => {
    const blob = new Blob([buildRScript()], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement('a'), {
      href: url, download: `omnibioai_${(objectId || '').slice(0, 8)}.R`,
    });
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
  };

  const handleAction = (type) => {
    if (type === 'notebook') {
      // Open JupyterLab with object ID in the URL
      window.open(notebookUrl, '_blank');

    } else if (type === 'python') {
      // Copy env vars to clipboard — paste in any terminal
      navigator.clipboard.writeText(pythonSnippet)
        .then(() => showToast('Env vars copied — paste in your terminal'))
        .catch(() => showToast('Copy failed — check browser clipboard permissions'));

    } else if (type === 'r') {
      // Download R script, then ask Django to open RStudio server-side
      downloadRScript();
      fetch(`${BASE_URL}/api/dev/launch/rstudio/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}` },
        body: JSON.stringify({ object_id: objectId }),
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.ok) {
            showToast('RStudio launched with R script');
          } else {
            showToast('R script downloaded — open it manually in RStudio');
          }
        })
        .catch(() => showToast('R script downloaded — open it manually in RStudio'));
    }
  };

  const handleCardClick = (type) => { setSelected(type); handleAction(type); };

  if (!objectId) {
    return (
      <div className="app">
        <ObjectSelector onSelect={(o) => setSelectedObject(o)} />
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {!urlObjectId && (
            <button
              onClick={() => { setSelectedObject(null); setObj(null); setFetchError(null); }}
              style={{
                background: 'none', border: '1px solid #dadce0', borderRadius: 6,
                padding: '4px 10px', fontSize: 12, color: '#5f6368', cursor: 'pointer',
              }}
            >
              ← Back
            </button>
          )}
          <span className="logo">OmniBioAI</span>
        </div>
        {obj && <span className="type-badge">{obj.object_type}</span>}
      </header>

      {loading && <div className="spinner-wrap"><div className="spinner" /></div>}
      {fetchError && <div className="error-card">Error loading object: {fetchError}</div>}

      {obj && (
        <>
          <ObjectCard obj={obj} objectId={objectId} />
          <div className="section-label">Open in environment</div>
          <div className="env-grid">
            <EnvCard type="notebook" title="Notebook"
              description="JupyterLab with object context preloaded"
              selected={selected === 'notebook'} onClick={() => handleCardClick('notebook')} />
            <EnvCard type="python" title="Python"
              description="Copy env vars — paste in any terminal"
              selected={selected === 'python'} onClick={() => handleCardClick('python')} />
            <EnvCard type="r" title="R / RStudio"
              description="Download R script + launch RStudio"
              selected={selected === 'r'} onClick={() => handleCardClick('r')} />
          </div>
          <button className="launch-btn" onClick={() => handleAction(selected)}>
            {LAUNCH_LABELS[selected]}
          </button>
        </>
      )}

      {toast && <Toast key={toast + Date.now()} message={toast} />}
      {modal && <InstallModal type={modal} onDismiss={() => setModal(null)} />}
    </div>
  );
}

export default App;
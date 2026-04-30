import React, { useState, useEffect } from 'react';
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

const MOCK_OBJECT = {
  object_id: 'test-1234-abcd-5678',
  name: 'TCGA-BRCA RNAseq cohort 2024',
  object_type: 'RNASeqObject',
  metadata: {
    samples: 1247,
    genome: 'hg38',
    platform: 'Illumina NovaSeq',
    created_by: 'manish',
  },
};

const shouldUseMock = (objectId) => USE_MOCK || objectId === 'test';

function tryOpenWithDetection(url, onSuccess, onFail) {
  let didBlur = false;

  const onBlur = () => { didBlur = true; };
  const onVisChange = () => { if (document.visibilityState === 'hidden') didBlur = true; };

  window.addEventListener('blur', onBlur);
  document.addEventListener('visibilitychange', onVisChange);

  window.open(url, '_blank');

  setTimeout(() => {
    window.removeEventListener('blur', onBlur);
    document.removeEventListener('visibilitychange', onVisChange);
    if (didBlur) {
      onSuccess();
    } else {
      onFail();
    }
  }, 2000);
}

const LAUNCH_LABELS = {
  notebook: 'Open in JupyterLab',
  python: 'Copy env vars + open VS Code',
  r: 'Download R script',
};

function App() {
  const params = new URLSearchParams(window.location.search);
  const objectId = params.get('object_id');

  const [obj, setObj] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState(null);
  const [selected, setSelected] = useState('notebook');
  const [toast, setToast] = useState(null);
  const [modal, setModal] = useState(null);

  useEffect(() => {
    if (!objectId) return;

    if (shouldUseMock(objectId)) {
      setObj(MOCK_OBJECT);
      return;
    }

    setLoading(true);
    setFetchError(null);
    fetch(`${BASE_URL}/api/dev/objects/${objectId}/`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        const empty = !data || data.count === 0 || (Array.isArray(data) && data.length === 0);
        setObj(empty ? MOCK_OBJECT : data);
        setLoading(false);
      })
      .catch((err) => {
        setFetchError(err.message);
        setLoading(false);
      });
  }, [objectId]);

  const showToast = (msg) => {
    setToast(null);
    setTimeout(() => setToast(msg), 10);
  };

  const notebookUrl = `${JUPYTER_BASE}/lab?token=${JUPYTER_TOKEN}&omnibioai_object_id=${objectId}`;

  const pythonSnippet =
    `export OMNIBIOAI_OBJECT_ID="${objectId}"\n` +
    `export OMNIBIOAI_BASE_URL="${BASE_URL}"\n` +
    `export OMNIBIOAI_TOKEN="${TOKEN}"\n` +
    `\n` +
    `# Paste in terminal, then:\n` +
    `from omnibioai_sdk import OmniClient\n` +
    `import os\n` +
    `c = OmniClient()\n` +
    `obj = c.object_get(os.environ["OMNIBIOAI_OBJECT_ID"])\n` +
    `print(obj["object_type"], obj["metadata"])`;

  const buildRScript = () => {
    const name = (obj && (obj.name || obj.object_type)) || 'Unknown';
    const objectType = (obj && obj.object_type) || 'Unknown';
    return (
      `# OmniBioAI — auto-generated starter script\n` +
      `# Object: ${name}\n` +
      `# Type:   ${objectType}\n` +
      `# ID:     ${objectId}\n` +
      `\n` +
      `Sys.setenv(\n` +
      `  OMNIBIOAI_OBJECT_ID = "${objectId}",\n` +
      `  OMNIBIOAI_BASE_URL  = "${BASE_URL}",\n` +
      `  OMNIBIOAI_TOKEN     = "${TOKEN}"\n` +
      `)\n` +
      `\n` +
      `library(httr2)\n` +
      `\n` +
      `obj <- request(Sys.getenv("OMNIBIOAI_BASE_URL")) |>\n` +
      `  req_url_path(paste0("/api/dev/objects/", Sys.getenv("OMNIBIOAI_OBJECT_ID"), "/")) |>\n` +
      `  req_headers(Authorization = paste("Bearer", Sys.getenv("OMNIBIOAI_TOKEN"))) |>\n` +
      `  req_perform() |>\n` +
      `  resp_body_json()\n` +
      `\n` +
      `cat("Loaded:", obj$object_type, "\\n")\n` +
      `print(obj$metadata)\n`
    );
  };

  const downloadRScript = () => {
    const script = buildRScript();
    const blob = new Blob([script], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `omnibioai_${(objectId || '').slice(0, 8)}.R`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleAction = (type) => {
    if (type === 'notebook') {
      window.open(notebookUrl, '_blank');
    } else if (type === 'python') {
      navigator.clipboard.writeText(pythonSnippet).catch(() => {});
      tryOpenWithDetection(
        'vscode://',
        () => showToast('Copied to clipboard — paste in your VS Code terminal'),
        () => setModal('vscode'),
      );
    } else if (type === 'r') {
      downloadRScript();
      tryOpenWithDetection(
        'rstudio://',
        () => showToast('R script downloaded — open it in RStudio'),
        () => setModal('rstudio'),
      );
    }
  };

  const handleCardClick = (type) => {
    setSelected(type);
    handleAction(type);
  };

  if (!objectId) {
    return (
      <div className="app">
        <header className="header">
          <div className="logo-wrap">
            <span className="logo">OmniBioAI SDK</span>
            <span className="logo-subtitle">Analysis Launcher</span>
          </div>
        </header>
        <div className="error-card">
          No object selected — open this launcher from the OmniBioAI platform with an object_id parameter
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <span className="logo">OmniBioAI</span>
        {obj && <span className="type-badge">{obj.object_type}</span>}
      </header>

      {loading && (
        <div className="spinner-wrap">
          <div className="spinner" />
        </div>
      )}

      {fetchError && (
        <div className="error-card">Error loading object: {fetchError}</div>
      )}

      {obj && (
        <>
          <ObjectCard obj={obj} objectId={objectId} />

          <div className="section-label">Open in environment</div>

          <div className="env-grid">
            <EnvCard
              type="notebook"
              title="Notebook"
              description="JupyterLab with object context preloaded"
              selected={selected === 'notebook'}
              onClick={() => handleCardClick('notebook')}
            />
            <EnvCard
              type="python"
              title="Python"
              description="VS Code with object ID ready in terminal"
              selected={selected === 'python'}
              onClick={() => handleCardClick('python')}
            />
            <EnvCard
              type="r"
              title="R / RStudio"
              description="Starter script downloaded, open in RStudio"
              selected={selected === 'r'}
              onClick={() => handleCardClick('r')}
            />
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

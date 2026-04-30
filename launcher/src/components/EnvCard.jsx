import React from 'react';

const ICON_BG = {
  notebook: '#fff7ed',
  python: '#eff6ff',
  r: '#f0fdf4',
};

function NotebookIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="2" width="14" height="18" rx="2" stroke="#ea580c" strokeWidth="1.5" />
      <line x1="6" y1="7" x2="14" y2="7" stroke="#ea580c" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="6" y1="11" x2="14" y2="11" stroke="#ea580c" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="6" y1="15" x2="10" y2="15" stroke="#ea580c" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function PythonIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M11 2C8.2 2 7 3.2 7 5v2h4v1H5C3.3 8 2 9.3 2 11c0 1.7 1.3 3 3 3h2v-2c0-1.7 1.2-3 4-3h4c1.7 0 3-1.3 3-3V5c0-1.8-1.2-3-4-3h-3z"
        fill="#3b82f6"
      />
      <circle cx="9" cy="4.5" r="1" fill="white" />
      <path
        d="M11 20c2.8 0 4-1.2 4-3v-2h-4v-1h6c1.7 0 3-1.3 3-3 0-1.7-1.3-3-3-3h-2v2c0 1.7-1.2 3-4 3H7c-1.7 0-3 1.3-3 3v2c0 1.8 1.2 3 4 3h3z"
        fill="#60a5fa"
      />
      <circle cx="13" cy="17.5" r="1" fill="white" />
    </svg>
  );
}

function RIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" xmlns="http://www.w3.org/2000/svg">
      <text x="3" y="17" fontFamily="serif" fontSize="18" fontWeight="bold" fill="#16a34a">R</text>
    </svg>
  );
}

const ICONS = {
  notebook: <NotebookIcon />,
  python: <PythonIcon />,
  r: <RIcon />,
};

function EnvCard({ type, title, description, selected, onClick }) {
  return (
    <div
      className={`env-card${selected ? ' env-card--selected' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <div className="env-icon" style={{ background: ICON_BG[type] }}>
        {ICONS[type]}
      </div>
      <div className="env-title">{title}</div>
      <div className="env-desc">{description}</div>
      <span className="env-badge">Ready</span>
    </div>
  );
}

export default EnvCard;

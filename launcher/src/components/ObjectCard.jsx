import React from 'react';

function ObjectCard({ obj, objectId }) {
  const metadata = obj.metadata || {};
  const entries = Object.entries(metadata);

  return (
    <div className="object-card">
      <div className="object-name">{obj.name || obj.object_type || 'Object'}</div>
      <div className="object-id">{objectId}</div>
      {entries.length > 0 && (
        <>
          <div className="divider" />
          <div className="metadata-grid">
            {entries.map(([key, value]) => (
              <React.Fragment key={key}>
                <div className="meta-key">{key}</div>
                <div className="meta-value">{String(value)}</div>
              </React.Fragment>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default ObjectCard;

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PatientDetail, TimelineCluster } from "../api";

export default function ClusteredTimeline({ patient }: { patient: PatientDetail }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const first = patient.clusters[0];
    if (first) setOpen({ [first.title]: true });
  }, [patient.id, patient.clusters]);

  function toggle(title: string) {
    setOpen((current) => ({ ...current, [title]: !current[title] }));
  }

  return (
    <div>
      {patient.clusters.length === 0 && <p className="muted">No documents on this timeline yet.</p>}
      {patient.clusters.map((cluster) => (
        <ClusterCard
          key={cluster.title}
          cluster={cluster}
          expanded={Boolean(open[cluster.title])}
          onToggle={() => toggle(cluster.title)}
        />
      ))}
    </div>
  );
}

function ClusterCard({
  cluster,
  expanded,
  onToggle,
}: {
  cluster: TimelineCluster;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="card cluster">
      <button type="button" className="cluster-head" onClick={onToggle}>
        <span>
          <strong>{cluster.title}</strong>
          <span className="badge">{cluster.document_count} record{cluster.document_count === 1 ? "" : "s"}</span>
          <span className="badge">{cluster.type_label}</span>
        </span>
        <span className="muted">{expanded ? "Hide" : "Show"}</span>
      </button>
      <p className="muted cluster-desc">{cluster.description}</p>
      {expanded &&
        cluster.documents.map((item) => (
          <div className="cluster-item" key={item.document_id}>
            <div>
              <span className="badge">{(item.document_type || "document").replace(/_/g, " ")}</span>{" "}
              <Link to={`/documents/${item.document_id}`}>{item.filename}</Link>
              {item.needs_review && <span className="badge warn">review</span>}
            </div>
            {item.summary && (
              <ul>
                {item.summary.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
    </div>
  );
}

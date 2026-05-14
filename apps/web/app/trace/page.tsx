import { Suspense } from "react";
import { TraceViewer } from "./trace-viewer";

export default function TracePage() {
  return (
    <Suspense fallback={<TraceViewerFallback />}>
      <TraceViewer />
    </Suspense>
  );
}

function TraceViewerFallback() {
  return (
    <section className="page traceViewerPage">
      <div className="header">
        <div>
          <p className="eyebrow">Runtime evidence</p>
          <h1>Trace Viewer</h1>
          <p>Loading runtime trace controls.</p>
        </div>
      </div>
    </section>
  );
}

const LINES = [
  { tag: "AUTH", text: "session handshake ready", warn: false },
  { tag: "MAIL", text: "inbox sync idle, awaiting login", warn: false },
  { tag: "SEC", text: "token store encrypted at rest", warn: false },
  { tag: "AUTH", text: "no active sessions", warn: true },
  { tag: "MAIL", text: "queue empty", warn: false },
];

function timestamp() {
  return new Date().toTimeString().slice(0, 8);
}

export default function ActivityRail() {
  return (
    <div className="rail">
      <div className="rail-heading">Agent activity</div>
      <div className="rail-log">
        {LINES.map((line, i) => (
          <div
            key={line.tag + i}
            className={`rail-line${line.warn ? " warn" : ""}`}
            style={{ animationDelay: `${i * 0.12}s` }}
          >
            <span className="ts">{timestamp()}</span>
            <span className="tag">{line.tag}</span>
            <span>{line.text}</span>
          </div>
        ))}
      </div>
      <div className="rail-status">
        <span className="pulse-dot" /> Listening for new sessions
      </div>
    </div>
  );
}

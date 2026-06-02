const POLL_INTERVAL_MS = Number(import.meta.env.VITE_POLL_INTERVAL_MS) || 4000;

export default function App() {
  return (
    <div>
      <p>{`Test: ${POLL_INTERVAL_MS}`}</p>
    </div>
  );
}
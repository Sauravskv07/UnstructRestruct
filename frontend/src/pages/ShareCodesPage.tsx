import { useEffect, useState } from "react";
import { api } from "../api";

type CodeInfo = {
  code: string;
  created_at: string;
  expires_at: string;
  revoked: boolean;
  expired: boolean;
};

export default function ShareCodesPage() {
  const [code, setCode] = useState<CodeInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api<{ code: CodeInfo | null }>("/me/share-code")
      .then((result) => setCode(result.code))
      .catch((err: Error) => setError(err.message));
  }

  useEffect(() => {
    load();
  }, []);

  async function generate() {
    setError(null);
    try {
      const result = await api<{ code: CodeInfo }>("/me/share-code", { method: "POST" });
      setCode(result.code);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not generate code");
    }
  }

  async function revoke() {
    setError(null);
    try {
      await api("/me/share-code/revoke", { method: "POST" });
      setCode(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not revoke");
    }
  }

  return (
    <div>
      <h1>Share access</h1>
      <p className="muted">
        Give this code to a clinician together with your username. It expires 24 hours after it is created.
        Generating a new code expires the old one and removes current clinician access.
      </p>
      <div className="card">
        {code && !code.expired ? (
          <>
            <p className="share-code">{code.code}</p>
            <p className="muted">Expires {new Date(code.expires_at).toLocaleString()}</p>
          </>
        ) : (
          <p className="muted">No active code.</p>
        )}
        <button type="button" onClick={() => void generate()}>
          Generate code
        </button>{" "}
        <button type="button" className="secondary" onClick={() => void revoke()} disabled={!code || code.expired}>
          Revoke
        </button>
        {error && <p className="badge err">{error}</p>}
      </div>
    </div>
  );
}

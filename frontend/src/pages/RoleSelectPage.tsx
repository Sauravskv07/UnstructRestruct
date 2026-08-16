import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { clearSession } from "../session";

export default function RoleSelectPage() {
  const navigate = useNavigate();
  const [choice, setChoice] = useState<"patient" | "clinician" | "">("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    clearSession();
    if (choice === "patient") navigate("/patient");
    if (choice === "clinician") navigate("/clinician/login");
  }

  return (
    <div>
      <h1>Who is using this?</h1>
      <p className="muted">
        Patients see only their own records and can share a 24-hour code with a clinician.
        Clinicians sign in with their ID and only see patients who have shared that code.
      </p>
      <form className="card" onSubmit={onSubmit}>
        <label className="choice">
          <input
            type="radio"
            name="role"
            checked={choice === "patient"}
            onChange={() => setChoice("patient")}
          />
          <span>
            <strong>I am a patient</strong>
            <div className="muted">View my records and manage sharing codes.</div>
          </span>
        </label>
        <label className="choice">
          <input
            type="radio"
            name="role"
            checked={choice === "clinician"}
            onChange={() => setChoice("clinician")}
          />
          <span>
            <strong>I am a healthcare professional</strong>
            <div className="muted">Sign in with your clinician ID, then add patients by share code.</div>
          </span>
        </label>
        <button type="submit" disabled={!choice} style={{ marginTop: 12 }}>
          Continue
        </button>
      </form>
    </div>
  );
}

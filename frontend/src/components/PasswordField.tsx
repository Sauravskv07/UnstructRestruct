import { useState } from "react";

type Props = {
  name?: string;
  defaultValue?: string;
  required?: boolean;
};

export default function PasswordField({ name = "password", defaultValue, required }: Props) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="password-field">
      <input
        name={name}
        type={visible ? "text" : "password"}
        defaultValue={defaultValue}
        required={required}
        autoComplete="current-password"
      />
      <button
        type="button"
        className="password-toggle"
        onClick={() => setVisible((value) => !value)}
        aria-label={visible ? "Hide password" : "Show password"}
        title={visible ? "Hide password" : "Show password"}
      >
        {visible ? (
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              d="M3 3l18 18M10.6 10.6A2 2 0 0012 14a2 2 0 001.4-.6M9.9 5.2A9.8 9.8 0 0112 5c5 0 9.3 3.1 11 7.5a11.6 11.6 0 01-4.2 4.8M6.1 6.1A11.6 11.6 0 001 12.5C2.7 16.9 7 20 12 20c1.6 0 3.1-.3 4.5-.9"
            />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              d="M1 12.5C2.7 8.1 7 5 12 5s9.3 3.1 11 7.5C21.3 16.9 17 20 12 20S2.7 16.9 1 12.5z"
            />
            <circle cx="12" cy="12.5" r="3" fill="none" stroke="currentColor" strokeWidth="2" />
          </svg>
        )}
      </button>
    </div>
  );
}

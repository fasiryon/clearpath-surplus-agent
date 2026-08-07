"use client";

import { FormEvent, useRef, useState } from "react";

type FormState = "idle" | "submitting" | "success" | "error";

export function IntakeForm() {
  const [state, setState] = useState<FormState>("idle");
  const [message, setMessage] = useState("");
  const startedAt = useRef(Date.now());

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("submitting");
    setMessage("");

    const form = event.currentTarget;
    const body = Object.fromEntries(new FormData(form).entries());
    body.startedAt = String(startedAt.current);

    try {
      const response = await fetch("/api/intake", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = (await response.json()) as { message?: string };

      if (!response.ok) throw new Error(result.message || "We could not send your request.");

      form.reset();
      setState("success");
      setMessage(result.message || "Your request was received.");
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Something went wrong. Please try again.");
    }
  }

  if (state === "success") {
    return (
      <div className="form-success" role="status">
        <div className="success-check" aria-hidden="true">✓</div>
        <p className="eyebrow">Request received</p>
        <h3>We’ll review the public record.</h3>
        <p>{message}</p>
        <p className="muted">You do not need to send a Social Security number, bank information, or payment.</p>
        <button
          className="text-button"
          type="button"
          onClick={() => {
            startedAt.current = Date.now();
            setState("idle");
          }}
        >
          Submit another request
        </button>
      </div>
    );
  }

  return (
    <form className="intake-form" onSubmit={submit} noValidate>
      <div className="field-grid two-columns">
        <label>
          Full name <span aria-hidden="true">*</span>
          <input name="fullName" autoComplete="name" maxLength={120} required />
        </label>
        <label>
          Preferred contact
          <select name="contactPreference" defaultValue="phone">
            <option value="phone">Phone call</option>
            <option value="email">Email</option>
          </select>
        </label>
      </div>

      <div className="field-grid two-columns">
        <label>
          Phone number
          <input name="phone" type="tel" autoComplete="tel" inputMode="tel" maxLength={30} />
        </label>
        <label>
          Email address
          <input name="email" type="email" autoComplete="email" maxLength={254} />
        </label>
      </div>
      <p className="field-hint">Please provide at least one way to reach you.</p>

      <label>
        Foreclosed property address <span aria-hidden="true">*</span>
        <input
          name="propertyAddress"
          autoComplete="street-address"
          placeholder="Street address, city, state, ZIP"
          maxLength={300}
          required
        />
      </label>

      <div className="field-grid two-columns">
        <label>
          Maryland county or city
          <select name="county" defaultValue="">
            <option value="">Select if known</option>
            <option>Baltimore City</option>
            <option>Baltimore County</option>
            <option>Anne Arundel County</option>
            <option>Carroll County</option>
            <option>Harford County</option>
            <option>Howard County</option>
            <option>Montgomery County</option>
            <option>Prince George&apos;s County</option>
            <option value="Other Maryland jurisdiction">Other Maryland jurisdiction</option>
          </select>
        </label>
        <label>
          Court case number
          <input name="caseNumber" placeholder="If known" maxLength={80} />
        </label>
      </div>

      <label>
        Anything else we should know?
        <textarea name="notes" rows={3} maxLength={1200} placeholder="Optional" />
      </label>

      <label className="checkbox-label">
        <input name="consent" type="checkbox" value="yes" required />
        <span>
          I agree that ClearPath Surplus Solutions may contact me by phone or email about this request. I understand this is not legal advice and I am not hiring ClearPath by submitting this form.
        </span>
      </label>

      <label className="honeypot" aria-hidden="true">
        Leave this field empty
        <input name="website" tabIndex={-1} autoComplete="off" />
      </label>

      {state === "error" && <p className="form-error" role="alert">{message}</p>}

      <button className="button button-primary form-submit" type="submit" disabled={state === "submitting"}>
        {state === "submitting" ? "Sending securely…" : "Request my free case review"}
        {state !== "submitting" && <span aria-hidden="true">→</span>}
      </button>
      <p className="form-fine-print">
        No obligation. Do not submit Social Security numbers, banking details, or identity documents here.
      </p>
    </form>
  );
}

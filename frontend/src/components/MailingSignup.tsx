import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "@/lib/api";

export default function MailingSignup() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage("");
    setError("");
    setSubmitting(true);
    try {
      const result = await api.subscribe(email);
      setMessage(result.status === "already_subscribed" ? "You are already on the list." : "You are on the list. We will email urgent circular alerts.");
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not complete your signup.");
    } finally {
      setSubmitting(false);
    }
  };

  return <section className="mailing-signup" aria-labelledby="mailing-signup-title">
    <div><p className="eyebrow">Stay informed</p><h2 id="mailing-signup-title">Important circulars, in your inbox.</h2><p>Get alerts when urgent government circulars are published. No noise, just notices that matter.</p></div>
    <form onSubmit={submit} className="mailing-form">
      <label><span className="sr-only">Email address</span><input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></label>
      <button className="button primary" type="submit" disabled={submitting}>{submitting ? "Joining..." : "Join the list"}</button>
    </form>
    {message && <p className="mailing-message">{message}</p>}
    {error && <p className="mailing-error" role="alert">{error}</p>}
  </section>;
}
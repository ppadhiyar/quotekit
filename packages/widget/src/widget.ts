/**
 * QuoteKit "Website Brain" widget.
 *
 * Customer embed:
 *   <script src="https://cdn.example.com/widget.js"
 *           data-api="https://api.example.com"
 *           data-tenant="acme"></script>
 *
 * Renders a floating chat bubble; answers come from the tenant's Azure AI
 * Search index and are gated by the same groundedness check as the API.
 */

interface ChatResponse {
  answer: string;
  citations: { document: string; snippet: string }[];
  groundedness_score: number | null;
  status: "approved" | "needs_review";
}

const script = document.currentScript as HTMLScriptElement | null;
const API = script?.dataset.api ?? "http://localhost:8000";
const TENANT = script?.dataset.tenant ?? "default";

function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  style: Partial<CSSStyleDeclaration>,
  text?: string,
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  Object.assign(el.style, style);
  if (text) el.textContent = text;
  return el;
}

function mount(): void {
  const bubble = h("button", {
    position: "fixed", bottom: "20px", right: "20px", width: "56px", height: "56px",
    borderRadius: "50%", border: "none", background: "#4f8ef7", color: "#fff",
    fontSize: "24px", cursor: "pointer", zIndex: "99999",
    boxShadow: "0 4px 14px rgba(0,0,0,.25)",
  }, "💬");

  const panel = h("div", {
    position: "fixed", bottom: "88px", right: "20px", width: "340px", height: "440px",
    background: "#fff", borderRadius: "14px", boxShadow: "0 8px 30px rgba(0,0,0,.2)",
    display: "none", flexDirection: "column", overflow: "hidden", zIndex: "99999",
    fontFamily: "-apple-system, 'Segoe UI', sans-serif",
  });

  const log = h("div", { flex: "1", overflowY: "auto", padding: "12px", fontSize: "14px" });
  const form = h("form", { display: "flex", borderTop: "1px solid #eee" });
  const input = h("input", { flex: "1", border: "none", padding: "12px", fontSize: "14px", outline: "none" });
  input.placeholder = "Ask a question…";
  const send = h("button", { border: "none", background: "none", padding: "0 14px", cursor: "pointer", color: "#4f8ef7", fontWeight: "600" }, "Send");

  form.append(input, send);
  panel.append(log, form);
  document.body.append(bubble, panel);

  bubble.addEventListener("click", () => {
    panel.style.display = panel.style.display === "none" ? "flex" : "none";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    addMsg(q, true);
    const thinking = addMsg("…", false);
    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Tenant": TENANT },
        body: JSON.stringify({ question: q }),
      });
      const data = (await res.json()) as ChatResponse;
      thinking.textContent = data.answer;
      if (data.status === "needs_review") {
        thinking.textContent += " (low confidence — a human will follow up)";
      }
    } catch {
      thinking.textContent = "Sorry — something went wrong.";
    }
  });

  function addMsg(text: string, mine: boolean): HTMLElement {
    const msg = h("div", {
      margin: "6px 0", padding: "8px 12px", borderRadius: "12px", maxWidth: "85%",
      background: mine ? "#4f8ef7" : "#f1f3f7", color: mine ? "#fff" : "#1a2233",
      marginLeft: mine ? "auto" : "0",
    }, text);
    log.append(msg);
    log.scrollTop = log.scrollHeight;
    return msg;
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount);
} else {
  mount();
}

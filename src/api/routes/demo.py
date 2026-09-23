from __future__ import annotations

from secrets import compare_digest

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.shared.configuration import get_settings

router = APIRouter(tags=["internal-demo"])

_DEMO_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Billing Agent Internal Demo</title>
  <style>
    :root {
      --bg: #f6efe5;
      --panel: #fff9ef;
      --ink: #221a13;
      --muted: #6f6254;
      --accent: #0d6f6a;
      --accent-2: #b9672e;
      --ok: #1e7a39;
      --err: #a22929;
      --border: #dfd5c7;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Segoe UI, Tahoma, Geneva, Verdana, sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 15% 10%, #f8e7cc 0%, transparent 40%),
        radial-gradient(circle at 100% 100%, #dfefee 0%, transparent 35%),
        var(--bg);
      padding: 22px;
    }

    .container {
      max-width: 1100px;
      margin: 0 auto;
      display: grid;
      gap: 14px;
    }

    .card {
      border: 1px solid var(--border);
      border-radius: 14px;
      background: var(--panel);
      padding: 16px;
      box-shadow: 0 8px 20px rgba(34, 26, 19, 0.08);
    }

    h1 { margin: 0 0 8px; font-size: 28px; }
    h2 { margin: 0 0 10px; font-size: 18px; }
    p { margin: 0 0 10px; color: var(--muted); }

    .row {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      margin-bottom: 10px;
    }

    label {
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 13px;
    }

    input, textarea {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      background: #fff;
      color: var(--ink);
      font-size: 14px;
    }

    textarea { min-height: 74px; resize: vertical; }

    .buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 8px;
    }

    button {
      border: 0;
      border-radius: 999px;
      padding: 10px 14px;
      color: #fff;
      background: var(--accent);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
    }

    button.alt { background: var(--accent-2); }
    .status { margin-top: 10px; font-weight: 700; }
    .ok { color: var(--ok); }
    .err { color: var(--err); }

    pre {
      margin: 10px 0 0;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      background: #fbf8f3;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 360px;
      overflow: auto;
      font-size: 12px;
      line-height: 1.4;
    }
  </style>
</head>
<body>
  <div class=\"container\">
    <div class=\"card\">
      <h1>Billing Agent Internal Demo</h1>
      <p>Single-page visual demo for internal testing on this API host.</p>
      <p>Use unique request_id values for each run to avoid duplicate idempotency conflicts.</p>
    </div>

    <div class=\"card\">
      <h2>1) /api/chat</h2>
      <div class=\"row\">
        <div>
          <label for=\"chatKey\">X-API-Key</label>
          <input id=\"chatKey\" value=\"dev-write-key\" />
        </div>
        <div>
          <label for=\"chatActor\">X-Actor-Id</label>
          <input id=\"chatActor\" value=\"user-1\" />
        </div>
        <div>
          <label for=\"chatCustomer\">customer_id</label>
          <input id=\"chatCustomer\" value=\"CUST-001\" />
        </div>
      </div>
      <div class=\"row\">
        <div>
          <label for=\"chatRequestId\">request_id</label>
          <input id=\"chatRequestId\" value=\"demo-chat-1\" />
        </div>
      </div>
      <label for=\"chatMessage\">message</label>
      <textarea id=\"chatMessage\">My invoice looks too high. Please review.</textarea>

      <div class=\"buttons\">
        <button id=\"chatSend\">Send Chat</button>
        <button class=\"alt\" id=\"sApproval\">Scenario: Approval (CUST-001)</button>
        <button class=\"alt\" id=\"sNoAction\">Scenario: No Action (CUST-002)</button>
        <button class=\"alt\" id=\"sAutoCredit\">Scenario: Auto Credit (CUST-003)</button>
        <button class=\"alt\" id=\"sManual\">Scenario: Manual Investigation (CUST-004)</button>
        <button class=\"alt\" id=\"sBadKey\">Scenario: Invalid API Key</button>
      </div>

      <div id=\"chatStatus\" class=\"status\"></div>
      <pre id=\"chatOutput\">No request sent yet.</pre>
    </div>

    <div class=\"card\">
      <h2>2) /api/approvals/{approval_id}/decision</h2>
      <div class=\"row\">
        <div>
          <label for=\"approvalId\">approval_id</label>
          <input id=\"approvalId\" placeholder=\"Auto-populated after approval scenario\" />
        </div>
        <div>
          <label for=\"approvalKey\">X-API-Key</label>
          <input id=\"approvalKey\" value=\"dev-approve-key\" />
        </div>
        <div>
          <label for=\"approvalActor\">X-Actor-Id</label>
          <input id=\"approvalActor\" value=\"approver-1\" />
        </div>
      </div>
      <div class=\"row\">
        <div>
          <label for=\"approverId\">approver_id</label>
          <input id=\"approverId\" value=\"approver-1\" />
        </div>
        <div>
          <label for=\"decision\">decision (approve|reject)</label>
          <input id=\"decision\" value=\"approve\" />
        </div>
      </div>
      <div class=\"buttons\">
        <button id=\"approvalSend\">Send Approval Decision</button>
      </div>
      <div id=\"approvalStatus\" class=\"status\"></div>
      <pre id=\"approvalOutput\">No approval decision sent yet.</pre>
    </div>
  </div>

  <script>
    const byId = (id) => document.getElementById(id);

    function setStatus(node, text, ok) {
      node.textContent = text;
      node.className = "status " + (ok ? "ok" : "err");
    }

    function render(node, data) {
      node.textContent = JSON.stringify(data, null, 2);
    }

    async function chatCall(apiKey) {
      const reqBody = {
        message: byId("chatMessage").value,
        customer_id: byId("chatCustomer").value,
        request_id: byId("chatRequestId").value
      };
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey || byId("chatKey").value,
          "X-Actor-Id": byId("chatActor").value
        },
        body: JSON.stringify(reqBody)
      });
      const text = await res.text();
      let payload;
      try { payload = JSON.parse(text); } catch { payload = { raw: text }; }

      const out = {
        request: reqBody,
        status: res.status,
        response: payload,
        headers: { "x-trace-id": res.headers.get("x-trace-id") }
      };
      setStatus(byId("chatStatus"), `HTTP ${res.status}`, res.ok);
      render(byId("chatOutput"), out);

      if (payload && payload.approval_request_id) {
        byId("approvalId").value = payload.approval_request_id;
      }
      return out;
    }

    async function approvalCall() {
      const approvalId = byId("approvalId").value;
      const reqBody = {
        approver_id: byId("approverId").value,
        decision: byId("decision").value
      };
      const res = await fetch(`/api/approvals/${encodeURIComponent(approvalId)}/decision`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": byId("approvalKey").value,
          "X-Actor-Id": byId("approvalActor").value
        },
        body: JSON.stringify(reqBody)
      });
      const text = await res.text();
      let payload;
      try { payload = JSON.parse(text); } catch { payload = { raw: text }; }

      const out = {
        approval_id: approvalId,
        request: reqBody,
        status: res.status,
        response: payload,
        headers: { "x-trace-id": res.headers.get("x-trace-id") }
      };
      setStatus(byId("approvalStatus"), `HTTP ${res.status}`, res.ok);
      render(byId("approvalOutput"), out);
      return out;
    }

    function stampRequestId(prefix) {
      byId("chatRequestId").value = `${prefix}-${Date.now()}`;
    }

    byId("chatSend").onclick = () => chatCall();
    byId("approvalSend").onclick = () => approvalCall();

    byId("sApproval").onclick = async () => {
      byId("chatCustomer").value = "CUST-001";
      byId("chatMessage").value = "My invoice is higher than expected. Please review and correct.";
      stampRequestId("demo-approval");
      await chatCall();
    };

    byId("sNoAction").onclick = async () => {
      byId("chatCustomer").value = "CUST-002";
      byId("chatMessage").value = "Can you verify this bill amount?";
      stampRequestId("demo-no-action");
      await chatCall();
    };

    byId("sAutoCredit").onclick = async () => {
      byId("chatCustomer").value = "CUST-003";
      byId("chatMessage").value = "Please review overbilling for this month.";
      stampRequestId("demo-auto-credit");
      await chatCall();
    };

    byId("sManual").onclick = async () => {
      byId("chatCustomer").value = "CUST-004";
      byId("chatMessage").value = "This bill is way too high, please investigate.";
      stampRequestId("demo-manual");
      await chatCall();
    };

    byId("sBadKey").onclick = async () => {
      byId("chatCustomer").value = "CUST-001";
      byId("chatMessage").value = "Testing auth failure.";
      stampRequestId("demo-invalid-key");
      await chatCall("wrong-key");
    };
  </script>
</body>
</html>
"""


def _authorize_demo(demo_key: str) -> None:
    settings = get_settings()
    if not compare_digest(demo_key, settings.auth_admin_key):
        raise HTTPException(status_code=403, detail="Invalid demo key")


@router.get("/internal/demo", response_class=HTMLResponse)
async def internal_demo(demo_key: str = Query(..., min_length=3)) -> HTMLResponse:
    _authorize_demo(demo_key)
    return HTMLResponse(_DEMO_HTML)


@router.get("/internal/demo/runtime")
async def internal_demo_runtime(demo_key: str = Query(..., min_length=3)) -> dict[str, object]:
  _authorize_demo(demo_key)
  settings = get_settings()
  engine = create_async_engine(settings.database_url)
  try:
    async with engine.connect() as conn:
      customer_rows = (await conn.execute(text("SELECT id, status FROM customers ORDER BY id"))).fetchall()
      invoice_rows = (
        await conn.execute(
          text(
            "SELECT customer_id, total_amount, status "
            "FROM invoices ORDER BY customer_id, issued_at DESC"
          )
        )
      ).fetchall()
  finally:
    await engine.dispose()

  return {
    "database_url": settings.database_url,
    "customers": [{"id": row[0], "status": row[1]} for row in customer_rows],
    "invoices": [
      {"customer_id": row[0], "total_amount": str(row[1]), "status": row[2]}
      for row in invoice_rows
    ],
  }

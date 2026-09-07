import assert from "node:assert/strict";

import worker, { isAutomatedEmail, isPartnershipReply } from "./src/index.js";


assert.equal(await isPartnershipReply({
  sender: "new-contact@example.com",
  subject: "Re: RaidBench collaboration: free Rust planning resource",
}), true);
assert.equal(await isPartnershipReply({
  sender: "random-person@gmail.com",
  subject: "Question about my account",
}), false);
assert.equal(await isPartnershipReply({
  sender: "account@notify.raidbench.com",
  subject: "RaidBench collaboration: 1 Reddit reply ready",
}), false);
assert.equal(isAutomatedEmail({
  sender: "mailer-daemon@example.com",
  subject: "Delivery Status Notification",
}), true);
assert.equal(await isPartnershipReply({
  sender: "partner@example.com",
  subject: "Re: RaidBench collaboration: resource placement",
  autoSubmitted: "auto-generated",
}), false);

function incomingMessage(sender, subject) {
  const raw = new TextEncoder().encode([
    `From: ${sender}`,
    "To: support@raidbench.com",
    `Subject: ${subject}`,
    "Message-ID: <worker-test@example.com>",
    "Content-Type: text/plain; charset=utf-8",
    "",
    "Thanks for reaching out. We would like to discuss the resource placement.",
  ].join("\r\n"));
  const forwarded = [];
  return {
    raw,
    rawSize: raw.byteLength,
    from: sender,
    headers: new Headers({ subject, "message-id": "<worker-test@example.com>" }),
    forwarded,
    async forward(recipient) { forwarded.push(recipient); },
  };
}

async function runEmail(message) {
  const pending = [];
  const originalFetch = globalThis.fetch;
  let feishuCalls = 0;
  globalThis.fetch = async () => {
    feishuCalls += 1;
    return new Response(JSON.stringify({ code: 0, msg: "success" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    await worker.email(message, {
      FORWARD_TO_EMAIL: "owner@example.com",
      FEISHU_WEBHOOK_URL: "https://open.feishu.cn/open-apis/bot/v2/hook/test",
      FEISHU_WEBHOOK_SECRET: "test-secret",
    }, { waitUntil(value) { pending.push(value); } });
    await Promise.all(pending);
    return { forwarded: message.forwarded, feishuCalls };
  } finally {
    globalThis.fetch = originalFetch;
  }
}

const ordinary = await runEmail(incomingMessage("player@example.com", "Question about my report"));
assert.deepEqual(ordinary.forwarded, ["owner@example.com"]);
assert.equal(ordinary.feishuCalls, 0);

const partner = await runEmail(incomingMessage("editor@example.com", "Re: RaidBench collaboration: free Rust planning resource"));
assert.deepEqual(partner.forwarded, ["owner@example.com"]);
assert.equal(partner.feishuCalls, 1);

console.log("Selective partnership email notification tests passed.");

import PostalMime from "postal-mime";


const MAX_PARSE_BYTES = 2_000_000;
const MAX_SNIPPET_CHARACTERS = 1600;


function cleanText(value, limit = MAX_SNIPPET_CHARACTERS) {
  return String(value || "")
    .replace(/<[^>]+>/g, " ")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, " ")
    .replace(/\s+/g, " ")
    .replaceAll("<", "＜")
    .replaceAll(">", "＞")
    .trim()
    .slice(0, limit);
}


function senderAddress(parsed, fallback) {
  const address = parsed?.from?.address || fallback || "unknown sender";
  return cleanText(address, 240).toLowerCase();
}


function bytesToBase64(value) {
  let binary = "";
  const bytes = new Uint8Array(value);
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return btoa(binary);
}


async function sha256(value) {
  const bytes = new TextEncoder().encode(String(value || ""));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}


async function feishuSignature(timestamp, secret) {
  const encoder = new TextEncoder();
  const stringToSign = `${timestamp}\n${secret}`;
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(stringToSign),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, new Uint8Array());
  return bytesToBase64(signature);
}


async function sendFeishuAlert(env, email) {
  if (!env.FEISHU_WEBHOOK_URL || !env.FEISHU_WEBHOOK_SECRET) {
    throw new Error("Feishu email notification is not configured");
  }
  const timestamp = Math.floor(Date.now() / 1000);
  const sign = await feishuSignature(timestamp, env.FEISHU_WEBHOOK_SECRET);
  const gmailSearch = `https://mail.google.com/mail/u/0/#search/${encodeURIComponent(`from:${email.sender}`)}`;
  const content = [
    "<at id=all></at> **RaidBench 收到新邮件**",
    `**发件人：** ${email.sender}`,
    `**主题：** ${email.subject || "（无主题）"}`,
    "",
    "**正文摘要（原文）：**",
    email.snippet || "邮件没有可读取的纯文本正文，请在 Gmail 查看完整内容。",
    "",
    "请在当前 Codex 任务中告诉我“处理 RaidBench 新邮件”，我会翻译并拟好回复。",
  ].join("\n");
  const payload = {
    timestamp: String(timestamp),
    sign,
    msg_type: "interactive",
    card: {
      config: { wide_screen_mode: true },
      header: {
        template: "blue",
        title: { tag: "plain_text", content: "RaidBench 新邮件提醒" },
      },
      elements: [
        { tag: "div", text: { tag: "lark_md", content } },
        {
          tag: "action",
          actions: [{
            tag: "button",
            text: { tag: "plain_text", content: "在 Gmail 查看完整邮件" },
            type: "primary",
            url: gmailSearch,
          }],
        },
        {
          tag: "note",
          elements: [{ tag: "plain_text", content: "邮件仍会转发到原 Gmail；飞书接口接收不代表你已阅读。" }],
        },
      ],
    },
  };
  const response = await fetch(env.FEISHU_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Feishu webhook returned HTTP ${response.status}`);
  }
  const result = await response.json();
  const code = result.code ?? result.StatusCode;
  if (code !== 0) {
    throw new Error(`Feishu webhook rejected email alert with code ${code}`);
  }
}


async function parseIncomingEmail(message) {
  const fallbackSubject = cleanText(message.headers.get("subject"), 300);
  if (Number(message.rawSize || 0) > MAX_PARSE_BYTES) {
    return {
      sender: cleanText(message.from, 240).toLowerCase(),
      subject: fallbackSubject,
      snippet: "邮件正文超过自动摘要上限，请在 Gmail 查看完整内容。",
    };
  }
  const parser = new PostalMime();
  const rawEmail = new Response(message.raw);
  const parsed = await parser.parse(await rawEmail.arrayBuffer());
  return {
    sender: senderAddress(parsed, message.from),
    subject: cleanText(parsed.subject || fallbackSubject, 300),
    snippet: cleanText(parsed.text || parsed.html),
  };
}


async function recordMonitorEvent(env, message, parsed, feishuStatus) {
  if (!env.ANALYTICS) return;
  const receivedAt = new Date().toISOString();
  const messageIdentity = message.headers.get("message-id") || `${receivedAt}:${parsed.sender}:${parsed.subject}`;
  const eventId = (await sha256(messageIdentity)).slice(0, 32);
  await env.ANALYTICS.prepare(`
    INSERT OR REPLACE INTO email_monitor_events (
      id, received_at, forwarded, feishu_status, sender_hash, subject_hash
    ) VALUES (?, ?, 1, ?, ?, ?)
  `).bind(
    eventId,
    receivedAt,
    feishuStatus,
    (await sha256(parsed.sender)).slice(0, 24),
    (await sha256(parsed.subject)).slice(0, 24),
  ).run();
}


export default {
  async email(message, env, ctx) {
    let parsed;
    try {
      parsed = await parseIncomingEmail(message);
    } catch (error) {
      parsed = {
        sender: cleanText(message.from, 240).toLowerCase(),
        subject: cleanText(message.headers.get("subject"), 300),
        snippet: "邮件正文自动解析失败，请在 Gmail 查看完整内容。",
      };
      console.error("Incoming email parsing failed", error instanceof Error ? error.message : String(error));
    }
    await message.forward(env.FORWARD_TO_EMAIL);
    ctx.waitUntil(
      (async () => {
        let feishuStatus = "accepted";
        try {
          await sendFeishuAlert(env, parsed);
        } catch (error) {
          feishuStatus = "failed";
          console.error("Feishu email alert failed", error instanceof Error ? error.message : String(error));
        }
        try {
          await recordMonitorEvent(env, message, parsed, feishuStatus);
        } catch (error) {
          console.error("Email monitor audit write failed", error instanceof Error ? error.message : String(error));
        }
      })(),
    );
  },
};


export { cleanText, feishuSignature, parseIncomingEmail, recordMonitorEvent, sendFeishuAlert, sha256 };

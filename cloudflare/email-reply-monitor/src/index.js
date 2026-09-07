import PostalMime from "postal-mime";


const MAX_PARSE_BYTES = 2_000_000;
const MAX_SNIPPET_CHARACTERS = 1600;
const KNOWN_PARTNER_CONTACT_HASHES = new Set([
  "10fb22ea8dab6ce5d38306c495935f42517111061c4ab6ab295968df9ecc3ca3",
  "578369841f618369f42b3453432ea9ee4558b91e6caf32082f8369e19e2bac97",
  "6553a7833f87ff1d33fd872ef63ecff241dce9a5b0577cc389cf5aacd209b834",
  "9e3465f75051e5e9418abea2994465415a70dc8f49612a2f7b2e0a572b732316",
  "b5ed10a49cb17b723a1231d7ad2fb4e95e2a97ecbe19c6e08ac5d785e5b5ae2e",
  "e8c413b7679900f027c1cf2c04503c1f4671ca480fe681211662fd18dc50ded1",
]);
const KNOWN_PARTNER_DOMAIN_HASHES = new Set([
  "13c6323770e2716592e41ac3011f6d13a7eaa06f1f2645cb352c96c4e59a476a",
  "21d0e410590c866d4f96a55c6480a83aee7ff8ed26b5291f044725c573265c2c",
  "347b2971f3e427c3c13a495872ad420f8e22e02fbc7e2d0a0926c2844e4a131a",
  "b9cc50c8292a915cca1321f8755b284fd4af8f7c0e77e27a076c7e6cc1ff7143",
  "bada07edb7d43d148ccf0956b8fa7b367df0694cbd8bdc907eb9f9947a7ce03d",
]);
const AUTOMATED_SUBJECT_PATTERN = /delivery status|undeliver|failure notice|mail delivery|password reset|reddit repl(?:y|ies)|notification|verify your|security alert/i;
const PARTNER_SUBJECT_PATTERN = /\braidbench\b.*\b(?:partner|partnership|collaborat|widget|calculator|resource|editorial|contributor|affiliate)\b|\b(?:partner|partnership|collaborat|widget|calculator|resource|editorial|contributor|affiliate)\b.*\braidbench\b/i;


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
    "<at id=all></at> **RaidBench 收到合作邮件回复**",
    `**发件人：** ${email.sender}`,
    `**主题：** ${email.subject || "（无主题）"}`,
    "",
    "**正文摘要（原文）：**",
    email.snippet || "邮件没有可读取的纯文本正文，请在 Gmail 查看完整内容。",
    "",
    "请在当前 Codex 任务中告诉我“处理 RaidBench 合作回复”，我会翻译、判断合作意图并拟好英文回复。",
  ].join("\n");
  const payload = {
    timestamp: String(timestamp),
    sign,
    msg_type: "interactive",
    card: {
      config: { wide_screen_mode: true },
      header: {
        template: "blue",
        title: { tag: "plain_text", content: "RaidBench 合作邮件回复" },
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
          elements: [{ tag: "plain_text", content: "仅匹配合作回复；原邮件仍转发 Gmail。飞书接口接收不代表你已阅读。" }],
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
      autoSubmitted: cleanText(message.headers.get("auto-submitted"), 120).toLowerCase(),
      precedence: cleanText(message.headers.get("precedence"), 120).toLowerCase(),
    };
  }
  const parser = new PostalMime();
  const rawEmail = new Response(message.raw);
  const parsed = await parser.parse(await rawEmail.arrayBuffer());
  return {
    sender: senderAddress(parsed, message.from),
    subject: cleanText(parsed.subject || fallbackSubject, 300),
    snippet: cleanText(parsed.text || parsed.html),
    autoSubmitted: cleanText(message.headers.get("auto-submitted"), 120).toLowerCase(),
    precedence: cleanText(message.headers.get("precedence"), 120).toLowerCase(),
  };
}


function isAutomatedEmail(email) {
  const sender = String(email?.sender || "").toLowerCase();
  const subject = String(email?.subject || "");
  const localPart = sender.includes("@") ? sender.split("@", 1)[0] : sender;
  const autoSubmitted = String(email?.autoSubmitted || "").toLowerCase();
  const precedence = String(email?.precedence || "").toLowerCase();
  return (
    sender.endsWith("@raidbench.com")
    || sender.endsWith("@notify.raidbench.com")
    || /^(?:no-?reply|do-?not-?reply|mailer-daemon|postmaster|bounce|notifications?)$/i.test(localPart)
    || (autoSubmitted && autoSubmitted !== "no")
    || ["bulk", "junk", "list"].includes(precedence)
    || AUTOMATED_SUBJECT_PATTERN.test(subject)
  );
}


async function isPartnershipReply(email) {
  const sender = String(email?.sender || "").trim().toLowerCase();
  if (!sender || isAutomatedEmail(email)) return false;
  const separator = sender.lastIndexOf("@");
  const domain = separator >= 0 ? sender.slice(separator + 1) : "";
  return (
    KNOWN_PARTNER_CONTACT_HASHES.has(await sha256(sender))
    || (domain && KNOWN_PARTNER_DOMAIN_HASHES.has(await sha256(domain)))
    || PARTNER_SUBJECT_PATTERN.test(String(email?.subject || ""))
  );
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
        autoSubmitted: cleanText(message.headers.get("auto-submitted"), 120).toLowerCase(),
        precedence: cleanText(message.headers.get("precedence"), 120).toLowerCase(),
      };
      console.error("Incoming email parsing failed", error instanceof Error ? error.message : String(error));
    }
    await message.forward(env.FORWARD_TO_EMAIL);
    ctx.waitUntil(
      (async () => {
        const notifyPartnerReply = await isPartnershipReply(parsed);
        let feishuStatus = notifyPartnerReply ? "accepted" : "skipped_non_partner";
        if (notifyPartnerReply) {
          try {
            await sendFeishuAlert(env, parsed);
          } catch (error) {
            feishuStatus = "failed";
            console.error("Feishu partner-email alert failed", error instanceof Error ? error.message : String(error));
          }
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


export { cleanText, feishuSignature, isAutomatedEmail, isPartnershipReply, parseIncomingEmail, recordMonitorEvent, sendFeishuAlert, sha256 };

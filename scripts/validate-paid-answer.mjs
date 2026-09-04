import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(scriptPath), "..");

function hoursBetween(later, earlier) {
  return (new Date(later).getTime() - new Date(earlier).getTime()) / 3_600_000;
}

function validDate(value) {
  return typeof value === "string" && Number.isFinite(new Date(value).getTime());
}

export function validatePaidAnswer(answer, policy) {
  const errors = [];
  const required = ["policyVersion", "answerId", "orderId", "game", "gameVersion", "generatedAt", "customerQuestion", "intake", "claims", "calculations", "answerText", "limitations", "qa", "delivery"];
  for (const key of required) if (!(key in answer)) errors.push(`Missing required field: ${key}`);
  if (errors.length) return errors;

  if (answer.policyVersion !== policy.policyVersion) errors.push("Answer policy version does not match the active policy.");
  if (!answer.gameVersion.trim()) errors.push("A named game version or source-check context is required.");
  if (!validDate(answer.generatedAt) || !validDate(answer.qa?.reviewedAt)) errors.push("Generated and reviewed timestamps must be valid ISO dates.");
  if (answer.intake?.status !== "complete" || answer.intake?.missingFields?.length) errors.push("Customer intake is incomplete.");
  if (answer.qa?.decision !== "approve" || answer.delivery?.status !== "ready") errors.push("QA decision and delivery status must both approve release.");
  if (answer.qa?.authorAgentId === answer.qa?.reviewerAgentId) errors.push("The independent reviewer must differ from the answer author.");
  if (answer.qa?.criticalClaimsVerified !== true) errors.push("QA did not affirm all critical claims.");
  if (answer.qa?.calculationTestsPassed !== true) errors.push("QA did not affirm calculation tests.");
  if (answer.qa?.versionChecked !== true) errors.push("QA did not affirm the game-version check.");
  if (Number(answer.delivery?.correctionWindowDays) < Number(policy.correctionPolicy.factualErrorCorrectionWindowDays)) errors.push("Correction window is shorter than policy.");

  const calculations = new Map((answer.calculations || []).map((item) => [item.calculationId, item]));
  const authoritative = new Set(policy.criticalClaimRules.authoritativeSourceTypes);
  const allowed = new Set(policy.criticalClaimRules.allowedSourceTypes);
  const claimIds = new Set();

  for (const claim of answer.claims || []) {
    if (!claim.claimId || claimIds.has(claim.claimId)) errors.push(`Claim ID is missing or duplicated: ${claim.claimId || "unknown"}`);
    claimIds.add(claim.claimId);
    const evidence = Array.isArray(claim.evidence) ? claim.evidence : [];
    const evidenceTypes = new Set(evidence.map((item) => item.sourceType));
    if (claim.status === "conflict" || claim.status === "unsupported") errors.push(`${claim.claimId} has blocking evidence status ${claim.status}.`);
    if (claim.critical) {
      if (claim.status !== "verified") errors.push(`${claim.claimId} is critical but not verified.`);
      if (evidence.length < policy.criticalClaimRules.minimumEvidenceItems) errors.push(`${claim.claimId} has fewer than the required evidence items.`);
      if (evidence.filter((item) => authoritative.has(item.sourceType)).length < policy.criticalClaimRules.requiredAuthoritativeEvidenceItems) errors.push(`${claim.claimId} lacks authoritative evidence.`);
    }
    for (const item of evidence) {
      if (!allowed.has(item.sourceType)) errors.push(`${claim.claimId} uses a disallowed source type: ${item.sourceType}`);
      if (item.sourceType !== "customer_input" && !/^https:\/\//i.test(item.url || "")) errors.push(`${claim.claimId} has a non-HTTPS evidence URL.`);
      if (!validDate(item.retrievedAt)) errors.push(`${claim.claimId} has an invalid evidence timestamp.`);
      if (answer.patchSensitive && validDate(item.retrievedAt) && validDate(answer.generatedAt)) {
        const age = hoursBetween(answer.generatedAt, item.retrievedAt);
        if (age < 0 || age > policy.criticalClaimRules.patchSensitiveEvidenceMaxAgeHoursAtDelivery) errors.push(`${claim.claimId} uses stale or future patch-sensitive evidence.`);
      }
    }
    if (claim.claimType === "numeric" && policy.criticalClaimRules.numericClaimsRequireCalculationTest) {
      const calculation = calculations.get(claim.calculationId);
      if (!calculation || calculation.passed !== true) errors.push(`${claim.claimId} lacks a passing calculation test.`);
      if (calculation && Math.abs(Number(calculation.actual) - Number(calculation.expected)) > Number(calculation.tolerance)) errors.push(`${claim.claimId} calculation exceeds tolerance.`);
    }
    if (
      claim.claimType === "numeric"
      && policy.criticalClaimRules.numericClaimsRequireDeterministicEvidence
      && !["deterministic_test", "in_game_test"].some((type) => evidenceTypes.has(type))
    ) errors.push(`${claim.claimId} lacks deterministic evidence for a numeric claim.`);
    if (
      claim.claimType === "mechanic"
      && claim.critical
      && policy.criticalClaimRules.mechanicClaimsRequireGameEvidence
      && !["official", "official_wiki", "in_game_test"].some((type) => evidenceTypes.has(type))
    ) errors.push(`${claim.claimId} lacks authoritative game evidence for a mechanic claim.`);
    if (
      claim.claimType === "customer_context"
      && policy.criticalClaimRules.customerContextClaimsRequireCustomerInput
      && !evidenceTypes.has("customer_input")
    ) errors.push(`${claim.claimId} lacks customer-input evidence for a customer-context claim.`);
  }

  const releaseText = [answer.answerText, ...(answer.claims || []).map((claim) => claim.text)].join(" ").toLowerCase();
  if (/\bev_[a-z0-9_]+\b/i.test(answer.answerText)) errors.push("Customer-facing answer text exposes an internal evidence ID.");
  for (const phrase of policy.forbiddenOutcomePhrases) {
    if (releaseText.includes(phrase.toLowerCase())) errors.push(`Forbidden outcome wording found: ${phrase}`);
  }
  return errors;
}

if (process.argv[1] && path.resolve(process.argv[1]) === scriptPath) {
  const input = process.argv[2] ? path.resolve(process.cwd(), process.argv[2]) : path.join(root, "templates", "paid-answer.sample.json");
  const policy = JSON.parse(fs.readFileSync(path.join(root, "content", "answer-quality-policy.json"), "utf8"));
  const answer = JSON.parse(fs.readFileSync(input, "utf8"));
  const errors = validatePaidAnswer(answer, policy);
  if (errors.length) {
    console.error(`BLOCKED: ${errors.length} paid-answer QA error(s)`);
    for (const error of errors) console.error(`- ${error}`);
    process.exitCode = 1;
  } else {
    console.log(`APPROVED: ${answer.answerId} passed paid-answer QA.`);
  }
}

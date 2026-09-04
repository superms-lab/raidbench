import assert from "node:assert/strict";
import fs from "node:fs";
import { validatePaidAnswer } from "../scripts/validate-paid-answer.mjs";

const policy = JSON.parse(fs.readFileSync("content/answer-quality-policy.json", "utf8"));
const sample = JSON.parse(fs.readFileSync("templates/paid-answer.sample.json", "utf8"));
const copy = (value) => JSON.parse(JSON.stringify(value));

assert.deepEqual(validatePaidAnswer(sample, policy), []);

{
  const answer = copy(sample);
  answer.claims[0].evidence = answer.claims[0].evidence.slice(0, 1);
  assert(validatePaidAnswer(answer, policy).some((error) => error.includes("fewer than")));
}

{
  const answer = copy(sample);
  answer.qa.reviewerAgentId = answer.qa.authorAgentId;
  assert(validatePaidAnswer(answer, policy).some((error) => error.includes("reviewer")));
}

{
  const answer = copy(sample);
  answer.answerText = "This is a guaranteed win.";
  assert(validatePaidAnswer(answer, policy).some((error) => error.includes("Forbidden")));
}

{
  const answer = copy(sample);
  answer.calculations[0].actual = 7;
  assert(validatePaidAnswer(answer, policy).some((error) => error.includes("tolerance")));
}

{
  const answer = copy(sample);
  answer.claims[0].evidence = answer.claims[0].evidence.filter((item) => item.sourceType !== "deterministic_test");
  assert(validatePaidAnswer(answer, policy).some((error) => error.includes("deterministic evidence")));
}

{
  const answer = copy(sample);
  answer.answerText = "Use the supported result [ev_internal_reference].";
  assert(validatePaidAnswer(answer, policy).some((error) => error.includes("internal evidence ID")));
}

console.log("Paid-answer validator tests passed.");

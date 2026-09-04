import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";


const require = createRequire(import.meta.url);
const root = process.cwd();
const engine = require(path.join(root, "multi-game-tool-engine.js"));
const tools = JSON.parse(fs.readFileSync(path.join(root, "content", "multigame-tools.json"), "utf8")).tools;
const toolById = new Map(tools.map((tool) => [tool.id, tool]));

function argument(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

function valueAtPath(value, dottedPath) {
  return dottedPath.split(".").reduce((current, part) => {
    if (current === null || current === undefined) return undefined;
    return current[Number.isInteger(Number(part)) && String(Number(part)) === part ? Number(part) : part];
  }, value);
}

export function evaluateSuite(suite) {
  const requestedCase = argument("--case");
  const cases = suite.cases.filter((item) => item.calculationFixture && (!requestedCase || item.caseId === requestedCase));
  if (requestedCase && !cases.length) throw new Error(`No calculation fixture found for ${requestedCase}`);
  const results = cases.map((item) => {
    const fixture = item.calculationFixture;
    const tool = toolById.get(fixture.toolId);
    if (!tool) throw new Error(`${item.caseId} references unknown tool ${fixture.toolId}`);
    const calculated = engine.calculate(tool, fixture.inputs);
    const assertions = fixture.assertions.map((assertion) => {
      const actual = Number(valueAtPath(calculated, assertion.path));
      const expected = Number(assertion.expected);
      const tolerance = Number(assertion.tolerance);
      const passed = Number.isFinite(actual) && Math.abs(actual - expected) <= tolerance;
      return { ...assertion, actual, passed };
    });
    return {
      caseId: item.caseId,
      productId: item.productId,
      toolId: fixture.toolId,
      passed: assertions.every((assertion) => assertion.passed),
      assertions,
    };
  });
  return {
    cases: results.length,
    assertions: results.reduce((sum, item) => sum + item.assertions.length, 0),
    passed: results.every((item) => item.passed),
    results,
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(import.meta.filename)) {
  const suitePath = path.resolve(root, argument("--suite", "private-data/shadow-benchmarks/latest-suite.json"));
  const suite = JSON.parse(fs.readFileSync(suitePath, "utf8"));
  try {
    const report = evaluateSuite(suite);
    if (process.argv.includes("--json")) console.log(JSON.stringify(report));
    else console.log(`Shadow calculations: ${report.cases} cases, ${report.assertions} assertions, ${report.passed ? "PASS" : "FAIL"}.`);
    if (!report.passed) process.exitCode = 1;
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  }
}

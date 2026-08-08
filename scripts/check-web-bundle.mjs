import { readdir, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import process from "node:process";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const distDirectory = path.join(repositoryRoot, "apps/web/dist/assets");
const files = await readdir(distDirectory);
const sizes = await Promise.all(
  files.map(async (file) => ({
    file,
    bytes: (await stat(path.join(distDirectory, file))).size,
  })),
);

const javascript = sizes.filter(({ file }) => file.endsWith(".js"));
const stylesheets = sizes.filter(({ file }) => file.endsWith(".css"));
const entry = javascript.find(({ file }) => file.startsWith("index-"));
const largestJavascript = javascript.reduce((largest, current) =>
  current.bytes > largest.bytes ? current : largest,
);
const largestStylesheet = stylesheets.reduce(
  (largest, current) => (current.bytes > largest.bytes ? current : largest),
  { file: "none", bytes: 0 },
);

const budgets = [
  ["initial JavaScript", entry?.bytes ?? 0, 700_000],
  ["largest JavaScript chunk", largestJavascript.bytes, 900_000],
  ["largest stylesheet", largestStylesheet.bytes, 150_000],
];

console.log(`Initial JavaScript: ${entry?.file ?? "missing"} (${entry?.bytes ?? 0} bytes)`);
console.log(`Largest JavaScript chunk: ${largestJavascript.file} (${largestJavascript.bytes} bytes)`);
console.log(`Largest stylesheet: ${largestStylesheet.file} (${largestStylesheet.bytes} bytes)`);

const failures = budgets.filter(([, actual, limit]) => actual > limit);
if (failures.length) {
  for (const [name, actual, limit] of failures) {
    console.error(`Bundle budget exceeded: ${name} is ${actual} bytes; limit is ${limit} bytes.`);
  }
  process.exitCode = 1;
}

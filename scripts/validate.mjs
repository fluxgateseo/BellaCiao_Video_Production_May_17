#!/usr/bin/env node
// Dependency-free repo integrity check for CI.
// - All JSON parses.
// - manifest.json: project + driveRoot + artifacts[].
// - characters/registry.json: every character has identity text + >=1 ref id.
// - content-queue/queue.json: items[] each valid against the status enum.
// - config/defaults.json: engine === "higgsfield", approval gate enabled.
// - No binary files are tracked in git (GitHub = text source of truth).

import { readFileSync, existsSync } from "node:fs";
import { execSync } from "node:child_process";

const ROOT = new URL("..", import.meta.url).pathname;
const errors = [];
const fail = (m) => errors.push(m);

const readJson = (rel) => {
  const p = ROOT + rel;
  if (!existsSync(p)) { fail(`missing file: ${rel}`); return null; }
  try { return JSON.parse(readFileSync(p, "utf8")); }
  catch (e) { fail(`invalid JSON ${rel}: ${e.message}`); return null; }
};

const manifest = readJson("manifest.json");
if (manifest) {
  if (manifest.project !== "BellaCiao_Video_Production_May_17") fail("manifest.project must be BellaCiao_Video_Production_May_17");
  if (!manifest.driveRoot) fail("manifest.driveRoot missing");
  if (!Array.isArray(manifest.artifacts)) fail("manifest.artifacts must be an array");
}

const registry = readJson("characters/registry.json");
if (registry) {
  if (!registry.characters || typeof registry.characters !== "object") {
    fail("registry.characters missing");
  } else {
    for (const [id, c] of Object.entries(registry.characters)) {
      const hasIdentity = c.identity_lock || c.lock || c.enzo_lock || c.maria_lock;
      if (!hasIdentity) fail(`registry.${id}: no identity/lock text`);
      const refIds = Object.entries(c.refs || {})
        .filter(([k]) => !k.endsWith("_note") && k !== "primary" && k !== "higgsfieldCustomReferenceId")
        .map(([, v]) => v);
      if (refIds.length === 0) fail(`registry.${id}: no Drive reference file id`);
    }
  }
}

const queue = readJson("content-queue/queue.json");
const STATUSES = ["draft","script_ready","prompts_ready","keyframes_ready","storyboard_approved","video_generating","rendered","published","rejected"];
if (queue) {
  if (!Array.isArray(queue.items)) fail("queue.items must be an array");
  else queue.items.forEach((it, i) => {
    if (!it.id) fail(`queue.items[${i}].id missing`);
    if (!STATUSES.includes(it.status)) fail(`queue.items[${i}].status invalid: ${it.status}`);
  });
}

const cfg = readJson("config/defaults.json");
if (cfg) {
  if (cfg.engine !== "higgsfield") fail("config.engine must be 'higgsfield'");
  if (!(cfg.approvalGate && cfg.approvalGate.enabled === true)) fail("config.approvalGate.enabled must be true");
}

readJson("config/drive-folders.json");
readJson("schemas/manifest.schema.json");
readJson("schemas/content-item.schema.json");
readJson("schemas/config.schema.json");

// Binary guard: GitHub is text-only; binaries belong in Drive.
const BINARY_RE = /\.(png|jpe?g|webp|gif|bmp|tiff?|mp4|mov|avi|mkv|webm|wav|mp3|aac|flac|m4a|zip|tar|gz|7z|pdf|psd|ai)$/i;
try {
  const tracked = execSync("git ls-files", { cwd: ROOT, encoding: "utf8" }).split("\n").filter(Boolean);
  const bins = tracked.filter((f) => BINARY_RE.test(f));
  if (bins.length) fail(`binary files tracked in git (must live in Drive): ${bins.join(", ")}`);
} catch {
  console.warn("warning: git ls-files unavailable, skipping binary guard");
}

if (errors.length) {
  console.error("VALIDATION FAILED:");
  for (const e of errors) console.error(" - " + e);
  process.exit(1);
}
console.log("validation passed");

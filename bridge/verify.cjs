#!/usr/bin/env node
'use strict';
// Offline verification only: never starts a paid model or connects to Discord.
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
function run(args, cwd = root) {
  const result = spawnSync(process.execPath, args, { cwd, stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
for (const repo of ['clocktower-ai', 'discord-botc']) {
  const compiler = path.join(root, repo, 'node_modules/typescript/bin/tsc');
  if (!fs.existsSync(compiler)) throw new Error(`Install ${repo} dependencies before verification (see bridge/README.md).`);
  run([compiler], path.join(root, repo));
}
const tests = fs.readdirSync(__dirname).filter(name => name === 'test.cjs' || name.endsWith('-test.cjs')).sort();
run(['--test', ...tests.map(name => path.join(__dirname, name))]);

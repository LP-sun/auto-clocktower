const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
fs.mkdirSync(path.join(__dirname, 'patches'), { recursive: true });
for (const name of ['discord-botc', 'clocktower-ai']) {
  const repo = path.resolve(__dirname, '..', name);
  fs.writeFileSync(path.join(__dirname, 'patches', name + '.patch'), execFileSync('git', ['diff', '--binary', 'HEAD'], { cwd: repo }));
  fs.copyFileSync(path.join(repo, 'package-lock.json'), path.join(__dirname, 'patches', name + '.package-lock.json'));
}
console.log('Saved source patches and dependency locks.');

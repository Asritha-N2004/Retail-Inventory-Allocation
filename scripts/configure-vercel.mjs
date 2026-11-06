import { randomBytes } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const cli = path.join(root,'.tools/vercel/node_modules/vercel/dist/vc.js');
const secrets = { JWT_SECRET:randomBytes(48).toString('hex') };
for (const [key,value] of Object.entries(secrets)) {
  const result=spawnSync(process.execPath,[cli,'env','add',key,'--environment','production,preview','--sensitive','--yes','--scope','resum-projects'],{input:value+'\n',encoding:'utf8',cwd:root});
  if(result.status!==0) throw new Error(`Could not configure ${key}: ${result.stderr}`);
  console.log(`${key} configured securely.`);
}
for (const [key,value] of Object.entries({AUTO_SEED:'false'})) {
  const result=spawnSync(process.execPath,[cli,'env','add',key,'--environment','production,preview','--yes','--scope','resum-projects'],{input:value+'\n',encoding:'utf8',cwd:root});
  if(result.status!==0) throw new Error(`Could not configure ${key}: ${result.stderr}`);
  console.log(`${key} configured.`);
}

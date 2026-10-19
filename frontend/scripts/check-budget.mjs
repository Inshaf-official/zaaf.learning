import fs from 'node:fs';import path from 'node:path';import{gzipSync}from 'node:zlib';
const root=path.resolve('dist');const manifest=JSON.parse(fs.readFileSync(path.join(root,'.vite/manifest.json'),'utf8'));const keys=Object.keys(manifest);const included=new Set();
function add(key){const entry=manifest[key];if(!entry||included.has(entry.file))return;included.add(entry.file);for(const dependency of entry.imports||[])add(dependency)}
for(const key of keys)if(key==='index.html'||/src\/features\/(Login|Dashboard|DashboardSummary|MedicalAlerts|PwaUpdate|InstitutionLogo)\.tsx$/.test(key))add(key);
for(const extra of ['registerSW.js','sw.js'])if(fs.existsSync(path.join(root,extra)))included.add(extra);
let bytes=0;for(const file of included){if(file.endsWith('.js'))bytes+=gzipSync(fs.readFileSync(path.join(root,file))).length}
const budget=180000;console.log(JSON.stringify({path:'login and dashboard including service worker',gzippedJavaScriptBytes:bytes,budgetBytes:budget,passed:bytes<budget,files:[...included]},null,2));if(bytes>=budget)process.exit(1);

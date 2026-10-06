// Dependency-free local preview; serves this site only. Not a production server.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = fs.realpathSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'));
const port = Number(process.env.PORT || 8080);
const prefix = (process.env.BASE_PATH || '').replace(/\/$/, '');
if (prefix && !/^\/[a-zA-Z0-9_/-]+$/.test(prefix)) throw new Error('BASE_PATH must be a slash-prefixed path, such as /electricity-project');
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.pdf': 'application/pdf', '.md': 'text/plain; charset=utf-8' };
http.createServer((req, res) => {
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end('Method not allowed'); return; }
  let pathname; try { pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname); } catch { res.writeHead(400); res.end('Bad path'); return; }
  if (pathname === prefix && prefix) { res.writeHead(301, { Location: prefix + '/' }); res.end(); return; }
  if (!pathname.startsWith(prefix + '/')) { res.writeHead(404); res.end('Not found'); return; }
  const local = pathname.slice(prefix.length);
  const requested = path.resolve(root, '.' + local, local.endsWith('/') ? 'index.html' : '');
  try {
    const real = fs.realpathSync(requested);
    if (!real.startsWith(root + path.sep) || !fs.statSync(real).isFile()) throw new Error('Outside site');
    res.writeHead(200, { 'Content-Type': types[path.extname(real).toLowerCase()] || 'application/octet-stream', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
    if (req.method === 'HEAD') res.end(); else fs.createReadStream(real).pipe(res);
  } catch { res.writeHead(404); res.end('Not found'); }
}).listen(port, '127.0.0.1', () => console.log(`Preview: http://127.0.0.1:${port}${prefix}/`));

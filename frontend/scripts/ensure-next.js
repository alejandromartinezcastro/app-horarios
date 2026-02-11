#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const nextBin = path.join(__dirname, '..', 'node_modules', '.bin', process.platform === 'win32' ? 'next.cmd' : 'next');

if (!fs.existsSync(nextBin)) {
  console.error('\n[frontend] Dependencias no instaladas.\n');
  console.error('Ejecuta primero: npm --prefix frontend install');
  console.error('Luego vuelve a correr: npm --prefix frontend run build\n');
  process.exit(1);
}

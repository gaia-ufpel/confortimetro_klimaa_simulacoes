import { existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { platform } from "node:os";

const python = platform() === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python";

if (!existsSync(python)) {
  console.error(`Ambiente virtual não encontrado em ${python}. Execute: python -m venv .venv`);
  process.exit(1);
}

const checks = {
  lint: ["-m", "ruff", "check", "."],
  // A base ainda não é integralmente anotada. Verifica os pontos de entrada
  // sem transformar módulos legados sem tipagem em bloqueio de push.
  typecheck: ["-m", "mypy", "--follow-imports=skip", "--ignore-missing-imports", "cli.py", "main.py"],
  test: ["-m", "pytest", "tests", "-q"],
};

const selected = process.argv.slice(2);
const names = selected.length ? selected : Object.keys(checks);

for (const name of names) {
  if (!(name in checks)) {
    console.error(`Verificação desconhecida: ${name}`);
    process.exit(1);
  }
  console.log(`\n> ${name}`);
  execFileSync(python, checks[name], { stdio: "inherit" });
}

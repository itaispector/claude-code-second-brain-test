export const log = {
  info: (...a) => process.stdout.write(`[info] ${a.join(" ")}\n`),
  error: (...a) => process.stderr.write(`[error] ${a.join(" ")}\n`),
};

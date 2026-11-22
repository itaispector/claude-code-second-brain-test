#!/usr/bin/env node
import { fetchReleases } from "./vendors/spotify.js";

const args = process.argv.slice(2);
const artist = args[0];

if (!artist) {
  console.error("usage: release-tracker <artist>");
  process.exit(1);
}

const releases = await fetchReleases(artist);
for (const r of releases) {
  console.log(`${r.date}  ${r.title}`);
}

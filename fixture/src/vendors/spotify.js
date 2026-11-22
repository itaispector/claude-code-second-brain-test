export async function fetchReleases(artist) {
  // TODO: real API call
  return [
    { title: `${artist} - Demo Single`, date: new Date("2026-11-01") },
    { title: `${artist} - Demo EP`, date: new Date("2026-12-15") },
  ];
}

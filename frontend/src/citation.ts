export function findCitationSpanRange(spans: string[], quote: string): number[] {
  const normalize = (text: string) => text.replace(/\s+/g, " ").trim().toLowerCase();
  const target = normalize(quote);
  if (!target) return [];
  let bestRange: number[] = [];
  for (let start = 0; start < spans.length; start += 1) {
    let joined = "";
    for (let end = start; end < spans.length && end < start + 35; end += 1) {
      joined = `${joined} ${spans[end]}`;
      if (normalize(joined).includes(target)) {
        const range = Array.from({ length: end - start + 1 }, (_, index) => start + index);
        if (!bestRange.length || range.length < bestRange.length) bestRange = range;
        break;
      }
      if (normalize(joined).length > target.length + 80) break;
    }
  }
  return bestRange;
}

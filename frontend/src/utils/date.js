export function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch (_) {
    return iso;
  }
}

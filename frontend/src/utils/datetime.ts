type HasCreatedAt = {
  created_at: string
}

export function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString()
}

export function sortByCreatedAtDesc<T extends HasCreatedAt>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
}

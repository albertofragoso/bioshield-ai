import path from 'path'

export function getLegalDocPath(filename: string): string {
  // process.cwd() en Next.js apunta a frontend/
  // '../docs/legal/' resuelve a la raíz del repo
  return path.join(process.cwd(), '..', 'docs', 'legal', filename)
}

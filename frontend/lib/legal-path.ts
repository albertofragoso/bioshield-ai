import path from "path";

export function getLegalDocPath(filename: string): string {
  return path.join(process.cwd(), "content", "legal", filename);
}

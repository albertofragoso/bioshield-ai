import sharp from "sharp";
import { readdirSync, mkdirSync } from "fs";
import { join } from "path";

const INPUT_DIR = join(process.cwd(), "public/avatars");
const OUTPUT_DIR = join(process.cwd(), "public/avatars/avif");

(async () => {
  mkdirSync(OUTPUT_DIR, { recursive: true });

  const pngs = readdirSync(INPUT_DIR).filter((f) => f.endsWith(".png"));

  for (const file of pngs) {
    const input = join(INPUT_DIR, file);
    const output = join(OUTPUT_DIR, file.replace(".png", ".avif"));

    await sharp(input)
      .resize({ width: 256, withoutEnlargement: true })
      .avif({ quality: 60, effort: 4 })
      .toFile(output);

    console.log(`✓ ${file} → avif/${file.replace(".png", ".avif")}`);
  }
})();

import { writeFile } from "node:fs/promises";

const sourceUrl = process.env.MOCK_SNAPSHOT_URL ?? "http://127.0.0.1:3000/api/data/snapshot";
const response = await fetch(sourceUrl);
if (!response.ok) {
  throw new Error(`Không thể export snapshot từ ${sourceUrl} (${response.status}). Hãy bật ALLOW_MOCK_SNAPSHOT_EXPORT=true và chạy dev server.`);
}
const output = new URL("../quto-data.snapshot.json", import.meta.url);
await writeFile(output, await response.text(), "utf8");
process.stdout.write(`Đã tạo ${output.pathname}\n`);

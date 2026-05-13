import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const [, , inputCsvPath, outputXlsxPath] = process.argv;

if (!inputCsvPath || !outputXlsxPath) {
  console.error("Usage: node export_master_player_bios_workbook.mjs <input.csv> <output.xlsx>");
  process.exit(1);
}

const csvText = await fs.readFile(inputCsvPath, "utf8");
const sheetName = "Master Player Bios 2026";
const workbook = await Workbook.fromCSV(csvText, { sheetName });

await workbook.render({
  sheetName,
  range: "A1:AJ20",
  scale: 1.5,
});

await fs.mkdir(path.dirname(outputXlsxPath), { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputXlsxPath);

console.log(JSON.stringify({ output_xlsx_path: outputXlsxPath }));

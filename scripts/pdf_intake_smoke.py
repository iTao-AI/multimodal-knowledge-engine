from __future__ import annotations

import argparse
import json
from pathlib import Path

from mke.adapters.pdf import PdfExtractionError, PyMuPDFPdfExtractor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_dir", type=Path)
    args = parser.parse_args()
    extractor = PyMuPDFPdfExtractor()
    results = []
    for path in sorted(args.pdf_dir.glob("*.pdf")):
        try:
            result = extractor.extract(path)
            results.append(
                {
                    "file": path.name,
                    "status": "ok",
                    "total_pages": result.report.total_pages,
                    "extracted_pages": result.report.extracted_pages,
                    "suspected_scanned_pages": result.report.suspected_scanned_pages,
                    "total_extracted_chars": result.report.total_extracted_chars,
                }
            )
        except PdfExtractionError as error:
            report = error.report
            results.append(
                {
                    "file": path.name,
                    "status": "failed",
                    "failure_reason": str(error),
                    "total_pages": report.total_pages if report else 0,
                    "extracted_pages": report.extracted_pages if report else 0,
                    "suspected_scanned_pages": (
                        report.suspected_scanned_pages if report else 0
                    ),
                    "total_extracted_chars": report.total_extracted_chars if report else 0,
                }
            )
    print(json.dumps({"pdf_count": len(results), "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

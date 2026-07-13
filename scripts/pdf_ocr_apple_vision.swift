#!/usr/bin/env swift

import CoreGraphics
import Foundation
import ImageIO
import Vision

enum ChildFailure: Error {
    case invalidArguments
    case invalidInput
    case recognitionFailed
    case invalidOutput
}

struct Arguments {
    let input: URL
    let output: URL
    let pageNumber: Int
}

func parseArguments() throws -> Arguments {
    let raw = Array(CommandLine.arguments.dropFirst())
    guard raw.count == 6 else { throw ChildFailure.invalidArguments }
    var values: [String: String] = [:]
    var index = 0
    while index < raw.count {
        let key = raw[index]
        guard ["--input", "--output", "--page-number"].contains(key),
              values[key] == nil else {
            throw ChildFailure.invalidArguments
        }
        values[key] = raw[index + 1]
        index += 2
    }
    guard let input = values["--input"],
          let output = values["--output"],
          let pageText = values["--page-number"],
          let pageNumber = Int(pageText), pageNumber > 0 else {
        throw ChildFailure.invalidArguments
    }
    return Arguments(
        input: URL(fileURLWithPath: input),
        output: URL(fileURLWithPath: output),
        pageNumber: pageNumber
    )
}

func loadImage(_ url: URL) throws -> CGImage {
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          CGImageSourceGetCount(source) == 1,
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw ChildFailure.invalidInput
    }
    return image
}

func recognize(_ image: CGImage) throws -> [[String: Any]] {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["en-US", "zh-Hans"]
    request.usesLanguageCorrection = false
    request.usesCPUOnly = true
    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])
    guard let observations = request.results else {
        throw ChildFailure.recognitionFailed
    }
    let ordered = observations.sorted { first, second in
        if first.boundingBox.maxY != second.boundingBox.maxY {
            return first.boundingBox.maxY > second.boundingBox.maxY
        }
        return first.boundingBox.minX < second.boundingBox.minX
    }
    return ordered.compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let box = observation.boundingBox
        return [
            "text": candidate.string.precomposedStringWithCanonicalMapping,
            "confidence": Double(candidate.confidence),
            "box": [Double(box.minX), Double(box.minY), Double(box.maxX), Double(box.maxY)],
        ]
    }
}

func writeResult(_ payload: [String: Any], to url: URL) throws {
    guard JSONSerialization.isValidJSONObject(payload) else {
        throw ChildFailure.invalidOutput
    }
    let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
    let handle = try FileHandle(forWritingTo: url)
    defer { try? handle.close() }
    try handle.truncate(atOffset: 0)
    try handle.write(contentsOf: data)
    try handle.synchronize()
}

do {
    let arguments = try parseArguments()
    let started = DispatchTime.now().uptimeNanoseconds
    let image = try loadImage(arguments.input)
    let lines = try recognize(image)
    guard !lines.isEmpty else { throw ChildFailure.recognitionFailed }
    let normalizedText = lines.compactMap { $0["text"] as? String }.joined(separator: "\n")
    let elapsed = DispatchTime.now().uptimeNanoseconds - started
    let payload: [String: Any] = [
        "schema": "mke.pdf_ocr_eval_result.v1",
        "provider": "apple-vision-local-v1",
        "profile": "phase0-200dpi-plain-text-v1",
        "page_number": arguments.pageNumber,
        "lines": lines,
        "normalized_text": normalizedText,
        "duration_ms": Int(elapsed / 1_000_000),
    ]
    try writeResult(payload, to: arguments.output)
} catch {
    FileHandle.standardError.write(Data("pdf ocr child failed\n".utf8))
    exit(2)
}

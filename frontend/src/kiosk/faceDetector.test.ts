import { describe, expect, it } from "vitest";

import { framingMessage } from "./faceDetector";

describe("enquadramento do rosto", () => {
  it("orienta o funcionário até o rosto estar bom para envio", () => {
    expect(framingMessage({ faces: 0, size: 0, centered: false })).toBe("Posicione o rosto na moldura");
    expect(framingMessage({ faces: 2, size: 0.3, centered: true })).toBe("Apenas uma pessoa por vez");
    expect(framingMessage({ faces: 1, size: 0.1, centered: true })).toBe("Aproxime-se da câmera");
    expect(framingMessage({ faces: 1, size: 0.3, centered: false })).toBe("Centralize o rosto na moldura");
    expect(framingMessage({ faces: 1, size: 0.3, centered: true })).toBeNull();
  });
});

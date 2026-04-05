import { vi } from "vitest";

export const html2pdfSetMock = vi.fn().mockReturnThis();
export const html2pdfFromMock = vi.fn().mockReturnThis();
export const html2pdfSaveMock = vi.fn();

export function resetHtml2pdfMocks() {
    html2pdfSetMock.mockClear();
    html2pdfFromMock.mockClear();
    html2pdfSaveMock.mockClear();
}

export default function html2pdf() {
    return {
        set: html2pdfSetMock,
        from: html2pdfFromMock,
        save: html2pdfSaveMock,
    };
}

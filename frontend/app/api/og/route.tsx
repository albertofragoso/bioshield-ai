import { ImageResponse } from "@vercel/og";

export const runtime = "edge";

export function GET() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#080c07",
        padding: "60px",
      }}
    >
      <div style={{ color: "#4ADE80", fontSize: 52, fontWeight: "bold", marginBottom: 16 }}>
        BioShield AI
      </div>
      <div
        style={{
          color: "#dcf0dc",
          fontSize: 32,
          textAlign: "center",
          maxWidth: 700,
          lineHeight: 1.3,
        }}
      >
        Lo que comes, en términos de TU sangre.
      </div>
      <div style={{ color: "#6b8a6a", fontSize: 18, marginTop: 28 }}>
        FDA · EFSA · Codex Alimentarius · Herramienta educativa
      </div>
    </div>,
    { width: 1200, height: 630 }
  );
}

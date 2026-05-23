import type { Metadata } from "next";
import { Pacifico, Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

// Pacifico — solo para el wordmark "BioShield" (único peso 400)
const pacifico = Pacifico({
  variable: "--font-pacifico",
  weight: "400",
  subsets: ["latin"],
  display: "swap",
});

// Space Grotesk — cuerpo general (inputs, botones, párrafos)
const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  weight: ["300", "400", "500", "600", "700"],
  subsets: ["latin"],
  display: "swap",
});

// JetBrains Mono — labels, alerts, metadata técnica (CAS, E-numbers, barcodes)
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "BioShield AI — Nutrición inteligente",
    template: "%s · BioShield AI",
  },
  description:
    "Escanea cualquier producto y descubre si sus aditivos son compatibles con tus análisis de laboratorio. Herramienta educativa basada en FDA, EFSA y Codex Alimentarius.",
  keywords: ["nutrición", "biomarcadores", "aditivos", "salud", "México", "EFSA", "FDA"],
  openGraph: {
    title: "BioShield AI — Nutrición inteligente",
    description: "Lo que comes, en términos de TU sangre.",
    images: [{ url: "/api/og", width: 1200, height: 630 }],
    locale: "es_MX",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "BioShield AI",
    description: "Lo que comes, en términos de TU sangre.",
    images: ["/api/og"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      // Dark-only por diseño: forzamos la clase dark para que shadcn y cualquier
      // consumidor de prefers-color-scheme reciba el tema correcto. No hay toggle.
      className={`dark ${pacifico.variable} ${spaceGrotesk.variable} ${jetbrainsMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

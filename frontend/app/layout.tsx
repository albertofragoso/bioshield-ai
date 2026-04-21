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
  title: "BioShield AI",
  description:
    "Analiza etiquetas nutricionales y cruza aditivos con tus biomarcadores",
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
